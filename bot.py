import os
import json
import requests
from flask import Flask, request

TOKEN = os.environ["BOT_TOKEN"]

API = f"https://api.telegram.org/bot{TOKEN}"

WEB_APP_URL = "https://book-quiz.onrender.com"

PAID_USERS_FILE = "paid_users.json"
DATABASE_FILE = "recommendation_database.json"
BOOKS_DIR = "books"

app = Flask(**name**)

# ============================================================

# ПОЛЬЗОВАТЕЛИ С ДОСТУПОМ

# ============================================================

def load_paid_users():
try:
if not os.path.exists(PAID_USERS_FILE):
return set()

```
    with open(PAID_USERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        return set()

    return set(str(x) for x in data)

except Exception as e:
    print("Ошибка загрузки paid_users:", e)
    return set()
```

def save_paid_users(users):
try:
with open(PAID_USERS_FILE, "w", encoding="utf-8") as f:
json.dump(
list(users),
f,
ensure_ascii=False,
indent=2
)

```
except Exception as e:
    print("Ошибка сохранения paid_users:", e)
```

PAID_USERS = load_paid_users()

# ============================================================

# TELEGRAM API

# ============================================================

def tg(method, data):
try:
response = requests.post(
f"{API}/{method}",
json=data,
timeout=30
)

```
    print()
    print("Telegram:", method)
    print("Status:", response.status_code)
    print("Response:", response.text[:1000])

    return response.json()

except Exception as e:
    print("Telegram ERROR:", method, e)
    return {}
```

# ============================================================

# БАЗА КНИГ

# ============================================================

def load_books():
try:
if not os.path.exists(DATABASE_FILE):
print("База книг не найдена:", DATABASE_FILE)
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

    print("Книг загружено из базы:", len(books))

    return books

except Exception as e:
    print("Ошибка загрузки базы книг:", e)
    return []
```

# ============================================================

# НОРМАЛИЗАЦИЯ НАЗВАНИЯ

# ============================================================

def normalize_text(text):
text = str(text or "").strip().lower()

```
replacements = {
    "ё": "е",
    "–": "-",
    "—": "-",
    "«": "",
    "»": "",
    '"': "",
    "'": ""
}

for old, new in replacements.items():
    text = text.replace(old, new)

return " ".join(text.split())
```

# ============================================================

# ПОИСК КНИГИ

# ============================================================

def find_book(title):
wanted = normalize_text(title)

```
if not wanted:
    return None

books = load_books()

# 1. Точное совпадение
for book in books:
    book_title = normalize_text(
        book.get("title", "")
    )

    if book_title == wanted:
        print("НАЙДЕНО ТОЧНО:", book_title)
        return book

# 2. Название входит в название книги
for book in books:
    book_title = normalize_text(
        book.get("title", "")
    )

    if wanted in book_title:
        print("НАЙДЕНО ПО ВХОЖДЕНИЮ:", book_title)
        return book

# 3. Название книги входит в результат теста
for book in books:
    book_title = normalize_text(
        book.get("title", "")
    )

    if book_title and book_title in wanted:
        print("НАЙДЕНО ОБРАТНЫМ ВХОЖДЕНИЕМ:", book_title)
        return book

print("КНИГА НЕ НАЙДЕНА:", title)

return None
```

# ============================================================

# ПОЛУЧЕНИЕ ИМЕНИ PDF

# ============================================================

def get_book_filename(book):
filename = str(
book.get("filename", "")
).strip()

```
if filename:
    return filename

filepath = str(
    book.get("filepath", "")
).strip()

if filepath:
    filepath = filepath.replace("\\", "/")
    return filepath.split("/")[-1]

return ""
```

# ============================================================

# ПОИСК PDF

# ============================================================

def find_pdf(book):
filename = get_book_filename(book)

```
if not filename:
    print("У книги нет filename")
    return None

# 1. books/filename.pdf
direct_path = os.path.join(
    BOOKS_DIR,
    filename
)

if os.path.isfile(direct_path):
    print("PDF найден:", direct_path)
    return direct_path

# 2. filename рядом с bot.py
if os.path.isfile(filename):
    print("PDF найден:", filename)
    return filename

# 3. Рекурсивный поиск внутри books
if os.path.exists(BOOKS_DIR):
    for root, dirs, files in os.walk(BOOKS_DIR):

        for file in files:

            if file == filename:
                path = os.path.join(
                    root,
                    file
                )

                print("PDF найден рекурсивно:", path)

                return path

# 4. Попробуем сравнить имена без учета регистра
wanted_filename = filename.lower()

if os.path.exists(BOOKS_DIR):

    for root, dirs, files in os.walk(BOOKS_DIR):

        for file in files:

            if file.lower() == wanted_filename:

                path = os.path.join(
                    root,
                    file
                )

                print(
                    "PDF найден без учета регистра:",
                    path
                )

                return path

