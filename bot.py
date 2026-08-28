import os
import json
import requests

from flask import Flask, request

TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
raise RuntimeError("BOT_TOKEN не задан в переменных окружения Render")

API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(**name**)

DATABASE_FILE = "recommendation_database.json"
PAID_USERS_FILE = "paid_users.json"
BOOKS_DIR = "books"

WEB_APP_URL = "https://book-quiz.onrender.com"
PRICE_STARS = 200

# ============================================================

# TELEGRAM API

# ============================================================

def tg(method, data=None):
try:
response = requests.post(
f"{API}/{method}",
json=data or {},
timeout=60
)

```
    print(f"Telegram {method}: {response.status_code}")
    print(response.text[:2000])

    return response.json()

except Exception as e:
    print(f"Telegram ERROR {method}: {e}")
    return {}
```

# ============================================================

# ОПЛАТИВШИЕ ПОЛЬЗОВАТЕЛИ

# ============================================================

def load_paid_users():
if not os.path.exists(PAID_USERS_FILE):
return set()

```
try:
    with open(PAID_USERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return {str(x) for x in data}

    return set()

except Exception as e:
    print("Ошибка загрузки paid_users:", e)
    return set()
```

def save_paid_users(users):
try:
with open(PAID_USERS_FILE, "w", encoding="utf-8") as f:
json.dump(
sorted(list(users)),
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

# БАЗА КНИГ

# ============================================================

def load_books():
if not os.path.exists(DATABASE_FILE):
print("База книг не найдена:", DATABASE_FILE)
return []

```
try:
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

    print(f"Загружено книг из базы: {len(books)}")

    return books

except Exception as e:
    print("Ошибка загрузки базы книг:", e)
    return []
```

# ============================================================

# ПОИСК КНИГИ

# ============================================================

def normalize_text(value):
return " ".join(
str(value or "")
.strip()
.lower()
.replace("ё", "е")
.split()
)

def find_book(title):
if not title:
return None

```
wanted = normalize_text(title)

if not wanted:
    return None

books = load_books()

# 1. Точное совпадение названия
for book in books:
    book_title = normalize_text(
        book.get("title", "")
    )

    if book_title == wanted:
        return book

# 2. Частичное совпадение
for book in books:
    book_title = normalize_text(
        book.get("title", "")
    )

    if not book_title:
        continue

    if wanted in book_title or book_title in wanted:
        return book

# 3. Поиск по filename без .pdf
wanted_filename = wanted.replace(".pdf", "")

for book in books:
    filename = normalize_text(
        book.get("filename", "")
    )

    filename_without_pdf = filename.replace(".pdf", "")

    if (
        wanted_filename
        and wanted_filename == filename_without_pdf
    ):
        return book

return None
```

# ============================================================

# ИМЯ PDF

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
    return None

# books/filename.pdf
direct_path = os.path.join(
    BOOKS_DIR,
    filename
)

if os.path.isfile(direct_path):
    return direct_path

# filename.pdf рядом с bot.py
if os.path.isfile(filename):
    return filename

# Рекурсивный поиск внутри books
if os.path.isdir(BOOKS_DIR):
    for root, dirs, files in os.walk(BOOKS_DIR):
        for file in files:
            if file == filename:
                return os.path.join(root, file)

return None
```

# ============================================================

# ОТПРАВКА PDF

# ============================================================

def send_book(chat_id, title):
print("=" * 60)
print("ЗАПРОС НА КНИГУ")
print("Пользователь:", chat_id)
print("Название из теста:", title)
print("=" * 60)

```
book = find_book(title)

if not book:
    print("КНИГА НЕ НАЙДЕНА В БАЗЕ:", title)

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "⚠️ Результат теста получен.\n\n"
                f"📕 Книга: {title}\n\n"
                "Но этой книги нет в recommendation_database.json."
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

print("Книга из базы:", real_title)
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
                f"📕 {real_title}\n"
                + (
                    f"✍️ {author}\n\n"
                    if author
                    else "\n"
                )
                + (
                    "Книга есть в базе, "
                    "но PDF-файл не найден на сервере.\n\n"
                    f"Ожидаемый файл: {filename}"
                )
            )
        }
    )

    return False

try:
    caption = (
        "🎉 Твой результат готов!\n\n"
        f"📕 {real_title}"
    )

    if author:
        caption += f"\n✍️ {author}"

    caption += "\n\nПриятного чтения! 📚"

    with open(pdf_path, "rb") as document:
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
        response.status_code,
        response.text[:2000]
    )

    if response.ok:
        print("КНИГА УСПЕШНО ОТПРАВЛЕНА")
        return True

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "⚠️ Не удалось отправить PDF.\n\n"
                f"Telegram ответил: {response.text[:500]}"
            )
        }
    )

    return False

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
```

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

```
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
user_id = request.args.get("user_id", "")

