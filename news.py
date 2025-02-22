import sys
import requests
import sqlite3
import time
import threading
import webbrowser
from bs4 import BeautifulSoup
from winotify import Notification, audio
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction  
from PySide6.QtCore import Qt, QTimer
from theme import THEME

# Configuração do User-Agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
}

DB_NAME = "news.db"
INTERVAL = 600  # 10 minutos
ICON_PATH = "assets/icon.png"


# Criar banco de dados SQLite se não existir
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


# Buscar as últimas notícias armazenadas
def get_last_news(limit=10):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT titulo, link FROM noticias ORDER BY id DESC LIMIT ?", (limit,))
    news = cursor.fetchall()
    conn.close()
    return news


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
                title = title_tag.text.strip().encode(response.encoding, 'ignore').decode('utf-8', 'ignore')
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
            news_list.append((title, link))

    return news_list


# Salvar notícias no banco de dados e retornar novas
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


# Exibir notificações no Windows com winotify
def send_notification(news_list):
    for title, link in news_list:
        toast = Notification(
            app_id="News Crawler",
            title="📰 Nova Notícia!",
            msg=title,
            duration="long"
        )
        toast.set_audio(audio.Default, loop=False)
        toast.add_actions(label="Ler notícia", launch=link)  # Link clicável
        toast.show()
        print(f"Notificação enviada: {title}")


# Função principal para buscar notícias e atualizar o banco de dados
def news_crawler():
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


# Interface gráfica com PySide6
class NewsApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Últimas Notícias")
        self.setGeometry(100, 100, 500, 400)
        self.setWindowIcon(QIcon(ICON_PATH))
        self.initUI()
        self.initTray()


        # Iniciar o timer para buscar notícias periodicamente
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_news)
        self.timer.start(INTERVAL * 1000)  # Executa a cada INTERVAL (10 minutos)

    def initUI(self):
        layout = QVBoxLayout()

        # Scroll area para suportar múltiplas notícias
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)

        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)

        self.setLayout(layout)
        self.update_news()  # Preencher notícias ao iniciar

    def update_news(self):
        print("Atualizando interface com novas notícias...")
        news = get_last_news()

        for i in reversed(range(self.content_layout.count())):
            self.content_layout.itemAt(i).widget().deleteLater()  # Limpa a interface

        if news:
            for title, link in news:
                frame = QFrame()
                frame_layout = QVBoxLayout(frame)

                title_label = QLabel(title)
                title_label.setWordWrap(True)
                title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

                link_button = QPushButton("Ler notícia")
                link_button.setStyleSheet("""
                                            QPushButton {
                                                background-color: #24273a; 
                                                color: white; 
                                                padding: 5px; 
                                                border-radius: 4px;
                                            }
                                            QPushButton:hover {
                                                background-color: #363a4f;
                                            }
                                            QPushButton:pressed {
                                                background-color: #1e2030;
                                            }
                                        """)
                link_button.clicked.connect(lambda _, url=link: webbrowser.open(url))

                frame_layout.addWidget(title_label)
                frame_layout.addWidget(link_button)
                frame.setLayout(frame_layout)
                frame.setStyleSheet("border: 1px solid #1e2030; padding: 10px; margin-bottom: 5px;")

                self.content_layout.addWidget(frame)
        else:
            no_news_label = QLabel("Nenhuma notícia disponível.")
            no_news_label.setAlignment(Qt.AlignCenter)
            self.content_layout.addWidget(no_news_label)

    def initTray(self):
        self.tray_icon = QSystemTrayIcon(QIcon(ICON_PATH), self)
        menu = QMenu()

        show_action = QAction("Abrir", self)
        show_action.triggered.connect(self.show)
        menu.addAction(show_action)

        exit_action = QAction("Sair", self)
        exit_action.triggered.connect(sys.exit)
        menu.addAction(exit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage("News Crawler", "O aplicativo foi minimizado para a bandeja.", QSystemTrayIcon.Information)


create_database()
news_crawler()

# Inicia o aplicativo
if __name__ == "__main__":
    threading.Thread(target=news_crawler, daemon=True).start()
    app = QApplication(sys.argv)
    app.setStyleSheet(THEME)
    window = NewsApp()
    window.show()
    sys.exit(app.exec())