print("PDF НЕ НАЙДЕН:", filename)

return None
```

# ============================================================

# ОТПРАВКА КНИГИ

# ============================================================

def send_book(chat_id, title):

```
print()
print("=" * 60)
print("НАЧИНАЕМ ВЫДАЧУ КНИГИ")
print("Результат теста:", title)
print("=" * 60)

book = find_book(title)

if not book:

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "⚠️ Тест завершён.\n\n"
                f"📕 Твоя книга: {title}\n\n"
                "Я нашёл название в результате теста, "
                "но не нашёл эту книгу в базе."
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

filename = get_book_filename(book)

pdf_path = find_pdf(book)

print("Название:", real_title)
print("Автор:", author)
print("Filename:", filename)
print("PDF:", pdf_path)

if not pdf_path:

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "🎉 Тест завершён!\n\n"
                f"📕 {real_title}\n\n"
                "Книга есть в базе, "
                "но PDF-файл не найден на сервере.\n\n"
                f"Ожидаемый файл:\n{filename}"
            )
        }
    )

    return False

try:

    with open(
        pdf_path,
        "rb"
    ) as document:

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

            timeout=180
        )

    print()
    print("ОТПРАВКА PDF")
    print("Status:", response.status_code)
    print("Response:", response.text[:1000])

    return response.ok

except Exception as e:

    print("ОШИБКА ОТПРАВКИ PDF:", e)

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
```

# ============================================================

# ГЛАВНАЯ СТРАНИЦА

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
return "OK"

# ============================================================

# ПРОВЕРКА ДОСТУПА

# ============================================================

@app.route("/check-access")
def check_access():

```
user_id = request.args.get(
    "user_id",
    ""
)

if not user_id:
    return {"paid": False}

return {
    "paid": str(user_id) in PAID_USERS
}
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
update = request.json or {}

print()
print("=" * 70)
print("НОВЫЙ UPDATE")
print("=" * 70)

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

    pre_checkout_id = pre_checkout.get("id")

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
# CALLBACK
# ========================================================

callback = update.get(
    "callback_query"
)

if callback:

    callback_id = callback.get("id")

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

        result = tg(
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

        print(
            "SEND INVOICE RESULT:",
            result
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

if not chat_id:
    return "ok"

user_id = str(chat_id)

# ========================================================
# УСПЕШНАЯ ОПЛАТА
# ========================================================

successful_payment = message.get(
    "successful_payment"
)

if successful_payment:

    print()
    print("ОПЛАТА ПОЛУЧЕНА:", user_id)

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
# /TESTPAY
# БЕСПЛАТНЫЙ ТЕСТОВЫЙ ДОСТУП
# ========================================================

text = message.get(
    "text",
    ""
).strip()

if text == "/testpay":

    print()
    print(
        "ТЕСТОВЫЙ ДОСТУП:",
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
                    "🧪 Тестовый доступ включён!\n\n"
                    "Оплата не требуется.\n\n"
                    "Проходи тест 👇"
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
# WEB APP DATA
# ========================================================

web_app_data = message.get(
    "web_app_data"
)

if web_app_data:

    print()
    print(
        "WEB APP DATA:",
        web_app_data
    )

    # ----------------------------------------------------
    # ПРОВЕРКА ДОСТУПА
    # ----------------------------------------------------

    if user_id not in PAID_USERS:

        print(
            "ПОПЫТКА ПЕРЕДАТЬ РЕЗУЛЬТАТ "
            "БЕЗ ОПЛАТЫ:",
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

    # ----------------------------------------------------
    # ПОЛУЧАЕМ РЕЗУЛЬТАТ
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

    action = result.get(
        "action"
    )

    if action != "quiz_result":

        print(
            "НЕИЗВЕСТНОЕ ДЕЙСТВИЕ:",
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

    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТ ТЕСТА")
    print("Типаж:", archetype)
    print("Книга:", book_title)
    print("Совпадение:", match)
    print("=" * 60)

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
# START
# ========================================================

if text == "/start":

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

return "ok"
```

# ============================================================

# ЗАПУСК

# ============================================================

if **name** == "**main**":

```
print("=" * 70)
print("BOOK QUIZ BOT STARTING")
print("PORT:", os.environ.get("PORT", "10000"))
print("WEB APP:", WEB_APP_URL)
print("DATABASE:", DATABASE_FILE)
print("BOOKS:", BOOKS_DIR)
print("PAID USERS:", len(PAID_USERS))
print("=" * 70)

app.run(
    host="0.0.0.0",
    port=int(
        os.environ.get(
            "PORT",
            10000
        )
    )
)
```
