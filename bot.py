import os
import json
import sqlite3
import logging

from flask import Flask, jsonify, request
import requests


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

log = logging.getLogger(__name__)


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEB_APP_URL = os.getenv("WEB_APP_URL", "").strip()

TEST_MODE = (
    os.getenv("TEST_MODE", "false")
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)

PORT = int(os.getenv("PORT", "10000"))

DB_PATH = os.getenv("DB_PATH", "quiz.db")

PRICE_STARS = 200

# Render автоматически предоставляет адрес сервиса.
RENDER_EXTERNAL_URL = os.getenv(
    "RENDER_EXTERNAL_URL",
    "https://book-quiz.onrender.com"
).strip().rstrip("/")

WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/telegram-webhook"


# =========================================================
# VALIDATION
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is not set in Render Environment Variables"
    )

if not WEB_APP_URL:
    raise RuntimeError(
        "WEB_APP_URL is not set in Render Environment Variables"
    )

if not WEB_APP_URL.startswith("https://"):
    raise RuntimeError(
        "WEB_APP_URL must start with https://"
    )

if " " in WEB_APP_URL:
    raise RuntimeError(
        "WEB_APP_URL contains spaces"
    )


# =========================================================
# TELEGRAM API
# =========================================================

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():
    conn = db()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            paid INTEGER NOT NULL DEFAULT 0,
            result_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()

    log.info("Database initialized")


# =========================================================
# SAVE USER
# =========================================================

def save_user(user):
    if not user:
        return

    if "id" not in user:
        return

    conn = db()

    conn.execute(
        """
        INSERT INTO users (
            user_id,
            username,
            first_name
        )
        VALUES (?, ?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            str(user["id"]),
            user.get("username", ""),
            user.get("first_name", "")
        )
    )

    conn.commit()
    conn.close()


# =========================================================
# SET PAYMENT STATUS
# =========================================================

def set_paid(user_id, paid=True):
    conn = db()

    conn.execute(
        """
        INSERT INTO users (
            user_id,
            paid,
            updated_at
        )
        VALUES (?, ?, CURRENT_TIMESTAMP)

        ON CONFLICT(user_id)
        DO UPDATE SET
            paid = excluded.paid,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            str(user_id),
            1 if paid else 0
        )
    )

    conn.commit()
    conn.close()


# =========================================================
# CHECK PAYMENT
# =========================================================

def is_paid(user_id):

    if TEST_MODE:
        return True

    conn = db()

    row = conn.execute(
        """
        SELECT paid
        FROM users
        WHERE user_id = ?
        """,
        (str(user_id),)
    ).fetchone()

    conn.close()

    if not row:
        return False

    return row["paid"] == 1


# =========================================================
# SAVE QUIZ RESULT
# =========================================================

