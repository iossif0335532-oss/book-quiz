import os
import json
import requests

from flask import Flask, request

TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("Не задана переменная окружения BOT_TOKEN")

API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

PAID_USERS_FILE = "paid_users.json"
DATABASE_FILE = "recommendation_database.json"
BOOKS_DIR = "books"

TEST_PRICE = 200
WEB_APP_URL = "https://book-quiz.onrender.com"


# ============================================================
# ПОЛЬЗОВАТЕЛИ, КОТОРЫЕ ОПЛАТИЛИ
# ============================================================

def load_paid_users():
    try:
        if not os.path.exists(PAID_USERS_FILE):
            return set()

        with open(PAID_USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return set()

        return {str(x) for x in data}

    except Exception as e:
        print("Ошибка загрузки paid_users.json:", e)
        return set()


def save_paid_users(users):
    try:
        with open(PAID_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                sorted(list(users)),
                f,
                ensure_ascii=False,
                indent=2
            )

        print("Оплаченные пользователи сохранены:", len(users))

    except Exception as e:
        print("Ошибка сохранения paid_users.json:", e)


PAID_USERS = load_paid_users()


# ============================================================
# TELEGRAM API
# ============================================================

def tg(method, data):
    try:
        response = requests.post(
            f"{API}/{method}",
            json=data,
            timeout=60
        )

        print()
        print("TELEGRAM:", method)
        print("STATUS:", response.status_code)
        print("RESPONSE:", response.text[:2000])

        try:
            return response.json()
        except Exception:
            return {}

    except Exception as e:
        print("TELEGRAM ERROR:", method, e)
        return {}


# ============================================================
# БАЗА КНИГ
# ============================================================

def load_books():
    try:
        if not os.path.exists(DATABASE_FILE):
            print("ОШИБКА: база не найдена:", DATABASE_FILE)
            return []

        with open(
            DATABASE_FILE,
            "r",
            encoding="utf-8-sig"
        ) as f:
            data = json.load(f)

        if isinstance(data, list):
            books = data

        elif isinstance(data, dict):
            books = data.get("books", [])

        else:
            books = []

        if not isinstance(books, list):
            print("ОШИБКА: books в базе не является списком")
            return []

        books = [
            book
            for book in books
            if isinstance(book, dict)
        ]

        print("Загружено книг из базы:", len(books))

        return books

    except Exception as e:
        print("ОШИБКА ЗАГРУЗКИ БАЗЫ:", e)
        return []


# ============================================================
# НОРМАЛИЗАЦИЯ НАЗВАНИЯ
# ============================================================

def normalize(text):
    if text is None:
        return ""

    text = str(text).strip().lower()

    replacements = {
        "ё": "е",
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "«": '"',
        "»": '"'
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return " ".join(text.split())


# ============================================================
# ПОИСК КНИГИ ВО ВСЕЙ БАЗЕ
# ============================================================

def find_book(title):
    requested = normalize(title)

    if not requested:
        return None

    books = load_books()

    # --------------------------------------------------------
    # 1. Точное совпадение названия
    # --------------------------------------------------------

    for book in books:

        book_title = normalize(
            book.get("title", "")
        )

        if book_title == requested:
            print("КНИГА НАЙДЕНА: точное совпадение")
            return book

    # --------------------------------------------------------
    # 2. Сравниваем название без кавычек
    # --------------------------------------------------------

    requested_clean = requested.replace('"', "").strip()

    for book in books:

        book_title = normalize(
            book.get("title", "")
        ).replace('"', "").strip()

        if book_title == requested_clean:
            print("КНИГА НАЙДЕНА: совпадение без кавычек")
            return book

    # --------------------------------------------------------
    # 3. Название содержится в названии книги
    # --------------------------------------------------------

    for book in books:

        book_title = normalize(
            book.get("title", "")
        )

        if requested in book_title:
            print("КНИГА НАЙДЕНА: частичное совпадение")
            return book

        if book_title in requested:
            print("КНИГА НАЙДЕНА: обратное частичное совпадение")
            return book

    # --------------------------------------------------------
    # 4. Проверяем дополнительные поля
    # --------------------------------------------------------

    for book in books:

        possible_titles = [
            book.get("name"),
            book.get("book"),
            book.get("book_title"),
            book.get("title_ru"),
            book.get("Название"),
            book.get("название")
        ]

        for value in possible_titles:

            if not value:
                continue

            candidate = normalize(value)

            if candidate == requested:
                print("КНИГА НАЙДЕНА: дополнительное поле")
                return book

    print("КНИГА НЕ НАЙДЕНА:", title)

    return None


# ============================================================
# ПОЛУЧЕНИЕ ИМЕНИ PDF ИЗ ЗАПИСИ
# ============================================================

def get_filename(book):

    fields = [
        "filename",
        "file",
        "pdf",
        "pdf_file",
        "pdf_filename",
        "filepath",
        "file_path",
        "path"
    ]

    for field in fields:

        value = book.get(field)

        if not value:
            continue

        value = str(value).strip()

        if not value:
            continue

        value = value.replace("\\", "/")

        filename = value.split("/")[-1]

        if filename.lower().endswith(".pdf"):
            return filename

    return ""


# ============================================================
# ПОИСК PDF
# ============================================================

def find_pdf(book):

    filename = get_filename(book)

    print("Ищем PDF для книги:", book.get("title"))
    print("Имя PDF из базы:", filename)

    if not filename:
        print("В записи книги нет имени PDF")
        return None

    # --------------------------------------------------------
    # books/filename.pdf
    # --------------------------------------------------------

    direct_path = os.path.join(
        BOOKS_DIR,
        filename
    )

    if os.path.isfile(direct_path):
        print("PDF найден:", direct_path)
        return direct_path

    # --------------------------------------------------------
    # filename.pdf рядом с bot.py
    # --------------------------------------------------------

    if os.path.isfile(filename):
        print("PDF найден:", filename)
        return filename

    # --------------------------------------------------------
    # Рекурсивный поиск внутри проекта
    # --------------------------------------------------------

    for root, dirs, files in os.walk("."):

        # Не ходим в служебные каталоги
        dirs[:] = [
            d for d in dirs
            if d not in {
                ".git",
                "__pycache__",
                ".venv",
                "venv"
            }
        ]

        for file in files:

            if file.lower() == filename.lower():

                path = os.path.join(
                    root,
                    file
                )

                print("PDF найден рекурсивно:", path)

                return path

    print("PDF НЕ НАЙДЕН:", filename)

    return None


# ============================================================
# ОТПРАВКА КНИГИ ПОЛЬЗОВАТЕЛЮ
# ============================================================

def send_book(chat_id, book_title):

    print()
    print("=" * 70)
    print("НАЧАЛО ВЫДАЧИ КНИГИ")
    print("Пользователь:", chat_id)
    print("Результат:", book_title)
    print("=" * 70)

    book = find_book(book_title)

    if not book:

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🎉 Тест завершён!\n\n"
                    f"📕 Твоя книга:\n{book_title}\n\n"
                    "Я не смог найти эту книгу в базе.\n"
                    "Проверь название книги в "
                    "recommendation_database.json."
                )
            }
        )

        return False

    real_title = str(
        book.get("title")
        or book.get("name")
        or book_title
    ).strip()

    author = str(
        book.get("author", "")
    ).strip()

    pdf_path = find_pdf(book)

    if not pdf_path:

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🎉 Тест завершён!\n\n"
                    f"📕 Твоя книга:\n{real_title}\n\n"
                    "Книга есть в базе, но PDF-файл "
                    "не найден на сервере.\n\n"
                    "Нужно положить соответствующий PDF "
                    "в папку books."
                )
            }
        )

        return False

    caption = (
        "🎉 Твой результат готов!\n\n"
        f"📕 {real_title}"
    )

    if author:
        caption += f"\n✍️ {author}"

    caption += "\n\nПриятного чтения! 📚"

    try:

        with open(
            pdf_path,
            "rb"
        ) as document:

            response = requests.post(
                f"{API}/sendDocument",

                data={
                    "chat_id": chat_id,
                    "caption": caption
                },

                files={
                    "document": (
                        os.path.basename(pdf_path),
                        document,
                        "application/pdf"
                    )
                },

                timeout=180
            )

        print()
        print("ОТПРАВКА PDF")
        print("Файл:", pdf_path)
        print("Статус:", response.status_code)
        print("Ответ:", response.text[:2000])

        if response.ok:
            print("КНИГА УСПЕШНО ОТПРАВЛЕНА")
            return True

        print("ОШИБКА TELEGRAM ПРИ ОТПРАВКЕ PDF")

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "⚠️ Книга найдена, но Telegram "
                    "не смог принять PDF.\n\n"
                    "Попробуй ещё раз."
                )
            }
        )

        return False

    except Exception as e:

        print("ОШИБКА ОТПРАВКИ PDF:", e)

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "⚠️ Произошла ошибка при отправке книги."
                )
            }
        )

        return False


