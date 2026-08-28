import os
import json
import requests

from flask import Flask, request

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

PAID_USERS_FILE = "paid_users.json"
DATABASE_FILE = "recommendation_database.json"
BOOKS_DIR = "books"


def load_paid_users():
    try:
        if not os.path.exists(PAID_USERS_FILE):
            return set()

        with open(PAID_USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return set(str(x) for x in data)

    except Exception as e:
        print("Ошибка загрузки paid_users:", e)
        return set()


def save_paid_users(users):
    try:
        with open(PAID_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                list(users),
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:
        print("Ошибка сохранения paid_users:", e)


PAID_USERS = load_paid_users()


def tg(method, data):
    try:
        response = requests.post(
            f"{API}/{method}",
            json=data,
            timeout=30
        )

        print("Telegram:", method)
        print("Status:", response.status_code)
        print("Response:", response.text[:1000])

        return response.json()

    except Exception as e:
        print("Telegram ERROR:", method, e)
        return {}


def load_books():
    try:
        if not os.path.exists(DATABASE_FILE):
            print("База книг не найдена:", DATABASE_FILE)
            return []

        with open(
            DATABASE_FILE,
            "r",
            encoding="utf-8-sig"
        ) as f:
            data = json.load(f)

        if isinstance(data, dict):
            books = data.get("books", [])

        elif isinstance(data, list):
            books = data

        else:
            books = []

        if not isinstance(books, list):
            return []

        return [
            book
            for book in books
            if isinstance(book, dict)
        ]

    except Exception as e:
        print("Ошибка загрузки базы книг:", e)
        return []


def find_book(title):
    title = str(title or "").strip().lower()

    if not title:
        return None

    books = load_books()

    for book in books:
        book_title = str(
            book.get("title", "")
        ).strip().lower()

        if book_title == title:
            return book

    for book in books:
        book_title = str(
            book.get("title", "")
        ).strip().lower()

        if title in book_title or book_title in title:
            return book

    return None


def get_book_filename(book):
    filename = str(
        book.get("filename", "")
    ).strip()

    if filename:
        return filename

    filepath = str(
        book.get("filepath", "")
    ).strip()

    if filepath:
        filepath = filepath.replace("\\", "/")
        return filepath.split("/")[-1]

    return ""


def find_pdf(book):
    filename = get_book_filename(book)

    if not filename:
        return None

    path = os.path.join(
        BOOKS_DIR,
        filename
    )

    if os.path.isfile(path):
        return path

    if os.path.isfile(filename):
        return filename

    if os.path.exists(BOOKS_DIR):
        for root, dirs, files in os.walk(BOOKS_DIR):
            for file in files:
                if file == filename:
                    return os.path.join(root, file)

    return None


def send_book(chat_id, title):
    print("Ищем книгу:", title)

    book = find_book(title)

    if not book:
        print("Книга не найдена:", title)

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "⚠️ Результат определён:\n\n"
                    f"📕 {title}\n\n"
                    "Но книга пока не подключена "
                    "к серверу."
                )
            }
        )

        return False

    real_title = str(
        book.get("title", title)
    ).strip()

    author = str(
        book.get("author", "")
    ).strip()

    pdf_path = find_pdf(book)

    print("Название:", real_title)
    print("PDF:", pdf_path)

    if not pdf_path:
        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🎉 Тест завершён!\n\n"
                    f"📕 Твоя книга:\n{real_title}\n\n"
                    "Но PDF этой книги пока "
                    "не загружен на сервер."
                )
            }
        )

        return False

    try:
        with open(pdf_path, "rb") as document:

            response = requests.post(
                f"{API}/sendDocument",

                data={
                    "chat_id": chat_id,
                    "caption": (
                        "🎉 Твой результат готов!\n\n"
                        f"📕 {real_title}"
                        +
                        (
                            f"\n✍️ {author}"
                            if author
                            else ""
                        )
                        +
                        "\n\nПриятного чтения! 📚"
                    )
                },

                files={
                    "document": document
                },

                timeout=120
            )

        print(
            "SEND DOCUMENT:",
            response.status_code,
            response.text[:1000]
        )

        return response.ok

    except Exception as e:
        print("Ошибка отправки PDF:", e)

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "⚠️ Книга найдена, "
                    "но произошла ошибка при отправке PDF."
                )
            }
        )

        return False


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
        return (
            "Ошибка загрузки index.html: " + str(e)
        ), 500


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
        return {"paid": False}

    return {
        "paid": str(user_id) in PAID_USERS
    }


