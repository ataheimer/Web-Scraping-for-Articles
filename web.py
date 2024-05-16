import re
from bs4 import BeautifulSoup
from flask import Flask, render_template, request
from pymongo import MongoClient
import requests

# Web sayfasından veri almak için bir fonksiyon
def scrape_website(response, link, text):

    #html ayırma
    soup = BeautifulSoup(response.content, 'html.parser')

    #Yayın id ve makale id
    match = re.search(r'issue/(\d+)/(\d+)', link)
    if match:
        publisher_id = match.group(1)
        article_id = match.group(2)
        print("Yayıncı id:", publisher_id)
        print("Yayın id:", article_id)
    else:
        print("ID'ler bulunamadı.")

    #Yayın adı
    for title in soup.find_all("h3", class_="article-title"):
        if title and title.text.strip():
            article_title = title.text.strip()
    print("Yayın adı:", article_title)
    
    #Yazarların isimleri
    article_authors = []
    for author in soup.find_all("a", class_="is-user"):
        if author.text.strip() not in article_authors:
            article_authors.append(author.text.strip())
    print(article_authors)

    #Yayın türü
    table = soup.find("table", class_="record_properties table")
    rows = table.find_all("tr")
    for tr in rows:
        th_element = tr.find("th")
        if th_element and th_element.text.strip() == "Bölüm":
            td_element = tr.find("td")
            if td_element:
                article_type = td_element.text.strip()
                print("Bölüm:", article_type)
    
    #Yayımlanma tarihi
    table = soup.find("table", class_="record_properties table")
    rows = table.find_all("tr")
    for tr in rows:
        th_element = tr.find("th")
        if th_element and th_element.text.strip() == "Yayımlanma Tarihi":
            td_element = tr.find("td")
            if td_element:
                article_date = td_element.text.strip()
                print("Yayımlanma tarihi:", article_date)
    
    #Yayıncı adı
    article_publisher = soup.find("h1", id="journal-title").text.strip()
    print("Yayıncı adı:",article_publisher)

    #Anahtar kelimeler (Arama motorunda aratılan)
    article_searchkeys = text
    print("Anahtar kelimeler (Arama motorunda aratılan):", article_searchkeys)

    #Anahtar kelimeler (Makaleye ait)
    article_keys = []
    for key in soup.find_all('a'):
        href = key.get('href')
        if href and href.startswith('/tr/search?q=%22'):
            article_keys.append(key.text.strip())
    print("Anahtar kelimeler (Makaleye ait):", article_keys)

    #Özet
    article_abstract = soup.find("div", class_="article-abstract data-section").text.strip()
    print("Özet:", article_abstract)

    #Referanslar
    article_references = soup.find("td", class_="cite-table-item").find_next().text.strip()
    print("Referanslar:", article_references)

    #Alıntı sayısı
    citations = soup.find("ul", class_="fa-ul")
    if citations:
        article_citations = len(citations.find_all("li"))
        print("Alıntı sayısı:", article_citations)
    else:
        article_citations = "Alıntı bulunamadı."

    #Doi numarası (Eğer varsa)
    if soup.find("a", class_="doi-link"):
        article_doi = soup.find("a", class_="doi-link").text.strip()
        print("Doi numarası:", article_doi)
    else:
        article_doi = "Doi linki yok."
        print("Doi numarası bulunamadı.")

    #URL adresi
    article_url = link
    print("URL adresi:", article_url)

    #PDF linkini alma ve indirme
    for pdf in soup.find_all("a"):
        href = pdf.get("href")
        if href and href.startswith("/tr/download/article-file/"):
            article_pdf = f"https://dergipark.org.tr{href}"
            print("Pdf linki:", article_pdf)
            request = requests.get(article_pdf)
            file_name = f"PDF'ler/{article_title}.pdf"
            with open(file_name, "wb") as pdf_file:
                pdf_file.write(request.content)
            print(f"PDF indirildi")
            break
    
    #MongoDB'ye kaydetme
    id = article_title + ": " + article_id
    data = {
            "_id": id,
            "PDF linki": article_pdf,
            "Yayıncı id": publisher_id,
            "Yayın id": article_id,
            "Yayın adı": article_title,
            "Yazarların isimleri": article_authors,
            "Yayın türü": article_type,
            "Yayımlanma tarihi": article_date,
            "Yayıncı adı": article_publisher,
            "Anahtar kelimeler (Arama motorunda aratılan)": article_searchkeys,
            "Anahtar kelimeler (Makaleye ait)": article_keys,
            "Özet": article_abstract,
            "Referanslar": article_references,
            "Alıntı sayısı": article_citations,
            "Doi numarası (Eğer varsa)": article_doi,
            "URL adresi": article_url,
        }
    # Verinin MongoDB'de olup olmadığını kontrol et
    existing_data = collection.find_one(data)
    if existing_data is None:
        # Veri yoksa ekle
        collection.insert_one(data)
        print('Veri eklendi.')
    else:
        print('Veri zaten var, tekrar eklenmedi.')
    
    return data

def manage(text):
    header = {
        "user-agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    url = f"https://dergipark.org.tr/tr/search?q={text}&section=articles"
    response = requests.get(url, headers=header)
    content = response.content
    soup = BeautifulSoup(content, "html.parser")

    #Makale linklerini bul
    links = []
    counter = 0
    while counter < 10:
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and href.startswith('https://dergipark.org.tr/tr/pub/'):
                links.append(href)
                counter += 1
                if counter >= 10:
                    break

    #Scraping
    dataset = []
    for link in links:
        try:
            response = requests.get(link)
            if response.status_code == 200:
                print(f"\n{link} başarıyla çekildi.")
                data = scrape_website(response, link, text)
                dataset.append(data)
            else:
                print(f"{link} bağlantısı başarısız. Durum kodu: {response.status_code}")
        except Exception as e:
            print(f"{link} çekilirken bir hata oluştu: {str(e)}")
    return dataset

# Flask uygulamasını oluşturalım
app = Flask(__name__)

#MongoDB bağlantısı
client = MongoClient('mongodb+srv://ataemiruncu:<password>@cluster0.prqckre.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
db = client["Scraping"]
collection = db["History"]

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        dataset = manage(text = request.form['arama_terimi'])
        return render_template('results.html', kayitlar=dataset)
    else:
        kayitlar = collection.find()
        return render_template('index.html', kayitlar=kayitlar)

@app.route('/bilgiler', methods=['POST'])
def bilgiler():
    return render_template("records.html", kayit = request.form["kayit"])

if __name__ == '__main__':
    app.run(debug=True)