#IMPORTAÇÕES NECESSÁRIAS
import os
import google.generativeai as genai
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import sqlite3
from rich import print

#DANDO NOME AO ARQUIVO 
DB_FILE = 'duvidas_jp.db'

#FUNÇÕES DO BANCO DE DADOS
def inicializar_banco():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
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
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT pergunta, resposta FROM duvidas")
    duvidas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return duvidas

#FUNÇÃO DE WEB SCRAPING
def raspar_e_salvar_no_banco(api_key):
    url_alvo = "https://www.jovemprogramador.com.br/duvidas.php"
    url_api = f"http://api.scraperapi.com?api_key={api_key}&url={url_alvo}&render=true"
    print("[cyan]Iniciando dúvidas do site Jovem Programador...[/cyan]")
    try:
        resposta = requests.get(url_api, timeout=90)
        resposta.raise_for_status()
        soup = BeautifulSoup(resposta.text, 'html.parser')

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
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
                    cursor.execute("INSERT INTO duvidas (pergunta, resposta) VALUES (?, ?)", (pergunta, resposta))
                    count += 1
        
        conn.commit()
        conn.close()

        if count > 0:
            print(f"[bold green]SUCESSO![/] {count} dúvidas foram encontradas e salvas")
        else:
            print("[yellow]AVISO: Nenhuma dúvida foi encontrada na página.[/yellow]")

    except requests.exceptions.RequestException as e:
        print(f"[bold red]ERRO CRÍTICO na busca das dúvidas[/bold red] {e}")

#LÓGICA PRINCIPAL DO CHATBOT
load_dotenv()
GEMINI_API_KEY = os.getenv('GOOGLE_GEMINI_API_KEY')
SCRAPER_API_KEY = os.getenv('SCRAPER_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-latest")

inicializar_banco()

#VALIDANDO DUVIDAS CARREGADAS DO BANCO DE dados
duvidas_raspadas = carregar_duvidas_do_banco()
if not duvidas_raspadas:
    print(f"[yellow]Dúvidas '{DB_FILE}' está vazio. Executando a busca das dúvidas...[/yellow]")
    raspar_e_salvar_no_banco(SCRAPER_API_KEY)
    duvidas_raspadas = carregar_duvidas_do_banco()
else:
    print("[purple]ASKBOT:[/] [bold cyan]Inicializando chat...[/bold cyan]")

duvidas_disponiveis = ""
if duvidas_raspadas:
    for duvida in duvidas_raspadas:
        duvidas_disponiveis += f"PERGUNTA: {duvida['pergunta']}\nRESPOSTA: {duvida['resposta']}\n\n"
else:
    print(f"\n[purple]ASKBOT:[/] [yellow]AVISO: A base de conhecimento está vazia.[/yellow]")

traco = 80 * "-"
askbot_prefixo = "[purple]ASKBOT:[/] "

print(f"[bold green]{traco}[/bold green]")
print(f"{askbot_prefixo}Olá! Sou um assistente do Jovem Programador. Como posso ajudar?")
print(f"{askbot_prefixo}Digite '[bold]sair[/bold]' para encerrar.")
print(f"[bold green]{traco}[/bold green]")

#LOOP DE CONVERSA COM LÓGICA REFINADA
while True:
    print("[bold cyan]Usuário:[/] ", end="")
    ask = input()

    if ask.lower() == 'sair':
        print(f"{askbot_prefixo}Finalizando... Até logo! :wave:")
        break

    if not duvidas_disponiveis:
        print(f"{askbot_prefixo}Desculpe, minha base de conhecimento está indisponível no momento.")
        continue

    #PROMPT PARA IA(INSTRUÇÕES)
    prompt_especialista = f"""
    Você é o "Askbot", um assistente virtual **altamente especializado e rigoroso** no programa "Jovem Programador". Sua principal função é fornecer respostas precisas e confiáveis, **construindo-as *exclusivamente* a partir do conteúdo presente nas "INFORMAÇÕES DISPONÍVEIS"**. Não utilize nenhum conhecimento prévio, externo ou inferências que não possam ser diretamente suportadas pelo texto fornecido.

    Diretrizes para Responder:

    1.  **Resposta Direta:** Se a resposta exata para a "PERGUNTA DO USUÁRIO" estiver claramente explicitada nas "INFORMAÇÕES DISPONÍVEIS", forneça essa resposta de forma concisa.
    2.  **Informação Relacionada/Próxima e Formulação:** Se a resposta exata NÃO for encontrada, mas houver informações **diretamente relacionadas ou complementares** nas "INFORMAÇÕES DISPONÍVEIS" que ajudem a esclarecer a pergunta, você DEVE utilizá-las para formular uma resposta útil e coerente. **Nesse caso, é permitido e esperado que você indique a ausência de uma informação específica se apenas a informação complementar for fornecida, especialmente em cenários de limites ou máximos.**
        * **Cenário Específico (Idade Máxima/Limite Superior):** Se a "PERGUNTA DO USUÁRIO" for sobre a idade máxima, um limite de idade superior, ou envolver uma idade específica para verificar elegibilidade (como "tenho 26 posso participar?", "qual a idade limite?"), e as "INFORMAÇÕES DISPONÍVEIS" contiverem apenas a idade mínima, sua resposta OBRIGATÓRIA deve ser: "**Não há idade máxima definida para participar do Jovem Programador, todos com a idade mínima de 16 anos ou maior podem participar do programa.**" 
        * **Exemplo PRÁTICO (Outro Tema - se aplicável):** Se o usuário perguntar "qual o valor da mensalidade?" e as "INFORMAÇÕES DISPONÍVEIS" contiverem "O programa Jovem Programador é totalmente gratuito e não há cobrança de taxas.", sua resposta OBRIGATÓRIA deve ser: "**O programa Jovem Programador é gratuito e não possui mensalidade.**"
    3.  **Ausência Completa de Informação:** Se, mesmo buscando por informações relacionadas ou complementares, você não encontrar **nada relevante** nas "INFORMAÇÕES DISPONÍVEIS" para a "PERGUNTA DO USUÁRIO", responda de forma educada, informando que você **não possui essa irformação de forma educada**. Em seguida, oriente o usuário a fazer uma pergunta sobre o programa jovem programador.

    ---

    INFORMAÇÕES DISPONÍVEIS:
    {duvidas_disponiveis}

    ---

    PERGUNTA DO USUÁRIO:
    "{ask}"

    ---

    Sua resposta (comece diretamente com a resposta, sem saudações adicionais ou introduções de "O Askbot diz:", etc.):
    """

    print(f"\n{askbot_prefixo}[yellow]Buscando resposta...[/yellow]")
    response = model.generate_content(prompt_especialista)
    print(f"{askbot_prefixo}", response.text)

    print(f"[bold green]{traco}[/bold green]")