# IMPORTAÇÕES NECESSÁRIAS
import os
import sqlite3
from rich import print
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup

# SDK DO GEMINI
import google.generativeai as genai

# --- CONFIGURAÇÃO DO FLASK ---
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# --- CONFIGURAÇÃO DO BANCO ---
DB_FILE = "duvidas_jp.db"


def inicializar_banco():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS duvidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta TEXT NOT NULL,
            resposta TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def carregar_duvidas_do_banco():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT pergunta, resposta FROM duvidas")
    duvidas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return duvidas


# --- SCRAPING ---
def raspar_e_salvar_no_banco(api_key):
    url_alvo = "https://www.jovemprogramador.com.br/duvidas.php"
    url_api = f"http://api.scraperapi.com?api_key={api_key}&url={url_alvo}&render=true"

    print("[cyan]Buscando dúvidas no site oficial do Jovem Programador...[/cyan]")

    try:
        resposta = requests.get(url_api, timeout=90)
        resposta.raise_for_status()
        soup = BeautifulSoup(resposta.text, "html.parser")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM duvidas")

        count = 0

        accordions = soup.find_all("div", class_="accordion")
        for accordion in accordions:
            blocos = accordion.find_all("div", recursive=False)
            for bloco in blocos:
                pergunta_tag = bloco.find("h4")
                resposta_tag = bloco.find("div", class_="card-body")
                if pergunta_tag and resposta_tag:
                    pergunta = pergunta_tag.get_text(strip=True)
                    resposta = " ".join(
                        resposta_tag.get_text(strip=True, separator=" ").split()
                    )
                    cursor.execute(
                        "INSERT INTO duvidas (pergunta, resposta) VALUES (?, ?)",
                        (pergunta, resposta),
                    )
                    count += 1

        conn.commit()
        conn.close()

        if count > 0:
            print(f"[bold green]Sucesso! {count} dúvidas foram salvas no banco.[/bold green]")
        else:
            print("[yellow]Aviso: nenhuma dúvida encontrada.[/yellow]")

    except Exception as e:
        print(f"[bold red]Erro ao raspar o site:[/bold red] {e}")
        return False

    return True


# --- CONFIG GEMINI ---
load_dotenv()

API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

if not API_KEY:
    print("[bold red]ERRO: Nenhuma chave de API encontrada![/bold red]")

genai.configure(api_key=API_KEY)

MODEL_NAME = "gemini-2.5-flash"

# --- INICIALIZA BANCO ---
inicializar_banco()
DUVIDAS_DB = carregar_duvidas_do_banco()

if not DUVIDAS_DB:
    print("[yellow]Banco vazio, iniciando scraping...[/yellow]")
    if SCRAPER_API_KEY:
        if raspar_e_salvar_no_banco(SCRAPER_API_KEY):
            DUVIDAS_DB = carregar_duvidas_do_banco()

DUVIDAS_DISPONIVEIS = ""
for item in DUVIDAS_DB:
    DUVIDAS_DISPONIVEIS += (
        f"PERGUNTA: {item['pergunta']}\nRESPOSTA: {item['resposta']}\n\n"
    )


# --- HOME SERVE O SITE ---
@app.route("/")
def home_page():
    return render_template("index.html")


# --- ROTA DO CHATBOT ---
@app.route("/ask", methods=["POST"])
def ask_chatbot():
    data = request.get_json() or {}
    pergunta = (data.get("question") or "").strip()

    if not pergunta:
        return jsonify({"answer": "Por favor, digite sua pergunta."}), 400

    prompt = f"""
    Você é o ASKBot, assistente virtual oficial do programa "Jovem Programador".
    Utilize APENAS as informações abaixo.

    {DUVIDAS_DISPONIVEIS}

    Pergunta: {pergunta}
    """

    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        answer = response.text.strip()

        return jsonify({"answer": answer})

    except Exception as e:
        print("[bold red]ERRO GEMINI:[/bold red]", e)
        return jsonify({"answer": "Erro ao processar sua pergunta."}), 500


# --- EXECUÇÃO LOCAL ---
if __name__ == "__main__":
    print("[cyan]Rodando AskBot na porta 5000...[/cyan]")
    app.run(host="0.0.0.0", port=5000)