def save_result(user_id, result):
    conn = db()

    conn.execute(
        """
        INSERT INTO users (
            user_id,
            result_json,
            updated_at
        )
        VALUES (?, ?, CURRENT_TIMESTAMP)

        ON CONFLICT(user_id)
        DO UPDATE SET
            result_json = excluded.result_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            str(user_id),
            json.dumps(
                result,
                ensure_ascii=False
            )
        )
    )

    conn.commit()
    conn.close()


# =========================================================
# TELEGRAM REQUEST
# =========================================================

def tg(method, payload=None):
    url = f"{API}/{method}"

    response = requests.post(
        url,
        json=payload or {},
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {data}"
        )

    return data


# =========================================================
# TELEGRAM WEBHOOK SETUP
# =========================================================

def setup_webhook():
    try:
        log.info(
            "Setting Telegram webhook: %s",
            WEBHOOK_URL
        )

        # Сначала удаляем старый webhook.
        tg(
            "deleteWebhook",
            {
                "drop_pending_updates": False
            }
        )

        # Затем устанавливаем новый.
        result = tg(
            "setWebhook",
            {
                "url": WEBHOOK_URL,
                "drop_pending_updates": False
            }
        )

        log.info(
            "Telegram webhook configured: %s",
            result
        )

        info = tg("getWebhookInfo")

        webhook_info = info.get(
            "result",
            {}
        )

        log.info(
            "Telegram webhook info: %s",
            webhook_info
        )

    except Exception:
        log.exception(
            "Could not configure Telegram webhook"
        )


# =========================================================
# MAIN KEYBOARD
# =========================================================

def start_keyboard():
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🎲 Пройти тест",
                    "web_app": {
                        "url": WEB_APP_URL
                    }
                }
            ],
            [
                {
                    "text": f"⭐ Оплатить {PRICE_STARS} Stars",
                    "callback_data": "pay_quiz"
                }
            ]
        ]
    }


# =========================================================
# START MESSAGE
# =========================================================

def send_start(chat_id):

    text = (
        "📚 <b>Какая книга тебя ждёт?</b>\n\n"
        "12 вопросов → твой типаж → "
        "персональная рекомендация книги.\n\n"
    )

    if TEST_MODE:
        text += (
            "🧪 <b>ТЕСТОВЫЙ РЕЖИМ</b>\n"
            "Оплата отключена для тестирования.\n"
            "Доступ к тесту открыт.\n\n"
        )
    else:
        text += (
            f"Стоимость прохождения — "
            f"<b>{PRICE_STARS} ⭐</b>.\n\n"
        )

    text += "Нажми кнопку ниже."

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": start_keyboard()
        }
    )


# =========================================================
# SEND INVOICE
# =========================================================

def send_invoice(chat_id):

    if TEST_MODE:

        set_paid(
            chat_id,
            True
        )

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🧪 <b>Тестовый режим</b>\n\n"
                    "Доступ открыт без оплаты.\n"
                    "Нажми «🎲 Пройти тест»."
                ),
                "parse_mode": "HTML",
                "reply_markup": start_keyboard()
            }
        )

        return

    payload = f"quiz_access:{chat_id}"

    tg(
        "sendInvoice",
        {
            "chat_id": chat_id,
            "title": "Прохождение теста",
            "description": (
                "12 вопросов и "
                "персональная рекомендация книги."
            ),
            "payload": payload,
            "currency": "XTR",
            "prices": [
                {
                    "label": "Прохождение теста",
                    "amount": PRICE_STARS
                }
            ],
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": (
                                f"⭐ Оплатить "
                                f"{PRICE_STARS}"
                            ),
                            "pay": True
                        }
                    ]
                ]
            }
        }
    )


# =========================================================
# ANSWER CALLBACK
# =========================================================

def answer_callback(
    callback_id,
    text=""
):
    try:
        tg(
            "answerCallbackQuery",
            {
                "callback_query_id": callback_id,
                "text": text
            }
        )

    except Exception:
        log.exception(
            "answerCallbackQuery failed"
        )


# =========================================================
# HANDLE MESSAGE
# =========================================================

def handle_message(message):

    user = message.get(
        "from"
    )

    if user:
        save_user(user)

    chat_id = message.get(
        "chat",
        {}
    ).get(
        "id"
    )

    if not chat_id:
        return


    # -----------------------------------------------------
    # SUCCESSFUL PAYMENT
    # -----------------------------------------------------

    successful_payment = message.get(
        "successful_payment"
    )

    if successful_payment:

        if user:
            set_paid(
                user["id"],
                True
            )

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "✅ <b>Оплата прошла!</b>\n\n"
                    "Доступ к тесту открыт.\n\n"
                    "Нажми «🎲 Пройти тест»."
                ),
                "parse_mode": "HTML",
                "reply_markup": start_keyboard()
            }
        )

        log.info(
            "Payment received: user=%s payload=%s",
            user.get("id") if user else None,
            successful_payment.get(
                "invoice_payload"
            )
        )

        return


    # -----------------------------------------------------
    # WEB APP RESULT
    # -----------------------------------------------------

    web_app_data = message.get(
        "web_app_data"
    )

    if web_app_data:

        if not user:
            return

        user_id = user["id"]

        # В боевом режиме результат принимаем
        # только от пользователя с доступом.
        if not is_paid(user_id):
            tg(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": (
                        "🔒 <b>Доступ закрыт.</b>\n\n"
                        "Сначала необходимо оплатить "
                        "прохождение теста."
                    ),
                    "parse_mode": "HTML"
                }
            )
            return

        raw_data = web_app_data.get(
            "data",
            "{}"
        )

        try:
            result = json.loads(
                raw_data
            )

        except json.JSONDecodeError:
            result = {
                "raw": raw_data
            }

        save_result(
            user_id,
            result
        )

        archetype = result.get(
            "archetype",
            "не определён"
        )

        book = result.get(
            "book",
            "не определена"
        )

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🎉 <b>Результат получен!</b>\n\n"
                    f"Твой типаж: "
                    f"<b>{archetype}</b>\n\n"
                    f"📕 Книга: "
                    f"<b>{book}</b>"
                ),
                "parse_mode": "HTML"
            }
        )

        log.info(
            "Quiz result received: user=%s",
            user_id
        )

        return


    # -----------------------------------------------------
    # TEXT COMMANDS
    # -----------------------------------------------------

    text = message.get(
        "text",
        ""
    ).strip()

    if text.startswith("/start"):

        send_start(
            chat_id
        )

        return


    if text.startswith("/help"):

        send_start(
            chat_id
        )

        return


    # -----------------------------------------------------
    # TEST COMMAND
    # -----------------------------------------------------

    if text == "/test":

        if not TEST_MODE:

            tg(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": (
                        "❌ Тестовый режим отключён."
                    )
                }
            )

            return

        if user:

            set_paid(
                user["id"],
                True
            )

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🧪 <b>Тестовый доступ включён.</b>\n\n"
                    "Нажми «🎲 Пройти тест»."
                ),
                "parse_mode": "HTML",
                "reply_markup": start_keyboard()
            }
        )

        return


# =========================================================
# HANDLE UPDATE
# =========================================================

def handle_update(update):

    try:

        # -------------------------------------------------
        # PRE-CHECKOUT
        # -------------------------------------------------

        pre_checkout = update.get(
            "pre_checkout_query"
        )

        if pre_checkout:

            payload = pre_checkout.get(
                "invoice_payload",
                ""
            )

            if payload.startswith(
                "quiz_access:"
            ):

                tg(
                    "answerPreCheckoutQuery",
                    {
                        "pre_checkout_query_id":
                            pre_checkout["id"],
                        "ok": True
                    }
                )

            else:

                tg(
                    "answerPreCheckoutQuery",
                    {
                        "pre_checkout_query_id":
                            pre_checkout["id"],
                        "ok": False,
                        "error_message":
                            "Неизвестный платёж."
                    }
                )

            return


        # -------------------------------------------------
        # MESSAGE
        # -------------------------------------------------

        message = update.get(
            "message"
        )

        if message:
            handle_message(
                message
            )
            return


        # -------------------------------------------------
        # CALLBACK QUERY
        # -------------------------------------------------

        callback = update.get(
            "callback_query"
        )

        if callback:

            user = callback.get(
                "from"
            )

            if user:
                save_user(user)

            data = callback.get(
                "data",
                ""
            )

            if data == "pay_quiz":

                answer_callback(
                    callback["id"]
                )

                callback_message = callback.get(
                    "message",
                    {}
                )

                chat = callback_message.get(
                    "chat",
                    {}
                )

                chat_id = chat.get(
                    "id"
                )

                if chat_id:
                    send_invoice(
                        chat_id
                    )

                return

    except Exception:
        log.exception(
            "Error while handling Telegram update"
        )


# =========================================================
# TELEGRAM WEBHOOK
# =========================================================

@app.post("/telegram-webhook")
def telegram_webhook():

    update = request.get_json(
        silent=True
    )

    if not update:
        return jsonify(
            {
                "ok": False,
                "error": "empty_update"
            }
        ), 400

    log.info(
        "Telegram update received: %s",
        update.get("update_id")
    )

    handle_update(
        update
    )

    return jsonify(
        {
            "ok": True
        }
    )


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return jsonify(
        {
            "ok": True,
            "service": "book-quiz-bot",
            "test_mode": TEST_MODE,
            "webhook": True
        }
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return jsonify(
        {
            "ok": True
        }
    )


# =========================================================
# CHECK ACCESS
# =========================================================

@app.get("/check-access")
def check_access():

    user_id = request.args.get(
        "user_id",
        ""
    ).strip()

    if not user_id:

        return jsonify(
            {
                "paid": False,
                "error": "user_id_required"
            }
        ), 400

    return jsonify(
        {
            "paid": is_paid(
                user_id
            ),
            "test_mode": TEST_MODE
        }
    )


# =========================================================
# WEBHOOK INFO
# =========================================================

@app.get("/webhook-info")
def webhook_info():

    try:

        result = tg(
            "getWebhookInfo"
        )

        return jsonify(
            result
        )

    except Exception as exc:

        log.exception(
            "Webhook info error"
        )

        return jsonify(
            {
                "ok": False,
                "error": str(exc)
            }
        ), 500


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    init_db()

    setup_webhook()

    log.info(
        "Starting Flask server on port %s",
        PORT
    )

    log.info(
        "TEST_MODE=%s",
        TEST_MODE
    )

    log.info(
        "WEB_APP_URL=%s",
        WEB_APP_URL
    )

    log.info(
        "WEBHOOK_URL=%s",
        WEBHOOK_URL
    )

    app.run(
        host="0.0.0.0",
        port=PORT,
        threaded=True,
        use_reloader=False
    )
