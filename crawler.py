import requests
import sqlite3
import time
from bs4 import BeautifulSoup
from plyer import notification

# Configuração do User-Agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
}

DB_NAME = "news.db"
INTERVAL = 600  # 10 minutos


# Função para criar a base de dados SQLite
def create_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS noticias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            link TEXT NOT NULL UNIQUE,
            data TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# Função para buscar notícias do CM7 Brasil
def get_cm7_news(pages=2):
    base_url = "https://cm7brasil.com/noticias/policia/page/"
    news_list = []

    for page in range(1, pages + 1):
        url = f"{base_url}{page}/"
        response = requests.get(url, headers=HEADERS)

        if response.status_code != 200:
            print(f"Falha ao obter página {page}: {response.status_code}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article", class_="cm7-card")

        if not articles:
            print(f"Nenhuma notícia encontrada na página {page}.")
            continue

        for article in articles:
            title_tag = article.find("h2", class_="h3 cm7-card-title")
            link_tag = article.find("a", href=True)

            if title_tag and link_tag:
                title = title_tag.text.strip()
                link = link_tag["href"].strip()
                news_list.append((title, link))

    return news_list


# Função para buscar notícias do Portal do Holanda
def get_holanda_news():
    base_url = "https://www.portaldoholanda.com.br"
    url = f"{base_url}/policial"

    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Failed to fetch data: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    news_list = []

    for article in soup.select("div.columns"):
        title_tag = article.select_one("h3.destaque.titulo a")
        link_tag = article.select_one("h3.destaque.titulo a")

        if title_tag and link_tag:
            title = title_tag.text.strip()
            link = base_url + link_tag["href"]

            news_list.append((title, link))  # Retorna uma tupla ao invés de dicionário

    return news_list


# Função para salvar notícias no SQLite e retornar novas notícias
def save_news(news_list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    new_news = []

    for title, link in news_list:
        try:
            cursor.execute("INSERT INTO noticias (titulo, link) VALUES (?, ?)", (title, link))
            new_news.append((title, link))
        except sqlite3.IntegrityError:
            pass  # Ignorar notícias duplicadas

    conn.commit()
    conn.close()
    return new_news


# Função para exibir notificações no Windows
def send_notification(news_list):
    for title, link in news_list:
        notification.notify(
            title="Nova Notícia!",
            message=title,
            app_name="News Crawler",
            timeout=10  # Tempo da notificação em segundos
        )
        print(f"Notificação enviada: {title}")


# Criar banco de dados se não existir
create_database()

# Loop infinito para rodar o crawler a cada 10 minutos
while True:
    print("\nBuscando novas notícias...")
    cm7_news = get_cm7_news(pages=2)
    holanda_news = get_holanda_news()

    all_news = cm7_news + holanda_news  # Unifica todas as notícias

    if all_news:
        new_news = save_news(all_news)
        if new_news:
            print(f"{len(new_news)} novas notícias adicionadas!")
            send_notification(new_news)
        else:
            print("Nenhuma nova notícia.")
    else:
        print("Nenhuma nova notícia encontrada.")

    print("Aguardando 10 minutos para a próxima busca...")
    time.sleep(INTERVAL)
