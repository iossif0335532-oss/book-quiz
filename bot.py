import os
import json
import requests

from flask import Flask, request

TOKEN = os.environ["BOT_TOKEN"]

API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(name)

PAID_USERS_FILE = "paid_users.json"
DATABASE_FILE = "recommendation_database.json"
BOOKS_DIR = "books"

WEB_APP_URL = "https://book-quiz.onrender.com"

PRICE_XTR = 200

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
    print("PAID USERS сохранены:", len(users))

except Exception as e:
    print("Ошибка сохранения paid_users:", e)
```

PAID_USERS = load_paid_users()

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

def load_books():
try:
if not os.path.exists(DATABASE_FILE):
print("ОШИБКА: база книг не найдена:", DATABASE_FILE)
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

    print("Книг загружено:", len(books))

    return books

except Exception as e:
    print("ОШИБКА загрузки базы книг:", e)
    return []
```

def normalize_text(value):
return " ".join(
str(value or "")
.strip()
.lower()
.split()
)

def find_book(title):
requested_title = normalize_text(title)

```
if not requested_title:
    return None

books = load_books()

print("Ищем книгу:", requested_title)

# 1. Точное совпадение названия
for book in books:
    book_title = normalize_text(
        book.get("title", "")
    )

    if book_title == requested_title:
        print(
            "КНИГА НАЙДЕНА — точное совпадение:",
            book.get("title")
        )
        return book

# 2. Название из результата содержится в названии книги
for book in books:
    book_title = normalize_text(
        book.get("title", "")
    )

    if requested_title in book_title:
        print(
            "КНИГА НАЙДЕНА — частичное совпадение:",
            book.get("title")
        )
        return book

# 3. Название книги содержится в результате
for book in books:
    book_title = normalize_text(
        book.get("title", "")
    )

    if book_title and book_title in requested_title:
        print(
            "КНИГА НАЙДЕНА — обратное частичное совпадение:",
            book.get("title")
        )
        return book

print("КНИГА НЕ НАЙДЕНА:", title)

return None
```

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

def find_pdf(book):
filename = get_book_filename(book)

```
if not filename:
    print("У книги нет filename/filepath")
    return None

print("Ищем PDF:", filename)

# books/filename.pdf
direct_path = os.path.join(
    BOOKS_DIR,
    filename
)

if os.path.isfile(direct_path):
    print("PDF найден:", direct_path)
    return direct_path

# рядом с bot.py
if os.path.isfile(filename):
    print("PDF найден рядом с bot.py:", filename)
    return filename

# рекурсивный поиск внутри books
if os.path.isdir(BOOKS_DIR):

    for root, dirs, files in os.walk(BOOKS_DIR):

        for file in files:

            if file == filename:

                path = os.path.join(
                    root,
                    file
                )

                print("PDF найден рекурсивно:", path)

                return path

# Дополнительный поиск без учета регистра
if os.path.isdir(BOOKS_DIR):

    target = filename.lower()

    for root, dirs, files in os.walk(BOOKS_DIR):

        for file in files:

            if file.lower() == target:

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

def send_book(chat_id, book_title):
print()
print("=" * 70)
print("НАЧИНАЕМ ОТПРАВКУ КНИГИ")
print("Chat ID:", chat_id)
print("Результат теста:", book_title)
print("=" * 70)

```
book = find_book(book_title)

if not book:

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "🎉 Тест завершён!\n\n"
                f"📕 Твоя книга:\n{book_title}\n\n"
                "⚠️ Я не смог найти эту книгу "
                "в базе recommendation_database.json."
            )
        }
    )

    return False

real_title = str(
    book.get("title", book_title)
).strip()

author = str(
    book.get("author", "")
).strip()

filename = get_book_filename(book)

pdf_path = find_pdf(book)

print("Название:", real_title)
print("Автор:", author)
print("Filename:", filename)
print("PDF path:", pdf_path)

if not pdf_path:

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "🎉 Тест завершён!\n\n"
                f"📕 Твоя книга:\n{real_title}\n"
                + (
                    f"✍️ {author}\n"
                    if author
                    else ""
                )
                + "\n"
                "⚠️ Книга есть в базе, "
                "но соответствующий PDF "
                "не найден в папке books."
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
                "document": document
            },
            timeout=180
        )

    print()
    print("SEND DOCUMENT")
    print("Status:", response.status_code)
    print("Response:", response.text[:2000])

    if response.ok:

        print("КНИГА УСПЕШНО ОТПРАВЛЕНА:", real_title)

        return True

    print("ОШИБКА TELEGRAM ПРИ ОТПРАВКЕ КНИГИ")

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "⚠️ Книга найдена, "
                "но Telegram не смог принять PDF."
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
                "⚠️ Произошла ошибка "
                "при отправке книги."
            )
        }
    )

    return False
