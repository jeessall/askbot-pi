# IMPORTAÇÕES
import os
import google.generativeai as genai
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import sqlite3
from rich import print

# FUNÇÕES DO BANCO DE DADOS
DB_FILE = 'duvidas_jp.db'  # Nome do nosso arquivo de banco de dados

def inicializar_banco():
    """Cria o banco de dados e a tabela 'duvidas' se eles não existirem."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Cria a tabela com colunas para id, pergunta e resposta
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS duvidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta TEXT NOT NULL,
            resposta TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def carregar_duvidas_do_banco():
    """Lê todas as dúvidas do banco de dados e retorna como uma lista de dicionários."""
    conn = sqlite3.connect(DB_FILE)
    # Retorna os resultados como dicionários para manter a compatibilidade com o resto do código
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT pergunta, resposta FROM duvidas")
    duvidas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return duvidas

# FUNÇÃO DE WEB SCRAPING
def raspar_e_salvar_no_banco(api_key):
    """
    Função que faz o scraping e salva os resultados DIRETAMENTE no banco de dados SQLite.
    """
    url_alvo = "https://www.jovemprogramador.com.br/duvidas.php"
    url_api = f"http://api.scraperapi.com?api_key={api_key}&url={url_alvo}&render=true"

    print("[cyan]Iniciando scraping do site Jovem Programador...[/cyan]")

    try:
        resposta = requests.get(url_api, timeout=90)
        resposta.raise_for_status()
        soup = BeautifulSoup(resposta.text, 'html.parser')

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Limpa a tabela antes de inserir novos dados para evitar duplicatas
        cursor.execute("DELETE FROM duvidas")

        count = 0
        accordions = soup.find_all('div', class_='accordion')
        for accordion in accordions:
            blocos_qa = accordion.find_all('div', recursive=False)
            for bloco in blocos_qa:
                pergunta_tag = bloco.find('h4')
                resposta_tag = bloco.find('div', class_='card-body')
                if pergunta_tag and resposta_tag:
                    pergunta = pergunta_tag.get_text(strip=True)
                    resposta = ' '.join(resposta_tag.get_text(strip=True, separator=' ').split())
                    # Insere cada dúvida no banco de dados
                    cursor.execute("INSERT INTO duvidas (pergunta, resposta) VALUES (?, ?)", (pergunta, resposta))
                    count += 1

        conn.commit()
        conn.close()

        if count > 0:
            print(f"[bold green]SUCESSO![/] {count} dúvidas foram encontradas e salvas em '[bold cyan]{DB_FILE}[/bold cyan]'.")
        else:
            print("[yellow]AVISO: Nenhuma dúvida foi encontrada na página.[/yellow]")

    except requests.exceptions.RequestException as e:
        print(f"[bold red]ERRO CRÍTICO na conexão ou scraping:[/bold red] {e}")

# LÓGICA PRINCIPAL DO CHATBOT
load_dotenv()
GEMINI_API_KEY = os.getenv('GOOGLE_GEMINI_API_KEY')
SCRAPER_API_KEY = os.getenv('SCRAPER_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-latest")
my_chat = model.start_chat(history=[])

# Inicializa o banco de dados
inicializar_banco()

# Tenta carregar as dúvidas do banco. Se estiver vazio, faz o scraping.
duvidas_raspadas = carregar_duvidas_do_banco()
if not duvidas_raspadas:
    print(f"[yellow]Banco de dados '{DB_FILE}' está vazio. Executando o scraping pela primeira vez...[/yellow]")
    raspar_e_salvar_no_banco(SCRAPER_API_KEY)
    # Carrega os dados novamente após o scraping
    duvidas_raspadas = carregar_duvidas_do_banco()
else:
    print("[purple]ASKBOT:[/] [bold cyan]Inicializando chat...[/bold cyan]")

contexto_perguntas = ""
if duvidas_raspadas:
    for i, duvida in enumerate(duvidas_raspadas):
        contexto_perguntas += f"Índice {i}: {duvida['pergunta']}\n"
else:
    print(f"\n[purple]ASKBOT:[/] [yellow]AVISO: Não foi possível carregar as dúvidas do banco.[/yellow]")

traco = 60 * "-"
askbot_prefixo = "[purple]ASKBOT:[/] "

print(f"[bold green]{traco}[/bold green]")
print(f"{askbot_prefixo}Faça uma pergunta ou digite '[bold]sair[/bold]' para encerrar.")
print(f"[bold green]{traco}[/bold green]")

while True:
    print("[bold cyan]Eu:[/] ", end="")
    ask = input()

    if ask.lower() == 'sair':
        print(f"{askbot_prefixo}Finalizando chat.... Até logo! :wave:")
        break

    resposta_encontrada = False
    if duvidas_raspadas:
        prompt_para_busca = f"Analise a pergunta do usuário e compare-a com a lista de perguntas frequentes abaixo. Se a pergunta do usuário for sobre um dos tópicos da lista, responda APENAS com o número do índice correspondente. Se não tiver relação, responda APENAS com -1.\n\nLista:\n{contexto_perguntas}\nPergunta do usuário: \"{ask}\"\n\nQual o índice?"
        try:
            resposta_busca = model.generate_content(prompt_para_busca)
            indice_encontrado = int(resposta_busca.text.strip())
            if 0 <= indice_encontrado < len(duvidas_raspadas):
                print(f"\n{askbot_prefixo}", duvidas_raspadas[indice_encontrado]['resposta'])
                resposta_encontrada = True
        except (ValueError, IndexError):
            resposta_encontrada = False

    if not resposta_encontrada:
        print(f"\n{askbot_prefixo}[yellow]Não encontrei uma resposta específica. Buscando na base de conhecimento geral...[/yellow]")
        response = my_chat.send_message(ask)
        print(askbot_prefixo, response.text)

    print(f"[bold green]{traco}[/bold green]")