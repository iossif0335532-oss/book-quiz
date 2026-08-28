import os
import json
import requests

from flask import Flask, request

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

app = Flask(**name**)

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

```
    log(
        f"Telegram {method}: "
        f"{response.status_code} "
        f"{response.text[:1500]}"
    )

    try:
        return response.json()
    except Exception:
        return {}

except Exception as e:
    log(f"Telegram ERROR {method}: {e}")
    return {}
```

# ============================================================

# ОПЛАЧЕННЫЕ ПОЛЬЗОВАТЕЛИ

# ============================================================

def load_paid_users():
try:
if not os.path.exists(PAID_USERS_FILE):
return set()

```
    with open(
        PAID_USERS_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)

    if not isinstance(data, list):
        return set()

    return {str(user_id) for user_id in data}

except Exception as e:
    log(f"Ошибка загрузки paid_users: {e}")
    return set()
```

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

```
    log(
        f"PAID USERS сохранены: {len(users)}"
    )

except Exception as e:
    log(
        f"Ошибка сохранения paid_users: {e}"
    )
```

PAID_USERS = load_paid_users()

def add_paid_user(user_id):
user_id = str(user_id)

```
PAID_USERS.add(user_id)

save_paid_users(PAID_USERS)

log(
    f"Пользователь добавлен "
    f"в PAID_USERS: {user_id}"
)
```

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

```
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
```

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

```
if not wanted:
    return None

books = load_books()

# 1. Точное совпадение

for book in books:

    book_title = normalize(
        book.get("title", "")
    )

    if book_title == wanted:
        return book

# 2. Совпадение без знаков

wanted_clean = (
    wanted
    .replace("(", "")
    .replace(")", "")
    .replace('"', "")
    .replace("'", "")
    .replace("«", "")
    .replace("»", "")
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
        .replace("«", "")
        .replace("»", "")
    )

    if book_title_clean == wanted_clean:
        return book

# 3. Частичное совпадение

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
```

# ============================================================

# ПОЛУЧЕНИЕ ИМЕНИ PDF

# ============================================================

def get_book_filename(book):

```
filename = str(
    book.get("filename", "")
).strip()

if filename:
    return filename

filepath = str(
    book.get("filepath", "")
).strip()

if filepath:

    filepath = filepath.replace(
        "\\",
        "/"
    )

    return filepath.split("/")[-1]

return ""
```

# ============================================================

# ПОИСК PDF

# ============================================================

def find_pdf(book):

```
filename = get_book_filename(book)

if not filename:

    log(
        "У книги отсутствует filename "
        "и filepath"
    )

    return None

log(
    f"Ищем PDF: {filename}"
)

# 1. books/filename

direct_path = os.path.join(
    BOOKS_DIR,
    filename
)

if os.path.isfile(direct_path):

    log(
        f"PDF найден: {direct_path}"
    )

    return direct_path

# 2. Корень проекта

root_path = filename

if os.path.isfile(root_path):

    log(
        f"PDF найден в корне: "
        f"{root_path}"
    )

    return root_path

# 3. Рекурсивный поиск

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
```

# ============================================================

# ОТПРАВКА ТЕКСТА

# ============================================================

def send_text(
chat_id,
text,
reply_markup=None
):

```
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
```

# ============================================================

# КНОПКА ТЕСТА

# ============================================================

def quiz_button():

```
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
```

# ============================================================

# КНОПКА ОПЛАТЫ

# ============================================================

def buy_button():

```
return {
    "inline_keyboard": [
        [
            {
                "text": (
                    f"🔓 Купить тест — "
                    f"{PRICE_STARS} ⭐"
                ),
                "callback_data": "buy_test"
            }
        ]
    ]
}
```

# ============================================================

# ОТПРАВКА КНИГИ

# ============================================================

def send_book(chat_id, title):