@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():

    update = request.json or {}

    print()
    print("=" * 60)
    print("НОВЫЙ UPDATE")
    print("=" * 60)

    print(
        json.dumps(
            update,
            ensure_ascii=False
        )[:5000]
    )

    # ========================================================
    # PRE-CHECKOUT
    # ========================================================

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
                "ok": True
            }
        )

        return "ok"

    # ========================================================
    # CALLBACK
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

        chat_id = message.get(
            "chat",
            {}
        ).get(
            "id"
        )

        data = callback.get(
            "data"
        )

        print(
            "CALLBACK:",
            data
        )

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
    # WEB APP DATA
    # ========================================================

    web_app_data = message.get(
        "web_app_data"
    )

    if web_app_data:

        print(
            "WEB APP DATA:",
            web_app_data
        )

        user_id = str(chat_id)

        if user_id not in PAID_USERS:

            print(
                "ПОПЫТКА ОТПРАВИТЬ РЕЗУЛЬТАТ "
                "БЕЗ ОПЛАТЫ:",
                user_id
            )

            tg(
                "sendMessage",
                {
                    "chat_id": chat_id,

                    "text": (
                        "🔒 Тест не оплачен.\n\n"
                        "Сначала приобрети прохождение "
                        "за 200 ⭐."
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

        raw_data = web_app_data.get(
            "data",
            ""
        )

        try:

            result = json.loads(
                raw_data
            )

        except Exception as e:

            print(
                "Ошибка JSON результата:",
                e
            )

            tg(
                "sendMessage",
                {
                    "chat_id":
                        chat_id,

                    "text":
                        "⚠️ Не удалось прочитать результат теста."
                }
            )

            return "ok"

        action = result.get(
            "action"
        )

        if action != "quiz_result":

            print(
                "Неизвестное действие:",
                action
            )

            return "ok"

        book_title = result.get(
            "book"
        )

        archetype = result.get(
            "archetype",
            ""
        )

        match = result.get(
            "match",
            ""
        )

        print("РЕЗУЛЬТАТ ТЕСТА")
        print("Типаж:", archetype)
        print("Книга:", book_title)
        print("Совпадение:", match)

        if not book_title:

            tg(
                "sendMessage",
                {
                    "chat_id":
                        chat_id,

                    "text":
                        "⚠️ В результате не указана книга."
                }
            )

            return "ok"

        send_book(
            chat_id,
            book_title
        )

        return "ok"

    # ========================================================
    # SUCCESSFUL PAYMENT
    # ========================================================

    successful_payment = message.get(
        "successful_payment"
    )

    if successful_payment:

        user_id = str(chat_id)

        print(
            "ОПЛАТА ПОЛУЧЕНА:",
            user_id
        )

        PAID_USERS.add(
            user_id
        )

        save_paid_users(
            PAID_USERS
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
                        "Нажимай кнопку и проходи тест 👇"
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

    # ========================================================
    # START
    # ========================================================

    if message.get("text") == "/start":

        user_id = str(chat_id)

        if user_id in PAID_USERS:

            tg(
                "sendMessage",
                {
                    "chat_id":
                        chat_id,

                    "text":
                        (
                            "📚 Book Quiz\n\n"
                            "Тест уже разблокирован.\n"
                            "Можешь проходить 👇"
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

        else:

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
