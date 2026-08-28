import os
import json
import requests

from flask import Flask, request, send_file

TOKEN = os.environ["BOT_TOKEN"]

API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

# Пользователи, которые оплатили тест
PAID_USERS_FILE = "paid_users.json"


def load_paid_users():
    try:
        if not os.path.exists(PAID_USERS_FILE):
            return set()

        with open(PAID_USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return set(str(x) for x in data)

    except Exception:
        return set()


def save_paid_users(users):
    with open(
        PAID_USERS_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            list(users),
            f,
            ensure_ascii=False,
            indent=2
        )


PAID_USERS = load_paid_users()


def tg(method, data):
    try:
        response = requests.post(
            f"{API}/{method}",
            json=data,
            timeout=20
        )

        print(
            "Telegram:",
            method,
            response.status_code,
            response.text[:500]
        )

        return response.json()

    except Exception as e:

        print(
            "Telegram ERROR:",
            method,
            e
        )

        return {}


@app.route("/")
def home():

    return send_file(
        "index.html"
    )


@app.route("/health")
def health():

    return "OK"


@app.route("/check-access")
def check_access():

    user_id = request.args.get(
        "user_id",
        ""
    )

    if not user_id:
        return {
            "paid": False
        }

    paid = str(user_id) in PAID_USERS

    return {
        "paid": paid
    }


@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():

    update = request.json or {}

    print(
        "UPDATE:",
        json.dumps(
            update,
            ensure_ascii=False
        )[:2000]
    )

    # ==========================================================
    # CALLBACK
    # ==========================================================

    callback = update.get(
        "callback_query"
    )

    if callback:

        callback_id = callback.get(
            "id"
        )

        message = callback.get(
            "message",
            {}
        )

        chat = message.get(
            "chat",
            {}
        )

        chat_id = chat.get(
            "id"
        )

        data = callback.get(
            "data"
        )

        # ------------------------------------------------------
        # КНОПКА ПОКУПКИ
        # ------------------------------------------------------

        if data == "buy_test":

            tg(
                "answerCallbackQuery",
                {
                    "callback_query_id":
                        callback_id
                }
            )

            tg(
                "sendInvoice",
                {
                    "chat_id": chat_id,

                    "title":
                        "Book Quiz",

                    "description":
                        "Одно прохождение теста «Какая книга тебя ждёт?»",

                    "payload":
                        f"book_quiz_{chat_id}",

                    "currency":
                        "XTR",

                    "prices":
                        [
                            {
                                "label":
                                    "Прохождение теста",

                                "amount":
                                    200
                            }
                        ]
                }
            )

            return "ok"

        return "ok"

    # ==========================================================
    # MESSAGE
    # ==========================================================

    message = update.get(
        "message"
    )

    if not message:

        return "ok"

    chat_id = message.get(
        "chat",
        {}
    ).get(
        "id"
    )

    # ==========================================================
    # PRE-CHECKOUT
    # ==========================================================

    pre_checkout = update.get(
        "pre_checkout_query"
    )

    if pre_checkout:

        pre_checkout_id = pre_checkout.get(
            "id"
        )

        tg(
            "answerPreCheckoutQuery",
            {
                "pre_checkout_query_id":
                    pre_checkout_id,

                "ok":
                    True
            }
        )

        return "ok"

    # ==========================================================
    # УСПЕШНАЯ ОПЛАТА
    # ==========================================================

    successful_payment = message.get(
        "successful_payment"
    )

    if successful_payment:

        user_id = str(
            chat_id
        )

        PAID_USERS.add(
            user_id
        )

        save_paid_users(
            PAID_USERS
        )

        print(
            "ОПЛАТА ПОЛУЧЕНА:",
            user_id
        )

        tg(
            "sendMessage",
            {
                "chat_id":
                    chat_id,

                "text":
                    (
                        "✅ Оплата прошла!\n\n"
                        "Тест разблокирован.\n\n"
                        "Теперь можешь пройти его 👇"
                    ),

                "reply_markup":
                    {
                        "inline_keyboard":
                            [
                                [
                                    {
                                        "text":
                                            "📚 Пройти тест",

                                        "web_app":
                                            {
                                                "url":
                                                    "https://book-quiz.onrender.com"
                                            }
                                    }
                                ]
                            ]
                    }
            }
        )

        return "ok"

    # ==========================================================
    # START
    # ==========================================================

    if message.get(
        "text"
    ) == "/start":

        user_id = str(
            chat_id
        )

        # ------------------------------------------------------
        # ЕСЛИ УЖЕ ОПЛАЧЕНО
        # ------------------------------------------------------

        if user_id in PAID_USERS:

            tg(
                "sendMessage",
                {
                    "chat_id":
                        chat_id,

                    "text":
                        (
                            "📚 Book Quiz\n\n"
                            "Тест уже разблокирован."
                        ),

                    "reply_markup":
                        {
                            "inline_keyboard":
                                [
                                    [
                                        {
                                            "text":
                                                "📚 Пройти тест",

                                            "web_app":
                                                {
                                                    "url":
                                                        "https://book-quiz.onrender.com"
                                                }
                                        }
                                    ]
                                ]
                        }
                }
            )

            return "ok"

        # ------------------------------------------------------
        # ЕСЛИ НЕ ОПЛАЧЕНО
        # ------------------------------------------------------

        tg(
            "sendMessage",
            {
                "chat_id":
                    chat_id,

                "text":
                    (
                        "📚 Book Quiz\n\n"
                        "Пройди тест и узнай, "
                        "какая книга подходит именно тебе.\n\n"
                        "🔓 Стоимость прохождения — 200 ⭐"
                    ),

                "reply_markup":
                    {
                        "inline_keyboard":
                            [
                                [
                                    {
                                        "text":
                                            "🔓 Купить тест — 200 ⭐",

                                        "callback_data":
                                            "buy_test"
                                    }
                                ]
                            ]
                    }
            }
        )

    return "ok"


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                10000
            )
        )
    )