# ============================================================
# КНОПКА ПРОХОЖДЕНИЯ ТЕСТА
# ============================================================

def test_button():

    return {
        "inline_keyboard": [
            [
                {
                    "text": "📚 Пройти тест",
                    "web_app": {
                        "url": WEB_APP_URL
                    }
                }
            ]
        ]
    }


# ============================================================
# КНОПКА ОПЛАТЫ
# ============================================================

def buy_button():

    return {
        "inline_keyboard": [
            [
                {
                    "text": f"🔓 Купить тест — {TEST_PRICE} ⭐",
                    "callback_data": "buy_test"
                }
            ]
        ]
    }


# ============================================================
# ГЛАВНАЯ
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

        print("Ошибка index.html:", e)

        return (
            "Book Quiz работает, "
            "но index.html не найден."
        ), 500


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():

    return "OK"


# ============================================================
# ПРОВЕРКА ОПЛАТЫ
# ============================================================

@app.route("/check-access")
def check_access():

    user_id = request.args.get(
        "user_id",
        ""
    ).strip()

    if not user_id:
        return {
            "paid": False
        }

    paid = str(user_id) in PAID_USERS

    print(
        "CHECK ACCESS:",
        user_id,
        "PAID:",
        paid
    )

    return {
        "paid": paid
    }


