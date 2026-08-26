import os
import requests
from flask import Flask, request

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

@app.route("/")
def home():
    return "Book Quiz Bot is running"

@app.route("/health")
def health():
    return "OK"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.json or {}
    message = update.get("message")

    if not message:
        return "ok"

    chat_id = message["chat"]["id"]

    if message.get("text") == "/start":
        requests.post(
            f"{API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "📚 Book Quiz\n\nПройди тест и узнай, какая книга подходит именно тебе.",
                "reply_markup": {
                    "inline_keyboard": [[
                        {
                            "text": "🔓 Купить тест — 500 ⭐",
                            "callback_data": "buy_test"
                        }
                    ]]
                }
            }
        )

    return "ok"

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
