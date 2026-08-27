import os
import requests
from flask import Flask, request

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)


def tg(method, data):
    return requests.post(
        f"{API}/{method}",
        json=data,
        timeout=20
    )


@app.route("/")
def home():
    with open("index.html", encoding="utf-8") as f:
        return f.read()


@app.route("/health")
def health():
    return "OK"


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.json or {}

    callback = update.get("callback_query")

    if callback:
        callback_id = callback["id"]
        chat_id = callback["message"]["chat"]["id"]
        data = callback.get("data")

        if data == "buy_test":
            tg("answerCallbackQuery", {
                "callback_query_id": callback_id
            })

            tg("sendInvoice", {
                "chat_id": chat_id,
                "title": "Book Quiz",
                "description": "Одно прохождение теста «Какая книга тебя ждёт?»",
                "payload": f"book_quiz_{chat_id}",
                "currency": "XTR",
                "prices": [
                    {
                        "label": "Прохождение теста",
                        "amount": 200
                    }
                ]
            })

        return "ok"

    message = update.get("message")

    if not message:
        return "ok"

    chat_id = message["chat"]["id"]

    if message.get("successful_payment"):
        tg("sendMessage", {
            "chat_id": chat_id,
            "text": (
                "✅ Оплата прошла!\n\n"
                "Тест разблокирован."
            ),
            "reply_markup": {
                "inline_keyboard": [[
                    {
                        "text": "📚 Пройти тест",
                        "web_app": {
                            "url": "https://book-quiz.onrender.com"
                        }
                    }
                ]]
            }
        })

        return "ok"

    if message.get("text") == "/start":
        tg("sendMessage", {
            "chat_id": chat_id,
            "text": (
                "📚 Book Quiz\n\n"
                "Пройди тест и узнай, какая книга подходит именно тебе."
            ),
            "reply_markup": {
                "inline_keyboard": [[
                    {
                        "text": "🔓 Купить тест — 200 ⭐",
                        "callback_data": "buy_test"
                    }
                ]]
            }
        })

    return "ok"


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
