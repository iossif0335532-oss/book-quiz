import os
import json
import requests

from flask import Flask, request

# ============================================================
# НАСТРОЙКИ
# ============================================================

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
# ОПЛАТИВШИЕ ПОЛЬЗОВАТЕЛИ
# ============================================================

def load_paid_users():
    try:
        if not os.path.exists(PAID_USERS_FILE):
            return set()

        with open(
            PAID_USERS_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        if not isinstance(data, list):
            return set()

        return set(str(x) for x in data)

    except Exception as e:
        print("Ошибка загрузки paid_users:", e)
        return set()


def save_paid_users(users):
    try:
        with open(
            PAID_USERS_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                sorted(list(users)),
                f,
                ensure_ascii=False,
                indent=2
            )

        return True

    except Exception as e:
        print("Ошибка сохранения paid_users:", e)
        return False


PAID_USERS = load_paid_users()


# ============================================================
# TELEGRAM API
# ============================================================

def tg(method, data=None):
    try:
        if data is None:
            data = {}

        response = requests.post(
            f"{API}/{method}",
            json=data,
            timeout=30
        )

        print(
            f"Telegram {method}:",
            response.status_code,
            response.text[:1000]
        )

        try:
            return response.json()
        except Exception:
            return {}

    except Exception as e:
        print(
            f"Telegram ERROR {method}:",
            e
        )
        return {}


# ============================================================
# БАЗА КНИГ
# ============================================================

def load_books():
    try:
        if not os.path.exists(DATABASE_FILE):
            print(
                "ОШИБКА: база книг не найдена:",
                DATABASE_FILE
            )
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
            return []

        result = []

        for book in books:
            if isinstance(book, dict):
                result.append(book)

        print(
            "Загружено книг из базы:",
            len(result)
        )

        return result

    except Exception as e:
        print(
            "ОШИБКА ЗАГРУЗКИ БАЗЫ:",
            e
        )
        return []


# ============================================================
# НОРМАЛИЗАЦИЯ НАЗВАНИЯ
# ============================================================

def normalize_text(value):
    value = str(value or "").strip().lower()

    replacements = {
        "ё": "е",
        "—": "-",
        "–": "-",
        "«": "",
        "»": "",
        "\"": "",
        "'": ""
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = " ".join(value.split())

    return value


# ============================================================
# ПОИСК КНИГИ В БАЗЕ
# ============================================================

def find_book(title):
    target = normalize_text(title)

    if not target:
        return None

    books = load_books()

    # --------------------------------------------------------
    # 1. ТОЧНОЕ СОВПАДЕНИЕ
    # --------------------------------------------------------

    for book in books:

        book_title = normalize_text(
            book.get("title", "")
        )

        if book_title == target:
            print(
                "Книга найдена точным совпадением:",
                book.get("title")
            )
            return book

    # --------------------------------------------------------
    # 2. ЧАСТИЧНОЕ СОВПАДЕНИЕ
    # --------------------------------------------------------

    for book in books:

        book_title = normalize_text(
            book.get("title", "")
        )

        if not book_title:
            continue

        if target in book_title:
            print(
                "Книга найдена частичным совпадением:",
                book.get("title")
            )
            return book

        if book_title in target:
            print(
                "Книга найдена частичным совпадением:",
                book.get("title")
            )
            return book

    # --------------------------------------------------------
    # 3. ПОИСК ПО НАЗВАНИЮ ФАЙЛА
    # --------------------------------------------------------

    for book in books:

        filename = normalize_text(
            get_book_filename(book)
        )

        if not filename:
            continue

        filename_without_pdf = filename

        if filename_without_pdf.endswith(".pdf"):
            filename_without_pdf = filename_without_pdf[:-4]

        if (
            target == filename_without_pdf
            or target in filename_without_pdf
            or filename_without_pdf in target
        ):
            print(
                "Книга найдена по имени файла:",
                book.get("title")
            )
            return book

    print(
        "КНИГА НЕ НАЙДЕНА:",
        title
    )

    return None


# ============================================================
# ПОЛУЧЕНИЕ ИМЕНИ PDF
# ============================================================

def get_book_filename(book):

    # --------------------------------------------------------
    # Вариант 1 — filename
    # --------------------------------------------------------

    filename = str(
        book.get(
            "filename",
            ""
        )
    ).strip()

    if filename:
        return filename

    # --------------------------------------------------------
    # Вариант 2 — filepath
    # --------------------------------------------------------

    filepath = str(
        book.get(
            "filepath",
            ""
        )
    ).strip()

    if filepath:

        filepath = filepath.replace(
            "\\",
            "/"
        )

        return filepath.split("/")[-1]

    # --------------------------------------------------------
    # Вариант 3 — file
    # --------------------------------------------------------

    filename = str(
        book.get(
            "file",
            ""
        )
    ).strip()

    if filename:
        return filename

    # --------------------------------------------------------
    # Вариант 4 — pdf
    # --------------------------------------------------------

    filename = str(
        book.get(
            "pdf",
            ""
        )
    ).strip()

    if filename:
        return filename

    return ""


# ============================================================
# ПОИСК PDF
# ============================================================

def find_pdf(book):

    filename = get_book_filename(book)

    print(
        "Ищем PDF:",
        filename
    )

    if not filename:
        print(
            "У книги нет filename/filepath/pdf"
        )
        return None

    # --------------------------------------------------------
    # Убираем возможные пути Windows/Linux
    # --------------------------------------------------------

    clean_filename = filename.replace(
        "\\",
        "/"
    ).split("/")[-1]

    # --------------------------------------------------------
    # 1. books/filename.pdf
    # --------------------------------------------------------

    direct_path = os.path.join(
        BOOKS_DIR,
        clean_filename
    )

    if os.path.isfile(direct_path):

        print(
            "PDF найден:",
            direct_path
        )

        return direct_path

    # --------------------------------------------------------
    # 2. filename рядом с bot.py
    # --------------------------------------------------------

    if os.path.isfile(clean_filename):

        print(
            "PDF найден рядом с bot.py:",
            clean_filename
        )

        return clean_filename

    # --------------------------------------------------------
    # 3. Рекурсивный поиск внутри books
    # --------------------------------------------------------

    if os.path.isdir(BOOKS_DIR):

        for root, dirs, files in os.walk(
            BOOKS_DIR
        ):

            for file in files:

                if file.lower() == clean_filename.lower():

                    found = os.path.join(
                        root,
                        file
                    )

                    print(
                        "PDF найден рекурсивно:",
                        found
                    )

                    return found

    # --------------------------------------------------------
    # 4. Поиск PDF по названию книги
    # --------------------------------------------------------

    book_title = normalize_text(
        book.get(
            "title",
            ""
        )
    )

    if book_title and os.path.isdir(BOOKS_DIR):

        for root, dirs, files in os.walk(
            BOOKS_DIR
        ):

            for file in files:

                if not file.lower().endswith(".pdf"):
                    continue

                filename_normalized = normalize_text(
                    os.path.splitext(file)[0]
                )

                if (
                    book_title == filename_normalized
                    or book_title in filename_normalized
                    or filename_normalized in book_title
                ):

                    found = os.path.join(
                        root,
                        file
                    )

                    print(
                        "PDF найден по названию книги:",
                        found
                    )

                    return found

    print(
        "PDF НЕ НАЙДЕН:",
        clean_filename
    )

    return None


# ============================================================
# ОТПРАВКА КНИГИ
# ============================================================

def send_book(chat_id, book_title):

    print()
    print("=" * 60)
    print("НАЧИНАЕМ ОТПРАВКУ КНИГИ")
    print("Пользователь:", chat_id)
    print("Книга:", book_title)
    print("=" * 60)

    book = find_book(book_title)

    if not book:

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🎉 Тест завершён!\n\n"
                    f"📕 Твоя книга:\n{book_title}\n\n"
                    "⚠️ Книга есть в результате теста, "
                    "но я не нашёл её в базе книг."
                )
            }
        )

        return False

    real_title = str(
        book.get(
            "title",
            book_title
        )
    ).strip()

    author = str(
        book.get(
            "author",
            ""
        )
    ).strip()

    pdf_path = find_pdf(book)

    if not pdf_path:

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🎉 Тест завершён!\n\n"
                    f"📕 Твоя книга:\n{real_title}\n"
                    +
                    (
                        f"✍️ {author}\n"
                        if author
                        else ""
                    )
                    +
                    "\n⚠️ PDF этой книги пока "
                    "не загружен на сервер."
                )
            }
        )

        return False

    # --------------------------------------------------------
    # ОТПРАВЛЯЕМ PDF
    # --------------------------------------------------------

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

        print(
            "SEND DOCUMENT:",
            response.status_code
        )

        print(
            response.text[:2000]
        )

        if response.ok:

            print(
                "КНИГА УСПЕШНО ОТПРАВЛЕНА:",
                real_title
            )

            return True

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "⚠️ Книга найдена, "
                    "но Telegram не смог её отправить."
                )
            }
        )

        return False

    except Exception as e:

        print(
            "ОШИБКА ОТПРАВКИ PDF:",
            e
        )

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "⚠️ Произошла ошибка "
                    "при отправке книги."
                )
            }
        )

        return False


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

        print(
            "Ошибка index.html:",
            e
        )

        return (
            "Book Quiz работает."
        ), 200


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():

    return "OK"


