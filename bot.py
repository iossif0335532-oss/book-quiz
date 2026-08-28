```python
import os
import json
import requests

from flask import Flask, request, jsonify


# ============================================================
# НАСТРОЙКИ
# ============================================================

TOKEN = os.environ.get("BOT_TOKEN", "").strip()

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан в переменных окружения Render"
    )

API = f"https://api.telegram.org/bot{TOKEN}"

WEB_APP_URL = "https://book-quiz.onrender.com"

PAID_USERS_FILE = "paid_users.json"
DATABASE_FILE = "recommendation_database.json"
BOOKS_DIR = "books"

PRICE_STARS = 200


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# ЛОГ
# ============================================================

def log(message):
    print(message, flush=True)


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

        log(
            f"Telegram {method}: "
            f"{response.status_code} "
            f"{response.text[:2000]}"
        )

        try:
            return response.json()
        except Exception:
            return {}

    except Exception as e:
        log(f"Telegram ERROR {method}: {e}")
        return {}


# ============================================================
# PAID USERS
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

        return {
            str(user_id)
            for user_id in data
        }

    except Exception as e:

        log(
            f"Ошибка загрузки paid_users: {e}"
        )

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

        log(
            f"PAID USERS сохранены: {len(users)}"
        )

    except Exception as e:

        log(
            f"Ошибка сохранения paid_users: {e}"
        )


PAID_USERS = load_paid_users()


def add_paid_user(user_id):

    user_id = str(user_id)

    PAID_USERS.add(user_id)

    save_paid_users(PAID_USERS)

    log(
        f"Пользователь добавлен в PAID_USERS: "
        f"{user_id}"
    )


def is_paid(user_id):

    return str(user_id) in PAID_USERS


# ============================================================
# БАЗА КНИГ
# ============================================================

def load_books():

    try:

        if not os.path.exists(DATABASE_FILE):

            log(
                f"База книг НЕ найдена: "
                f"{DATABASE_FILE}"
            )

            return []

        with open(
            DATABASE_FILE,
            "r",
            encoding="utf-8-sig"
        ) as f:

            data = json.load(f)

        if isinstance(data, dict):

            books = data.get(
                "books",
                []
            )

        elif isinstance(data, list):

            books = data

        else:

            books = []

        if not isinstance(books, list):
            return []

        books = [
            book
            for book in books
            if isinstance(book, dict)
        ]

        log(
            f"База книг загружена: "
            f"{len(books)} книг"
        )

        return books

    except Exception as e:

        log(
            f"Ошибка загрузки базы книг: {e}"
        )

        return []


# ============================================================
# НОРМАЛИЗАЦИЯ
# ============================================================

def normalize(value):

    return (
        str(value or "")
        .strip()
        .lower()
        .replace("ё", "е")
    )


# ============================================================
# ПОИСК КНИГИ
# ============================================================

def find_book(title):

    wanted = normalize(title)

    if not wanted:
        return None

    books = load_books()

    # --------------------------------------------------------
    # 1. Точное совпадение
    # --------------------------------------------------------

    for book in books:

        book_title = normalize(
            book.get("title", "")
        )

        if book_title == wanted:
            return book

    # --------------------------------------------------------
    # 2. Без скобок и кавычек
    # --------------------------------------------------------

    wanted_clean = (
        wanted
        .replace("(", "")
        .replace(")", "")
        .replace('"', "")
        .replace("'", "")
    )

    for book in books:

        book_title = normalize(
            book.get("title", "")
        )

        book_title_clean = (
            book_title
            .replace("(", "")
            .replace(")", "")
            .replace('"', "")
            .replace("'", "")
        )

        if book_title_clean == wanted_clean:
            return book

    # --------------------------------------------------------
    # 3. Частичное совпадение
    # --------------------------------------------------------

    for book in books:

        book_title = normalize(
            book.get("title", "")
        )

        if (
            wanted in book_title
            or book_title in wanted
        ):
            return book

    return None


# ============================================================
# ИМЯ PDF
# ============================================================

def get_book_filename(book):

    filename = str(
        book.get(
            "filename",
            ""
        )
    ).strip()

    if filename:
        return filename

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

    return ""


# ============================================================
# ПОИСК PDF
# ============================================================

def find_pdf(book):

    filename = get_book_filename(book)

    if not filename:

        log(
            "У книги отсутствует filename/filepath"
        )

        return None

    log(
        f"Ищем PDF: {filename}"
    )

    # --------------------------------------------------------
    # 1. books/filename
    # --------------------------------------------------------

    direct_path = os.path.join(
        BOOKS_DIR,
        filename
    )

    if os.path.isfile(direct_path):

        log(
            f"PDF найден: {direct_path}"
        )

        return direct_path

    # --------------------------------------------------------
    # 2. Корень проекта
    # --------------------------------------------------------

    root_path = filename

    if os.path.isfile(root_path):

        log(
            f"PDF найден в корне: {root_path}"
        )

        return root_path

    # --------------------------------------------------------
    # 3. Рекурсивно внутри books
    # --------------------------------------------------------

    if os.path.isdir(BOOKS_DIR):

        for root, dirs, files in os.walk(
            BOOKS_DIR
        ):

            for file in files:

                if file == filename:

                    found_path = os.path.join(
                        root,
                        file
                    )

                    log(
                        f"PDF найден рекурсивно: "
                        f"{found_path}"
                    )

                    return found_path

    log(
        f"PDF НЕ найден: {filename}"
    )

    return None


# ============================================================
# ОТПРАВКА ТЕКСТА
# ============================================================

def send_text(
    chat_id,
    text,
    reply_markup=None
):

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup is not None:

        data["reply_markup"] = reply_markup

    return tg(
        "sendMessage",
        data
    )


# ============================================================
# КНОПКА ТЕСТА
# ============================================================

def quiz_button():

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
                    "text":
                        f"🔓 Купить тест — {PRICE_STARS} ⭐",

                    "callback_data":
                        "buy_test"
                }

            ]

        ]

    }


# ============================================================
# ОТПРАВКА КНИГИ
# ============================================================

def send_book(
    chat_id,
    title
):

    log("")
    log("=" * 70)
    log("ОТПРАВКА КНИГИ")
    log("=" * 70)

    log(
        f"Chat ID: {chat_id}"
    )

    log(
        f"Результат теста: {title}"
    )

    # --------------------------------------------------------
    # Ищем книгу в базе
    # --------------------------------------------------------

    book = find_book(title)

    if not book:

        log(
            f"КНИГА НЕ НАЙДЕНА В БАЗЕ: {title}"
        )

        send_text(
            chat_id,
            (
                "⚠️ Тест завершён, "
                "но книга не найдена в базе.\n\n"
                f"📕 {title}\n\n"
                "Проверь название книги "
                "в recommendation_database.json."
            )
        )

        return False

    # --------------------------------------------------------
    # Данные книги
    # --------------------------------------------------------

    real_title = str(
        book.get(
            "title",
            title
        )
    ).strip()

    author = str(
        book.get(
            "author",
            ""
        )
    ).strip()

    filename = get_book_filename(
        book
    )

    log(
        f"Книга в базе: {real_title}"
    )

    log(
        f"Автор: {author}"
    )

    log(
        f"Filename: {filename}"
    )

    # --------------------------------------------------------
    # Ищем PDF
    # --------------------------------------------------------

    pdf_path = find_pdf(book)

    if not pdf_path:

        log(
            f"PDF НЕ НАЙДЕН для книги: "
            f"{real_title}"
        )

        send_text(
            chat_id,
            (
                "🎉 Тест завершён!\n\n"
                f"📕 {real_title}\n\n"
                "Но PDF этой книги "
                "не найден на сервере.\n\n"
                f"Искомый файл:\n"
                f"{filename}\n\n"
                "Проверь папку books."
            )
        )

        return False

    # --------------------------------------------------------
    # Caption
    # --------------------------------------------------------

    caption = (
        "🎉 Твой результат готов!\n\n"
        f"📕 {real_title}"
    )

    if author:

        caption += (
            f"\n✍️ {author}"
        )

    caption += (
        "\n\nПриятного чтения! 📚"
    )

    log(
        f"Отправляем файл: {pdf_path}"
    )

    # --------------------------------------------------------
    # Отправляем PDF
    # --------------------------------------------------------

    try:

        with open(
            pdf_path,
            "rb"
        ) as document:

            response = requests.post(

                f"{API}/sendDocument",

                data={
                    "chat_id":
                        str(chat_id),

                    "caption":
                        caption
                },

                files={
                    "document": (
                        os.path.basename(
                            pdf_path
                        ),
                        document,
                        "application/pdf"
                    )
                },

                timeout=180
            )

        log(
            "sendDocument: "
            f"{response.status_code} "
            f"{response.text[:2000]}"
        )

        if response.ok:

            result = response.json()

            if result.get("ok"):

                log(
                    f"КНИГА УСПЕШНО ОТПРАВЛЕНА: "
                    f"{real_title}"
                )

                return True

        send_text(
            chat_id,
            (
                "⚠️ PDF найден, "
                "но Telegram не смог "
                "его отправить.\n\n"
                f"{response.text[:1000]}"
            )
        )

        return False

    except Exception as e:

        log(
            f"ОШИБКА ОТПРАВКИ PDF: {e}"
        )

        send_text(
            chat_id,
            (
                "⚠️ Произошла ошибка "
                "при отправке книги.\n\n"
                f"{e}"
            )
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

        return (
            "Ошибка загрузки index.html: "
            + str(e)
        ), 500


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
        "paid": is_paid(user_id)
    }


# ============================================================
# TESTPAY
# ============================================================

@app.route("/testpay")
def testpay():

    user_id = request.args.get(
        "user_id",
        ""
    ).strip()

    if not user_id:

        return (
            "Для теста открой:\n"
            "/testpay?user_id=ТВОЙ_TELEGRAM_ID"
        )

    add_paid_user(
        user_id
    )

    return (
        "OK. Доступ выдан.\n"
        f"user_id={user_id}"
    )


# ============================================================
# НОВЫЙ ENDPOINT
#
# СЮДА MINI APP ОТПРАВЛЯЕТ РЕЗУЛЬТАТ
# ============================================================

@app.route(
    "/submit-result",
    methods=["POST"]
)
def submit_result():

    log("")
    log("=" * 70)
    log("НОВЫЙ РЕЗУЛЬТАТ ТЕСТА")
    log("=" * 70)

    try:

        data = request.get_json(
            silent=True
        ) or {}

        log(
            json.dumps(
                data,
                ensure_ascii=False
            )[:10000]
        )

        # ----------------------------------------------------
        # USER ID
        # ----------------------------------------------------

        user_id = str(
            data.get(
                "user_id",
                ""
            )
        ).strip()

        if not user_id:

            log(
                "ОШИБКА: отсутствует user_id"
            )

            return jsonify({
                "ok": False,
                "error":
                    "user_id_required"
            }), 400

        # ----------------------------------------------------
        # ПРОВЕРКА ОПЛАТЫ
        # ----------------------------------------------------

        if not is_paid(user_id):

            log(
                f"ПОЛЬЗОВАТЕЛЬ НЕ ОПЛАТИЛ: "
                f"{user_id}"
            )

            return jsonify({
                "ok": False,
                "error":
                    "not_paid"
            }), 403

        # ----------------------------------------------------
        # ACTION
        # ----------------------------------------------------

        action = data.get(
            "action"
        )

        if action != "quiz_result":

            log(
                f"НЕВЕРНЫЙ ACTION: {action}"
            )

            return jsonify({
                "ok": False,
                "error":
                    "invalid_action"
            }), 400

        # ----------------------------------------------------
        # КНИГА
        # ----------------------------------------------------

        book_title = str(
            data.get(
                "book",
                ""
            )
        ).strip()

        if not book_title:

            log(
                "ОШИБКА: книга отсутствует"
            )

            return jsonify({
                "ok": False,
                "error":
                    "book_required"
            }), 400

        archetype = str(
            data.get(
                "archetype",
                ""
            )
        ).strip()

        match = data.get(
            "match",
            ""
        )

        log(
            f"USER ID: {user_id}"
        )

        log(
            f"ТИПАЖ: {archetype}"
        )

        log(
            f"КНИГА: {book_title}"
        )

        log(
            f"MATCH: {match}"
        )

        # ----------------------------------------------------
        # ОТПРАВЛЯЕМ КНИГУ
        # ----------------------------------------------------

        success = send_book(
            user_id,
            book_title
        )

        if success:

            log(
                "РЕЗУЛЬТАТ УСПЕШНО ОБРАБОТАН"
            )

            return jsonify({
                "ok": True,
                "sent": True,
                "book": book_title
            })

        log(
            "КНИГА НЕ БЫЛА ОТПРАВЛЕНА"
        )

        return jsonify({
            "ok": False,
            "sent": False,
            "error":
                "book_not_sent"
        }), 500

    except Exception as e:

        log(
            f"ОШИБКА /submit-result: {e}"
        )

        return jsonify({
            "ok": False,
            "error":
                str(e)
        }), 500


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

    log("")
    log("=" * 70)
    log("НОВЫЙ TELEGRAM UPDATE")
    log("=" * 70)

    log(
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

        pre_checkout_id = (
            pre_checkout.get("id")
        )

        log(
            f"PRE-CHECKOUT: "
            f"{pre_checkout_id}"
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

        callback_data = callback.get(
            "data",
            ""
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

        log(
            f"CALLBACK: {callback_data}"
        )

        tg(
            "answerCallbackQuery",
            {
                "callback_query_id":
                    callback_id
            }
        )

        # ----------------------------------------------------
        # ПОКУПКА
        # ----------------------------------------------------

        if callback_data == "buy_test":

            if not chat_id:

                return "ok"

            tg(
                "sendInvoice",
                {
                    "chat_id":
                        chat_id,

                    "title":
                        "Book Quiz",

                    "description":
                        "Одно прохождение психологического теста «Какая книга тебя ждёт?»",

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
                                    PRICE_STARS
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

    chat = message.get(
        "chat",
        {}
    )

    chat_id = chat.get(
        "id"
    )

    if not chat_id:

        return "ok"

    user_id = str(
        chat_id
    )

    # ========================================================
    # УСПЕШНАЯ ОПЛАТА
    # ========================================================

    successful_payment = message.get(
        "successful_payment"
    )

    if successful_payment:

        log(
            f"ОПЛАТА ПОЛУЧЕНА: "
            f"{user_id}"
        )

        add_paid_user(
            user_id
        )

        send_text(
            chat_id,
            (
                "✅ Оплата прошла!\n\n"
                "Тест разблокирован.\n\n"
                "Нажимай кнопку и проходи тест 👇"
            ),
            quiz_button()
        )

        return "ok"

    # ========================================================
    # WEB APP DATA
    #
    # ОСТАВЛЯЕМ ДЛЯ СОВМЕСТИМОСТИ
    # ========================================================

    web_app_data = message.get(
        "web_app_data"
    )

    if web_app_data:

        log(
            "WEB APP DATA ПОЛУЧЕН"
        )

        raw_data = web_app_data.get(
            "data",
            ""
        )

        if raw_data:

            try:

                result = json.loads(
                    raw_data
                )

                log(
                    "WEB APP RESULT:"
                )

                log(
                    json.dumps(
                        result,
                        ensure_ascii=False
                    )[:5000]
                )

                if (
                    result.get("action")
                    == "quiz_result"
                ):

                    if is_paid(user_id):

                        book_title = result.get(
                            "book",
                            ""
                        )

                        if book_title:

                            send_book(
                                user_id,
                                book_title
                            )

            except Exception as e:

                log(
                    f"Ошибка WEB APP DATA: {e}"
                )

        return "ok"

    # ========================================================
    # TEXT
    # ========================================================

    text = message.get(
        "text",
        ""
    ).strip()

    # ========================================================
    # TESTPAY
    # ========================================================

    if text == "/testpay":

        add_paid_user(
            user_id
        )

        send_text(
            chat_id,
            (
                "🧪 ТЕСТОВАЯ ОПЛАТА АКТИВИРОВАНА.\n\n"
                "Твой Telegram ID добавлен "
                "в список оплативших.\n\n"
                "Теперь можешь проходить тест 👇"
            ),
            quiz_button()
        )

        return "ok"

    # ========================================================
    # START
    # ========================================================

    if text.startswith("/start"):

        if is_paid(user_id):

            send_text(
                chat_id,
                (
                    "📚 Book Quiz\n\n"
                    "Тест уже разблокирован.\n"
                    "Можешь проходить 👇"
                ),
                quiz_button()
            )

        else:

            send_text(
                chat_id,
                (
                    "📚 Book Quiz\n\n"
                    "Пройди тест и узнай, "
                    "какая книга подходит именно тебе.\n\n"
                    f"🔓 Стоимость прохождения — "
                    f"{PRICE_STARS} ⭐"
                ),
                buy_button()
            )

        return "ok"

    return "ok"


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":

    books = load_books()

    log("")
    log("=" * 70)
    log("BOOK QUIZ BOT STARTING")
    log("=" * 70)

    log(
        f"PORT: "
        f"{os.environ.get('PORT', '10000')}"
    )

    log(
        f"WEB APP: {WEB_APP_URL}"
    )

    log(
        f"DATABASE: {DATABASE_FILE}"
    )

    log(
        f"BOOKS: {BOOKS_DIR}"
    )

    log(
        f"BOOKS IN DATABASE: {len(books)}"
    )

    log(
        f"PAID USERS: {len(PAID_USERS)}"
    )

    log("=" * 70)

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                "10000"
            )
        )
    )
```
