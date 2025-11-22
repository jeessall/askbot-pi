# IMPORTAÇÕES NECESSÁRIAS
import os
import sqlite3
from rich import print
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup

# SDK NOVO DO GEMINI
import google.generativeai as genai

# --- CONFIGURAÇÃO DO FLASK ---
app = Flask(__name__)
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
            print(
                f"[bold green]Sucesso! {count} dúvidas foram salvas no banco.[/bold green]"
            )
        else:
            print("[yellow]Aviso: nenhuma dúvida foi encontrada na página.[/yellow]")

    except Exception as e:
        print(f"[bold red]Erro ao raspar o site:[/bold red] {e}")
        return False

    return True


# --- CONFIG GERAL / GEMINI ---
load_dotenv()

API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

if not API_KEY:
    print(
        "[bold red]ERRO: Nenhuma chave de API do Gemini encontrada. "
        "Defina GOOGLE_GEMINI_API_KEY ou GEMINI_API_KEY no .env[/bold red]"
    )

genai.configure(api_key=API_KEY)

# modelo moderno e compatível
MODEL_NAME = "gemini-1.5-flash"
model = genai.GenerativeModel(MODEL_NAME)

# --- INICIALIZAÇÃO DO BANCO E BASE DE CONHECIMENTO ---
inicializar_banco()

DUVIDAS_DB = carregar_duvidas_do_banco()

if not DUVIDAS_DB:
    print("[yellow]Base de dúvidas vazia. Iniciando scraping...[/yellow]")
    if SCRAPER_API_KEY:
        ok = raspar_e_salvar_no_banco(SCRAPER_API_KEY)
        if ok:
            DUVIDAS_DB = carregar_duvidas_do_banco()
        else:
            print("[red]Falha ao atualizar a base via scraping.[/red]")
    else:
        print(
            "[yellow]SCRAPER_API_KEY não definida. Não é possível raspar o site agora.[/yellow]"
        )

# monta texto plano com as dúvidas
DUVIDAS_DISPONIVEIS = ""
if DUVIDAS_DB:
    for item in DUVIDAS_DB:
        DUVIDAS_DISPONIVEIS += (
            f"PERGUNTA: {item['pergunta']}\nRESPOSTA: {item['resposta']}\n\n"
        )
else:
    print(
        "[purple]ASKBOT:[/] [yellow]Aviso: a base de conhecimento está vazia. "
        "O bot poderá responder apenas de forma limitada.[/yellow]"
    )


# --- ROTA PRINCIPAL DO CHAT ---
@app.route("/ask", methods=["POST"])
def ask_chatbot():
    data = request.get_json() or {}
    pergunta = (data.get("question") or "").strip()

    if not pergunta:
        return jsonify({"answer": "Por favor, digite sua pergunta."}), 400

    if not DUVIDAS_DISPONIVEIS:
        return (
            jsonify(
                {
                    "answer": (
                        "No momento minha base de conhecimento está indisponível. "
                        "Tente novamente mais tarde ou consulte diretamente o site oficial "
                        "do programa Jovem Programador."
                    )
                }
            ),
            503,
        )

    # 🔥 SEU PROMPT 100% ORIGINAL (NÃO ALTEREI NADA)
    prompt = f"""
    Você é o ASKBot, assistente virtual oficial e altamente especializado no programa "Jovem Programador".

    Sua função é responder exclusivamente com base nas informações abaixo,
    sem inventar dados e sem usar conhecimento externo que não esteja explícito
    neste texto.

    REGRAS ESPECIAIS QUE VOCÊ DEVE SEGUIR:
    - Se a pergunta envolver idade máxima, limite de idade ou dúvidas como
      "tenho 26, posso participar?", responda literalmente:
      "Não há idade máxima definida para participar do Jovem Programador, todos com a idade mínima de 16 anos ou maior podem participar do programa."
    - Se a pergunta for sobre valor, mensalidade ou se o curso é pago,
      e as informações indicarem que é gratuito, responda algo como:
      "O programa Jovem Programador é gratuito e não possui mensalidade."
    - Se a pergunta não estiver coberta de forma alguma pelas informações abaixo,
      diga que não possui essa informação e sugira que a pessoa consulte o site
      ou faça outra pergunta sobre o programa.

    BASE DE CONHECIMENTO (dúvidas oficiais raspadas do site):
    {DUVIDAS_DISPONIVEIS}

    PERGUNTA DO USUÁRIO:
    "{pergunta}"

    Responda de forma direta, clara e educada, em português do Brasil.
    Não repita o enunciado "PERGUNTA DO USUÁRIO" na resposta.
    """

    try:
        # 🔥 CHAMADA CORRETA PARA O GEMINI NOVO
        response = model.generate_content(prompt)

        answer = (response.text or "").strip()
        if not answer:
            answer = (
                "Não consegui gerar uma resposta no momento. "
                "Tente reformular a pergunta ou tentar novamente daqui a pouco."
            )

        return jsonify({"answer": answer})

    except Exception as e:
        print(f"[bold red]ERRO API GEMINI:[/bold red] {e}")
        return jsonify({"answer": "Erro ao consultar a inteligência artificial."}), 500


# --- EXECUÇÃO ---
if __name__ == "__main__":
    print("[cyan]ASKBOT: Servidor Flask rodando na porta 5000...[/cyan]")
    app.run(host="0.0.0.0", port=5000, debug=True)