```
log("")
log("=" * 70)
log("ОТПРАВКА КНИГИ")
log("=" * 70)

log(
    f"Результат теста: {title}"
)

# --------------------------------------------------------
# ИЩЕМ КНИГУ В БАЗЕ
# --------------------------------------------------------

book = find_book(title)

if not book:

    log(
        f"Книга НЕ найдена в базе: "
        f"{title}"
    )

    send_text(
        chat_id,
        (
            "⚠️ Тест завершён, "
            "но я не нашёл эту книгу "
            "в базе.\n\n"
            f"📕 {title}\n\n"
            "Проверь название книги "
            "в recommendation_database.json."
        )
    )

    return False

# --------------------------------------------------------
# ДАННЫЕ КНИГИ
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

filename = get_book_filename(book)

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
# ИЩЕМ PDF
# --------------------------------------------------------

pdf_path = find_pdf(book)

if not pdf_path:

    log(
        "PDF НЕ НАЙДЕН"
    )

    send_text(
        chat_id,
        (
            "🎉 Тест завершён!\n\n"
            f"📕 Твоя книга:\n"
            f"{real_title}\n\n"
            "Но PDF этой книги "
            "не найден на сервере.\n\n"
            f"Искомый файл:\n"
            f"{filename}\n\n"
            "Проверь, что PDF находится "
            "в папке books."
        )
    )

    return False

# --------------------------------------------------------
# CAPTION
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

# --------------------------------------------------------
# ОТПРАВЛЯЕМ PDF
# --------------------------------------------------------

try:

    with open(
        pdf_path,
        "rb"
    ) as document:

        response = requests.post(
            f"{API}/sendDocument",

            data={
                "chat_id": str(chat_id),
                "caption": caption
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
        f"{response.text[:1500]}"
    )

    if response.ok:

        log(
            "КНИГА УСПЕШНО ОТПРАВЛЕНА"
        )

        return True

    send_text(
        chat_id,
        (
            "⚠️ PDF найден, "
            "но Telegram не смог "
            "его отправить.\n\n"
            f"Ошибка:\n"
            f"{response.text[:1000]}"
        )
    )

    return False

except Exception as e:

    log(
        f"Ошибка отправки PDF: {e}"
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
```

# ============================================================

# ГЛАВНАЯ

# ============================================================

@app.route("/")
def home():

```
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
```

# ============================================================

# HEALTH

# ============================================================

@app.route("/health")
def health():

```
return "OK"
```

# ============================================================

# CHECK ACCESS

# ============================================================

@app.route("/check-access")
def check_access():

```
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
```

# ============================================================

# TESTPAY

# ============================================================

@app.route("/testpay")
def testpay():

```
user_id = request.args.get(
    "user_id",
    ""
).strip()

if not user_id:

    return (
        "OK\n\n"
        "Используй:\n"
        "/testpay?user_id=ТВОЙ_ID"
    )

add_paid_user(
    user_id
)

return (
    "OK\n\n"
    "Доступ выдан.\n"
    f"user_id={user_id}"
)
```

# ============================================================

# WEBHOOK

# ============================================================

@app.route(
"/webhook",
methods=["POST"]
)
def webhook():