```

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

    print("Ошибка index.html:", e)

    return (
        "Book Quiz\n\n"
        "Ошибка загрузки приложения."
    ), 500
```

@app.route("/health")
def health():
return "OK"

@app.route("/check-access")
def check_access():

```
user_id = request.args.get(
    "user_id",
    ""
)

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
```

@app.route(
"/webhook",
methods=["POST"]
)
def webhook():

```
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


# ==========================================================
# CALLBACK QUERY
# ==========================================================

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

    chat_id = callback_message.get(
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
        data,
        "CHAT:",
        chat_id
    )

    # ------------------------------------------------------
    # ПОКУПКА ТЕСТА
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
                                PRICE_XTR
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

if not chat_id:
    return "ok"


# ==========================================================
# УСПЕШНАЯ ОПЛАТА
# ==========================================================

successful_payment = message.get(
    "successful_payment"
)

if successful_payment:

    user_id = str(chat_id)

    print()
    print("=" * 70)
    print("УСПЕШНАЯ ОПЛАТА")
    print("USER:", user_id)
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
                    "Нажимай кнопку ниже и проходи тест 👇"
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


# ==========================================================
# WEB APP DATA
# ==========================================================

web_app_data = message.get(
    "web_app_data"
)

if web_app_data:

    user_id = str(chat_id)

    print()
    print("=" * 70)
    print("ПОЛУЧЕН РЕЗУЛЬТАТ MINI APP")
    print("USER:", user_id)
    print("=" * 70)

    print(
        json.dumps(
            web_app_data,
            ensure_ascii=False
        )[:5000]
    )

    # ------------------------------------------------------
    # ПРОВЕРКА ОПЛАТЫ
    # ------------------------------------------------------

    if user_id not in PAID_USERS:

        print(
            "БЕЗ ОПЛАТЫ — РЕЗУЛЬТАТ НЕ ОБРАБАТЫВАЕМ"
        )

        tg(
            "sendMessage",
            {
                "chat_id":
                    chat_id,

                "text":
                    (
                        "🔒 Тест заблокирован.\n\n"
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


    # ------------------------------------------------------
    # ЧИТАЕМ ДАННЫЕ ТЕСТА
    # ------------------------------------------------------

    raw_data = web_app_data.get(
        "data",
        ""
    )

    if not raw_data:

        print(
            "WEB APP DATA ПУСТОЙ"
        )

        tg(
            "sendMessage",
            {
                "chat_id":
                    chat_id,

                "text":
                    "⚠️ Тест не передал результат."
            }
        )

        return "ok"


    try:

        result = json.loads(
            raw_data
        )

    except Exception as e:

        print(
            "ОШИБКА JSON:",
            e
        )

        print(
            "RAW DATA:",
            raw_data
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
        "РЕЗУЛЬТАТ JSON:",
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )[:10000]
    )


    action = result.get(
        "action"
    )

    if action != "quiz_result":

        print(
            "НЕИЗВЕСТНОЕ ACTION:",
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
    print("=" * 70)
    print("РЕЗУЛЬТАТ ТЕСТА")
    print("Типаж:", archetype)
    print("Книга:", book_title)
    print("Совпадение:", match)
    print("=" * 70)


    if not book_title:

        tg(
            "sendMessage",
            {
                "chat_id":
                    chat_id,

                "text":
                    (
                        "⚠️ Тест завершён, "
                        "но название книги не передалось."
                    )
            }
        )

        return "ok"


    # ------------------------------------------------------
    # ОТПРАВЛЯЕМ КНИГУ ИЗ БАЗЫ
    # ------------------------------------------------------

    send_book(
        chat_id,
        book_title
    )

    return "ok"


# ==========================================================
# /START
# ==========================================================

text = message.get(
    "text",
    ""
).strip()

if text == "/start":

    user_id = str(chat_id)

    print(
        "START:",
        user_id
    )

    # ------------------------------------------------------
    # УЖЕ ОПЛАЧЕНО
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
                        "Тест уже разблокирован.\n\n"
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


    # ------------------------------------------------------
    # НЕ ОПЛАЧЕНО
    # ------------------------------------------------------

    tg(
        "sendMessage",
        {
            "chat_id":
                chat_id,

            "text":
                (
                    "📚 Book Quiz\n\n"
                    "Пройди психологический тест "
                    "и узнай, какая книга подходит "
                    "именно тебе.\n\n"
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

if **name** == "**main**":

```
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
print()

app.run(
    host="0.0.0.0",
    port=port
)
```