# ============================================================
# WEBHOOK
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
    print("=" * 80)
    print("НОВЫЙ TELEGRAM UPDATE")
    print("=" * 80)

    print(
        json.dumps(
            update,
            ensure_ascii=False
        )[:10000]
    )

    # ========================================================
    # PRE-CHECKOUT QUERY
    # ========================================================

    pre_checkout = update.get(
        "pre_checkout_query"
    )

    if pre_checkout:

        pre_checkout_id = pre_checkout.get(
            "id"
        )

        print(
            "PRE-CHECKOUT:",
            pre_checkout_id
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


    # ========================================================
    # CALLBACK QUERY
    # ========================================================

    callback = update.get(
        "callback_query"
    )

    if callback:

        callback_id = callback.get(
            "id"
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

        data = callback.get(
            "data"
        )

        print(
            "CALLBACK:",
            data
        )

        # ----------------------------------------------------
        # ПОКУПКА
        # ----------------------------------------------------

        if data == "buy_test":

            tg(
                "answerCallbackQuery",
                {
                    "callback_query_id":
                        callback_id
                }
            )

            invoice = tg(
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
                                    TEST_PRICE
                            }
                        ]
                }
            )

            print(
                "INVOICE RESULT:",
                invoice
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

    chat = message.get(
        "chat",
        {}
    )

    chat_id = chat.get(
        "id"
    )

    if not chat_id:
        return "ok"


    # ========================================================
    # УСПЕШНАЯ ОПЛАТА
    # ========================================================

    successful_payment = message.get(
        "successful_payment"
    )

    if successful_payment:

        user_id = str(
            chat_id
        )

        print()
        print("=" * 70)
        print("ОПЛАТА ПОЛУЧЕНА")
        print("USER:", user_id)
        print(
            "PAYLOAD:",
            successful_payment.get(
                "invoice_payload"
            )
        )
        print(
            "CURRENCY:",
            successful_payment.get(
                "currency"
            )
        )
        print(
            "TOTAL:",
            successful_payment.get(
                "total_amount"
            )
        )
        print("=" * 70)

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
                    test_button()
            }
        )

        return "ok"


    # ========================================================
    # WEB APP DATA
    # ========================================================

    web_app_data = message.get(
        "web_app_data"
    )

    if web_app_data:

        print()
        print("=" * 70)
        print("ПОЛУЧЕН РЕЗУЛЬТАТ ИЗ MINI APP")
        print("=" * 70)

        user_id = str(
            chat_id
        )

        # ----------------------------------------------------
        # ПРОВЕРЯЕМ ОПЛАТУ
        # ----------------------------------------------------

        if user_id not in PAID_USERS:

            print(
                "ЗАПРЕЩЕНО: пользователь не оплатил",
                user_id
            )

            tg(
                "sendMessage",
                {
                    "chat_id":
                        chat_id,

                    "text":
                        (
                            "🔒 Тест не оплачен.\n\n"
                            "Сначала приобрети прохождение "
                            "за 200 ⭐."
                        ),

                    "reply_markup":
                        buy_button()
                }
            )

            return "ok"

        # ----------------------------------------------------
        # ЧИТАЕМ DATA
        # ----------------------------------------------------

        raw_data = web_app_data.get(
            "data",
            ""
        )

        print(
            "RAW WEB APP DATA:",
            raw_data
        )

        try:

            result = json.loads(
                raw_data
            )

        except Exception as e:

            print(
                "ОШИБКА JSON:",
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

        print(
            "RESULT:",
            json.dumps(
                result,
                ensure_ascii=False
            )[:5000]
        )

        action = result.get(
            "action"
        )

        if action != "quiz_result":

            print(
                "Неизвестное действие:",
                action
            )

            return "ok"

        # ----------------------------------------------------
        # ПОЛУЧАЕМ КНИГУ
        # ----------------------------------------------------

        book_title = (
            result.get("book")
            or result.get("book_title")
            or result.get("title")
        )

        archetype = result.get(
            "archetype",
            ""
        )

        match = result.get(
            "match",
            ""
        )

        print()
        print("ТИПАЖ:", archetype)
        print("КНИГА:", book_title)
        print("СОВПАДЕНИЕ:", match)

        if not book_title:

            tg(
                "sendMessage",
                {
                    "chat_id":
                        chat_id,

                    "text":
                        (
                            "⚠️ Тест завершён, "
                            "но название книги не передано."
                        )
                }
            )

            return "ok"

        # ----------------------------------------------------
        # ОТПРАВЛЯЕМ КНИГУ
        # ----------------------------------------------------

        send_book(
            chat_id,
            book_title
        )

        return "ok"


    # ========================================================
    # START
    # ========================================================

    text = message.get(
        "text",
        ""
    ).strip()

    if text == "/start":

        user_id = str(
            chat_id
        )

        print(
            "START:",
            user_id
        )

        # ----------------------------------------------------
        # УЖЕ ОПЛАЧЕНО
        # ----------------------------------------------------

        if user_id in PAID_USERS:

            tg(
                "sendMessage",
                {
                    "chat_id":
                        chat_id,

                    "text":
                        (
                            "📚 Book Quiz\n\n"
                            "Тест уже разблокирован.\n\n"
                            "Нажимай кнопку и проходи 👇"
                        ),

                    "reply_markup":
                        test_button()
                }
            )

        # ----------------------------------------------------
        # НЕ ОПЛАЧЕНО
        # ----------------------------------------------------

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
                        buy_button()
                }
            )

        return "ok"


    return "ok"


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    print()
    print("=" * 70)
    print("BOOK QUIZ BOT STARTING")
    print("PORT:", port)
    print("WEB APP:", WEB_APP_URL)
    print("DATABASE:", DATABASE_FILE)
    print("BOOKS:", BOOKS_DIR)
    print("PAID USERS:", len(PAID_USERS))
    print("=" * 70)

    app.run(
        host="0.0.0.0",
        port=port
    )