```
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
    )[:15000]
)

# ========================================================
# PRE CHECKOUT
# ========================================================

pre_checkout = update.get(
    "pre_checkout_query"
)

if pre_checkout:

    pre_checkout_id = pre_checkout.get(
        "id"
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
        f"CALLBACK: "
        f"{callback_data}"
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
                    (
                        "Одно прохождение "
                        "психологического теста "
                        "«Какая книга тебя ждёт?»"
                    ),

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
            "Нажимай кнопку и проходи "
            "тест 👇"
        ),
        quiz_button()
    )

    return "ok"


# ========================================================
# WEB APP DATA
# ========================================================

web_app_data = message.get(
    "web_app_data"
)

if web_app_data:

    log("")
    log("=" * 70)
    log("WEB APP DATA ПОЛУЧЕН")
    log("=" * 70)

    log(
        json.dumps(
            web_app_data,
            ensure_ascii=False
        )[:10000]
    )

    # ----------------------------------------------------
    # ПРОВЕРКА ОПЛАТЫ
    # ----------------------------------------------------

    if not is_paid(user_id):

        log(
            "ПОЛЬЗОВАТЕЛЬ НЕ ОПЛАЧИВАЛ"
        )

        send_text(
            chat_id,
            (
                "🔒 Тест не оплачен.\n\n"
                "Сначала приобрети "
                f"прохождение за "
                f"{PRICE_STARS} ⭐."
            ),
            buy_button()
        )

        return "ok"

    # ----------------------------------------------------
    # DATA
    # ----------------------------------------------------

    raw_data = web_app_data.get(
        "data",
        ""
    )

    if not raw_data:

        log(
            "WEB APP DATA ПУСТОЙ"
        )

        send_text(
            chat_id,
            "⚠️ Тест не передал результат."
        )

        return "ok"

    log(
        f"RAW DATA: {raw_data}"
    )

    # ----------------------------------------------------
    # JSON
    # ----------------------------------------------------

    try:

        result = json.loads(
            raw_data
        )

    except Exception as e:

        log(
            f"Ошибка JSON: {e}"
        )

        send_text(
            chat_id,
            (
                "⚠️ Не удалось прочитать "
                "результат теста."
            )
        )

        return "ok"

    log("")
    log("РАЗОБРАННЫЙ РЕЗУЛЬТАТ:")

    log(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )[:10000]
    )

    # ----------------------------------------------------
    # ACTION
    # ----------------------------------------------------

    action = result.get(
        "action"
    )

    if action != "quiz_result":

        log(
            f"НЕИЗВЕСТНОЕ ACTION: "
            f"{action}"
        )

        send_text(
            chat_id,
            (
                "⚠️ Получен неизвестный "
                "результат теста."
            )
        )

        return "ok"

    # ----------------------------------------------------
    # КНИГА
    # ----------------------------------------------------

    book_title = str(
        result.get(
            "book",
            ""
        )
    ).strip()

    archetype = str(
        result.get(
            "archetype",
            ""
        )
    ).strip()

    match = result.get(
        "match",
        ""
    )

    log(
        f"Типаж: {archetype}"
    )

    log(
        f"Книга: {book_title}"
    )

    log(
        f"Совпадение: {match}"
    )

    if not book_title:

        send_text(
            chat_id,
            (
                "⚠️ В результате "
                "теста не указана книга."
            )
        )

        return "ok"

    # ----------------------------------------------------
    # ОТПРАВКА КНИГИ
    # ----------------------------------------------------

    success = send_book(
        chat_id,
        book_title
    )

    if success:

        log(
            "ГОТОВО: книга отправлена."
        )

    else:

        log(
            "Книга не отправлена."
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
# /TESTPAY
# ========================================================

if text == "/testpay":

    add_paid_user(
        user_id
    )

    send_text(
        chat_id,
        (
            "🧪 ТЕСТОВАЯ ОПЛАТА "
            "АКТИВИРОВАНА.\n\n"
            "Твой Telegram ID добавлен "
            "в список оплативших.\n\n"
            "Теперь можешь проходить "
            "тест 👇"
        ),
        quiz_button()
    )

    return "ok"


# ========================================================
# /START
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
                "какая книга подходит "
                "именно тебе.\n\n"
                f"🔓 Стоимость прохождения — "
                f"{PRICE_STARS} ⭐"
            ),
            buy_button()
        )

    return "ok"


# ========================================================
# НЕИЗВЕСТНАЯ КОМАНДА
# ========================================================

return "ok"
```

# ============================================================

# START

# ============================================================

if **name** == "**main**":

```
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
    f"WEB APP: "
    f"{WEB_APP_URL}"
)

log(
    f"DATABASE: "
    f"{DATABASE_FILE}"
)

log(
    f"BOOKS: "
    f"{BOOKS_DIR}"
)

log(
    f"BOOKS IN DATABASE: "
    f"{len(books)}"
)

log(
    f"PAID USERS: "
    f"{len(PAID_USERS)}"
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
