import os
import json
import hmac
import hashlib
import urllib.parse
from flask import Flask, request, jsonify
import requests


# ============================================================
# НАСТРОЙКИ
# ============================================================

TOKEN = os.environ["BOT_TOKEN"]

API = f"https://api.telegram.org/bot{TOKEN}"

WEB_APP_URL = "https://book-quiz.onrender.com"


app = Flask(__name__)


# ============================================================
# ОПЛАТИВШИЕ ПОЛЬЗОВАТЕЛИ
#
# Пока храним в памяти.
# Позже подключим постоянную базу.
# ============================================================

PAID_USERS = set()


# ============================================================
# TELEGRAM API
# ============================================================

def tg(method, data=None):

    try:

        response = requests.post(
            f"{API}/{method}",
            json=data or {},
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
            "Telegram API ERROR:",
            method,
            e
        )

        return {}


# ============================================================
# ПРОВЕРКА TELEGRAM WEB APP INIT DATA
# ============================================================

def validate_init_data(init_data):

    if not init_data:
        return None

    try:

        parsed = urllib.parse.parse_qs(
            init_data,
            strict_parsing=True
        )

        received_hash_list = parsed.get("hash")

        if not received_hash_list:
            return None

        received_hash = received_hash_list[0]

        data_check_items = []

        for key in sorted(parsed.keys()):

            if key == "hash":
                continue

            value = parsed[key][0]

            data_check_items.append(
                f"{key}={value}"
            )

        data_check_string = "\n".join(
            data_check_items
        )

        secret_key = hmac.new(
            b"WebAppData",
            TOKEN.encode(),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            received_hash
        ):
            print(
                "WEB APP: неправильная подпись"
            )

            return None

        user_data = parsed.get("user")

        if not user_data:
            return None

        user = json.loads(
            user_data[0]
        )

        return user

    except Exception as e:

        print(
            "INIT DATA ERROR:",
            e
        )

        return None


# ============================================================
# ГЛАВНАЯ СТРАНИЦА
# ============================================================

@app.route("/")
def home():

    try:

        with open(
            "index.html",
            "r",
            encoding="utf-8"
        ) as f:

            return f.read()

    except Exception as e:

        print(
            "INDEX ERROR:",
            e
        )

        return (
            "Ошибка загрузки приложения",
            500
        )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return "OK"


# ============================================================
# ПРОВЕРКА ДОСТУПА К ТЕСТУ
# ============================================================

@app.route(
    "/check-access",
    methods=["POST"]
)
def check_access():

    data = request.get_json(
        silent=True
    ) or {}

    init_data = data.get(
        "initData",
        ""
    )

    user = validate_init_data(
        init_data
    )

    if not user:

        return jsonify({
            "ok": False,
            "paid": False,
            "error": "invalid_init_data"
        }), 403

    user_id = user.get("id")

    if not user_id:

        return jsonify({
            "ok": False,
            "paid": False,
            "error": "user_not_found"
        }), 403

    paid = user_id in PAID_USERS

    print(
        "ACCESS CHECK:",
        user_id,
        "PAID:",
        paid
    )

    return jsonify({
        "ok": True,
        "paid": paid
    })


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():

    update = request.get_json(
        silent=True
    ) or {}

    print()
    print(
        "========== TELEGRAM UPDATE =========="
    )
    print(
        json.dumps(
            update,
            ensure_ascii=False
        )[:3000]
    )

    # ========================================================
    # PRE-CHECKOUT QUERY
    #
    # Telegram спрашивает:
    # можно ли проводить оплату?
    # ========================================================

    pre_checkout = update.get(
        "pre_checkout_query"
    )

    if pre_checkout:

        query_id = pre_checkout.get(
            "id"
        )

        payload = pre_checkout.get(
            "invoice_payload",
            ""
        )

        print(
            "PRE-CHECKOUT:",
            query_id,
            payload
        )

        tg(
            "answerPreCheckoutQuery",
            {
                "pre_checkout_query_id":
                    query_id,

                "ok": True
            }
        )

        return "ok"


    # ========================================================
    # CALLBACK BUTTON
    # ========================================================

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

        # ----------------------------------------------------
        # ПОКУПКА ТЕСТА
        # ----------------------------------------------------

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
                    "chat_id":
                        chat_id,

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


    # ========================================================
    # MESSAGE
    # ========================================================

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


    # ========================================================
    # УСПЕШНАЯ ОПЛАТА
    # ========================================================

    successful_payment = message.get(
        "successful_payment"
    )

    if successful_payment:

        telegram_user_id = chat_id

        PAID_USERS.add(
            telegram_user_id
        )

        print()
        print(
            "===================================="
        )
        print(
            "ОПЛАТА ПОЛУЧЕНА"
        )
        print(
            "USER:",
            telegram_user_id
        )
        print(
            "PAID USERS:",
            PAID_USERS
        )
        print(
            "===================================="
        )
        print()

        tg(
            "sendMessage",
            {
                "chat_id":
                    chat_id,

                "text":
                    (
                        "✅ Оплата прошла!\n\n"
                        "Доступ к тесту открыт.\n\n"
                        "Нажми кнопку ниже 👇"
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
                                                    WEB_APP_URL
                                            }
                                    }
                                ]
                            ]
                    }
            }
        )

        return "ok"


    # ========================================================
    # /START
    # ========================================================

    if message.get(
        "text"
    ) == "/start":

        # ----------------------------------------------------
        # Если пользователь уже оплатил
        # ----------------------------------------------------

        if chat_id in PAID_USERS:

            tg(
                "sendMessage",
                {
                    "chat_id":
                        chat_id,

                    "text":
                        (
                            "📚 Book Quiz\n\n"
                            "У тебя уже есть доступ к тесту."
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
                                                        WEB_APP_URL
                                                }
                                        }
                                    ]
                                ]
                        }
                }
            )

        else:

            # ------------------------------------------------
            # Новый пользователь
            # ------------------------------------------------

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
                            "12 вопросов → твой типаж → "
                            "персональная рекомендация."
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


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
