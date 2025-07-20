# main.py
from fastapi import FastAPI, Request
import telebot
import requests
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = FastAPI()

def ask_chatgpt(message):
    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": message}
        ]
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    result = response.json()
    return result["choices"][0]["message"]["content"]

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    try:
        reply = ask_chatgpt(message.text)
        bot.reply_to(message, reply)
    except Exception as e:
        bot.reply_to(message, "حصل خطأ، جرّب تاني")

@app.post("/")
async def webhook(req: Request):
    json_data = await req.json()
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "ok"

@app.get("/")
def root():
    return {"status": "ok"}