# ============================================================
# ПРОВЕРКА ДОСТУПА
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

    return {
        "paid":
            str(user_id)
            in PAID_USERS
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
    print("=" * 70)
    print("НОВЫЙ TELEGRAM UPDATE")
    print("=" * 70)

    print(
        json.dumps(
            update,
            ensure_ascii=False
        )[:10000]
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

        print(
            "CALLBACK DATA:",
            data
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

            invoice_result = tg(
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
                invoice_result
            )

            return "ok"

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
        print("=" * 60)
        print("ОПЛАТА ПОЛУЧЕНА")
        print("USER:", user_id)
        print("=" * 60)

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
    # ДАННЫЕ ИЗ TELEGRAM MINI APP
    # ========================================================

    web_app_data = message.get(
        "web_app_data"
    )

    if web_app_data:

        print()
        print("=" * 60)
        print("ПОЛУЧЕН РЕЗУЛЬТАТ MINI APP")
        print("=" * 60)

        print(
            "WEB APP DATA:",
            web_app_data
        )

        user_id = str(
            chat_id
        )

        # ----------------------------------------------------
        # ПРОВЕРКА ОПЛАТЫ
        # ----------------------------------------------------

        if user_id not in PAID_USERS:

            print(
                "ПОПЫТКА ПОЛУЧИТЬ КНИГУ БЕЗ ОПЛАТЫ:",
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
                            f"за {TEST_PRICE} ⭐."
                        ),

                    "reply_markup":
                        {
                            "inline_keyboard":
                                [
                                    [
                                        {
                                            "text":
                                                f"🔓 Купить тест — {TEST_PRICE} ⭐",

                                            "callback_data":
                                                "buy_test"
                                        }
                                    ]
                                ]
                        }
                }
            )

            return "ok"


        # ----------------------------------------------------
        # ЧИТАЕМ JSON
        # ----------------------------------------------------

        raw_data = web_app_data.get(
            "data",
            ""
        )

        print(
            "RAW RESULT:",
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


        # ----------------------------------------------------
        # ПРОВЕРЯЕМ ACTION
        # ----------------------------------------------------

        action = result.get(
            "action"
        )

        print(
            "ACTION:",
            action
        )

        if action != "quiz_result":

            print(
                "Неизвестное действие:",
                action
            )

            return "ok"


        # ----------------------------------------------------
        # ПОЛУЧАЕМ РЕЗУЛЬТАТ
        # ----------------------------------------------------

        book_title = result.get(
            "book",
            ""
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
        print(
            "РЕЗУЛЬТАТ ТЕСТА:"
        )

        print(
            "Типаж:",
            archetype
        )

        print(
            "Книга:",
            book_title
        )

        print(
            "Совпадение:",
            match
        )


        # ----------------------------------------------------
        # ЕСЛИ КНИГА НЕ УКАЗАНА
        # ----------------------------------------------------

        if not book_title:

            tg(
                "sendMessage",
                {
                    "chat_id":
                        chat_id,

                    "text":
                        "⚠️ В результате теста не указана книга."
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
    # /START
    # ========================================================

    text = message.get(
        "text",
        ""
    ).strip()

    if text == "/start":

        user_id = str(
            chat_id
        )

        # ----------------------------------------------------
        # УЖЕ ОПЛАТИЛ
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
                                                        WEB_APP_URL
                                                }
                                        }
                                    ]
                                ]
                        }
                }
            )

            return "ok"


        # ----------------------------------------------------
        # НЕ ОПЛАТИЛ
        # ----------------------------------------------------

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
                        f"🔓 Стоимость прохождения — {TEST_PRICE} ⭐"
                    ),

                "reply_markup":
                    {
                        "inline_keyboard":
                            [
                                [
                                    {
                                        "text":
                                            f"🔓 Купить тест — {TEST_PRICE} ⭐",

                                        "callback_data":
                                            "buy_test"
                                    }
                                ]
                            ]
                        }
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
            10000
        )
    )

    print(
        "Book Quiz запускается..."
    )

    print(
        "PORT:",
        port
    )

    print(
        "DATABASE:",
        DATABASE_FILE
    )

    print(
        "BOOKS DIR:",
        BOOKS_DIR
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