```
if not user_id:
    return {"paid": False}

return {
    "paid": str(user_id) in PAID_USERS
}
```

# ============================================================

# WEBHOOK

# ============================================================

@app.route("/webhook", methods=["POST"])
def webhook():
update = request.get_json(silent=True) or {}

```
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
    pre_checkout_id = pre_checkout.get("id")

    print(
        "PRE-CHECKOUT:",
        pre_checkout_id
    )

    tg(
        "answerPreCheckoutQuery",
        {
            "pre_checkout_query_id": pre_checkout_id,
            "ok": True
        }
    )

    return "ok"


# ========================================================
# CALLBACK QUERY
# ========================================================

callback = update.get("callback_query")

if callback:
    callback_id = callback.get("id")
    data = callback.get("data", "")

    message = callback.get(
        "message",
        {}
    )

    chat = message.get(
        "chat",
        {}
    )

    chat_id = chat.get("id")

    print("CALLBACK DATA:", data)
    print("CHAT ID:", chat_id)

    tg(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id
        }
    )

    if data == "buy_test":
        print(
            "Создаём счёт на",
            PRICE_STARS,
            "⭐ для",
            chat_id
        )

        result = tg(
            "sendInvoice",
            {
                "chat_id": chat_id,
                "title": "Book Quiz",
                "description": (
                    "Одно прохождение психологического "
                    "теста «Какая книга тебя ждёт?»"
                ),
                "payload": f"book_quiz_{chat_id}",
                "currency": "XTR",
                "prices": [
                    {
                        "label": "Прохождение теста",
                        "amount": PRICE_STARS
                    }
                ]
            }
        )

        print("INVOICE RESULT:", result)

    return "ok"


# ========================================================
# MESSAGE
# ========================================================

message = update.get("message")

if not message:
    return "ok"

chat = message.get(
    "chat",
    {}
)

chat_id = chat.get("id")

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
    print("=" * 70)
    print("УСПЕШНАЯ ОПЛАТА")
    print("USER ID:", user_id)
    print("PAYMENT:", successful_payment)
    print("=" * 70)

    PAID_USERS.add(user_id)
    save_paid_users(PAID_USERS)

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "✅ Оплата прошла!\n\n"
                "Тест разблокирован.\n\n"
                "Нажимай кнопку ниже и проходи тест 👇"
            ),
            "reply_markup": {
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
    print("WEB APP DATA")
    print("=" * 70)
    print(web_app_data)

    # Проверяем оплату
    if user_id not in PAID_USERS:
        print(
            "ПОЛЬЗОВАТЕЛЬ НЕ ОПЛАТИЛ:",
            user_id
        )

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🔒 Тест пока не оплачен.\n\n"
                    "Сначала приобрети прохождение за 200 ⭐."
                ),
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {
                                "text": "🔓 Купить тест — 200 ⭐",
                                "callback_data": "buy_test"
                            }
                        ]
                    ]
                }
            }
        )

        return "ok"


    # Получаем JSON результата
    raw_data = web_app_data.get(
        "data",
        ""
    )

    print("RAW RESULT:", raw_data)

    try:
        result = json.loads(raw_data)

    except Exception as e:
        print(
            "ОШИБКА JSON:",
            e
        )

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "⚠️ Не удалось прочитать результат теста."
                )
            }
        )

        return "ok"


    action = result.get("action")

    if action != "quiz_result":
        print(
            "НЕИЗВЕСТНОЕ ACTION:",
            action
        )

        return "ok"


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
                "chat_id": chat_id,
                "text": (
                    "⚠️ В результате теста "
                    "не указана книга."
                )
            }
        )

        return "ok"


    # Отправляем книгу из базы
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
)

if text == "/start":
    print(
        "START от пользователя:",
        user_id
    )

    if user_id in PAID_USERS:
        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "📚 Book Quiz\n\n"
                    "Тест уже разблокирован.\n"
                    "Можешь проходить 👇"
                ),
                "reply_markup": {
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
            }
        )

    else:
        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "📚 Book Quiz\n\n"
                    "Пройди тест и узнай, "
                    "какая книга подходит именно тебе.\n\n"
                    "🔓 Стоимость прохождения — 200 ⭐"
                ),
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {
                                "text": "🔓 Купить тест — 200 ⭐",
                                "callback_data": "buy_test"
                            }
                        ]
                    ]
                }
            }
        )

return "ok"
```

# ============================================================

# ЗАПУСК

# ============================================================

if **name** == "**main**":
print("=" * 70)
print("BOOK QUIZ BOT STARTING")
print("PORT:", os.environ.get("PORT", "10000"))
print("WEB APP:", WEB_APP_URL)
print("DATABASE:", DATABASE_FILE)
print("BOOKS:", BOOKS_DIR)
print("PAID USERS:", len(PAID_USERS))
print("=" * 70)

```
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
