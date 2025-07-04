import google.generativeai as genai 
import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY=os.getenv('GOOGLE_GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

#for model in genai.list_models():
    #if 'generateContent' in model.supported_generation_methods:
        #print(model.name)

model = genai.GenerativeModel("gemini-1.5-flash-latest")

my_chat = model.start_chat(history=[])

ask = input("Faça uma pergunta: ")

while ask != "sair":
    response = my_chat.send_message(ask)
    print(response.text)
    ask = input("Faça uma pergunta: ")
