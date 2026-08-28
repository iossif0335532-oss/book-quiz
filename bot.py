import os
import json
import requests

from flask import Flask, request

# ============================================================

# НАСТРОЙКИ

# ============================================================

TOKEN = os.environ["BOT_TOKEN"]

API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(**name**)

PAID_USERS_FILE = "paid_users.json"
DATABASE_FILE = "recommendation_database.json"
BOOKS_DIR = "books"

# ============================================================

# ОПЛАЧИВШИЕ ПОЛЬЗОВАТЕЛИ

# ============================================================

def load_paid_users():

```
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

    return set(
        str(x)
        for x in data
    )

except Exception as e:

    print(
        "Ошибка загрузки paid_users:",
        e
    )

    return set()
```

def save_paid_users(users):

```
try:

    with open(
        PAID_USERS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            list(users),
            f,
            ensure_ascii=False,
            indent=2
        )

except Exception as e:

    print(
        "Ошибка сохранения paid_users:",
        e
    )
```

PAID_USERS = load_paid_users()

# ============================================================

# TELEGRAM API

# ============================================================

def tg(method, data):

```
try:

    response = requests.post(
        f"{API}/{method}",
        json=data,
        timeout=30
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

    print(
        "Telegram ERROR:",
        method,
        e
    )

    return {}
```

# ============================================================

# БАЗА КНИГ

# ============================================================

def load_books():

```
try:

    if not os.path.exists(DATABASE_FILE):

        print(
            "База книг не найдена:",
            DATABASE_FILE
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

    print(
        "Загружено книг из базы:",
        len(books)
    )

    return books

except Exception as e:

    print(
        "Ошибка загрузки recommendation_database.json:",
        e
    )

    return []
```

# ============================================================

# ПОИСК КНИГИ В БАЗЕ

# ============================================================

def find_book(title):

```
requested_title = str(
    title or ""
).strip()

if not requested_title:
    return None

requested_lower = requested_title.lower()

books = load_books()

# --------------------------------------------------------
# 1. ТОЧНОЕ СОВПАДЕНИЕ
# --------------------------------------------------------

for book in books:

    book_title = str(
        book.get(
            "title",
            ""
        )
    ).strip()

    if not book_title:
        continue

    if book_title.lower() == requested_lower:

        print(
            "НАЙДЕНО ТОЧНО:",
            book_title
        )

        return book

# --------------------------------------------------------
# 2. ЧАСТИЧНОЕ СОВПАДЕНИЕ
# --------------------------------------------------------

for book in books:

    book_title = str(
        book.get(
            "title",
            ""
        )
    ).strip()

    if not book_title:
        continue

    book_lower = book_title.lower()

    if (
        requested_lower in book_lower
        or book_lower in requested_lower
    ):

        print(
            "НАЙДЕНО ПО ЧАСТИ:",
            book_title
        )

        return book

# --------------------------------------------------------
# 3. НОРМАЛИЗОВАННОЕ СОВПАДЕНИЕ
# --------------------------------------------------------

def normalize(text):

    text = str(
        text or ""
    ).lower()

    chars = []

    for char in text:

        if char.isalnum() or char.isspace():

            chars.append(char)

    return " ".join(
        "".join(chars).split()
    )

normalized_requested = normalize(
    requested_title
)

for book in books:

    book_title = str(
        book.get(
            "title",
            ""
        )
    ).strip()

    if not book_title:
        continue

    normalized_book = normalize(
        book_title
    )

    if (
        normalized_requested == normalized_book
        or normalized_requested in normalized_book
        or normalized_book in normalized_requested
    ):

        print(
            "НАЙДЕНО ПО НОРМАЛИЗАЦИИ:",
            book_title
        )

        return book

print(
    "КНИГА НЕ НАЙДЕНА:",
    requested_title
)

return None
```

# ============================================================

# ПОЛУЧЕНИЕ ИМЕНИ ФАЙЛА

# ============================================================

def get_book_filename(book):

```
# --------------------------------------------------------
# filename
# --------------------------------------------------------

filename = str(
    book.get(
        "filename",
        ""
    )
).strip()

if filename:

    filename = filename.replace(
        "\\",
        "/"
    )

    return os.path.basename(
        filename
    )

# --------------------------------------------------------
# filepath
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

    return os.path.basename(
        filepath
    )

# --------------------------------------------------------
# pdf
# --------------------------------------------------------

pdf = str(
    book.get(
        "pdf",
        ""
    )
).strip()

if pdf:

    pdf = pdf.replace(
        "\\",
        "/"
    )

    return os.path.basename(
        pdf
    )

return ""
```

# ============================================================

# ПОИСК PDF

# ============================================================

def find_pdf(book):

```
filename = get_book_filename(
    book
)

if not filename:

    print(
        "У книги нет имени PDF"
    )

    return None

print(
    "Ищем PDF:",
    filename
)

# --------------------------------------------------------
# 1. books/filename.pdf
# --------------------------------------------------------

path = os.path.join(
    BOOKS_DIR,
    filename
)

if os.path.isfile(path):

    print(
        "PDF НАЙДЕН:",
        path
    )

    return path

# --------------------------------------------------------
# 2. рядом с bot.py
# --------------------------------------------------------

path = filename

if os.path.isfile(path):

    print(
        "PDF НАЙДЕН:",
        path
    )

    return path

# --------------------------------------------------------
# 3. рекурсивный поиск
# --------------------------------------------------------

if os.path.exists(BOOKS_DIR):

    for root, dirs, files in os.walk(
        BOOKS_DIR
    ):

        for file in files:

            if file.lower() == filename.lower():

                path = os.path.join(
                    root,
                    file
                )

                print(
                    "PDF НАЙДЕН РЕКУРСИВНО:",
                    path
                )

                return path

print(
    "PDF НЕ НАЙДЕН:",
    filename
)

return None
```

# ============================================================

# ОТПРАВКА PDF

# ============================================================

def send_pdf(
chat_id,
pdf_path,
title,
author=""
):

```
caption = (
    "🎉 Твой результат готов!\n\n"
    f"📕 {title}"
)

if author:

    caption += (
        f"\n✍️ {author}"
    )

caption += (
    "\n\nПриятного чтения! 📚"
)

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
    print(
        "SEND DOCUMENT STATUS:",
        response.status_code
    )

    print(
        "SEND DOCUMENT RESPONSE:",
        response.text[:2000]
    )

    return response.ok

except Exception as e:

    print(
        "Ошибка отправки PDF:",
        e
    )

    return False
```

# ============================================================

# ОТПРАВКА КНИГИ ПО НАЗВАНИЮ

# ============================================================

def send_book(
chat_id,
book_title
):

```
print()
print("=" * 70)
print("НАЧАЛО ВЫДАЧИ КНИГИ")
print("Пользователь:", chat_id)
print("Результат:", book_title)
print("=" * 70)

book = find_book(
    book_title
)

if not book:

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,

            "text": (
                "🎉 Тест завершён!\n\n"
                "📕 Твоя книга:\n"
                f"{book_title}\n\n"
                "⚠️ Книга есть в результате, "
                "но я не нашёл её в базе recommendation_database.json."
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

print(
    "КНИГА:",
    real_title
)

print(
    "АВТОР:",
    author
)

pdf_path = find_pdf(
    book
)

if not pdf_path:

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,

            "text": (
                "🎉 Тест завершён!\n\n"
                f"📕 {real_title}\n\n"
                "⚠️ Я нашёл книгу в базе, "
                "но PDF-файл этой книги не найден на сервере.\n\n"
                "Проверь папку books."
            )
        }
    )

    return False

success = send_pdf(
    chat_id,
    pdf_path,
    real_title,
    author
)

if success:

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
            "но Telegram не смог получить PDF.\n\n"
            "Попробуй пройти тест ещё раз."
        )
    }
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

# ПРОВЕРКА ОПЛАТЫ

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

paid = (
    str(user_id)
    in PAID_USERS
)

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
            "INVOICE RESULT:",
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
    print(
        "=============================================="
    )
    print(
        "ОПЛАТА ПОЛУЧЕНА"
    )
    print(
        "USER:",
        user_id
    )
    print(
        "PAYMENT:",
        json.dumps(
            successful_payment,
            ensure_ascii=False
        )
    )
    print(
        "=============================================="
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
# WEB APP DATA
# ========================================================

web_app_data = message.get(
    "web_app_data"
)

if web_app_data:

    user_id = str(
        chat_id
    )

    print()
    print(
        "WEB APP DATA:"
    )

    print(
        json.dumps(
            web_app_data,
            ensure_ascii=False
        )
    )

    # ----------------------------------------------------
    # ПРОВЕРКА ОПЛАТЫ
    # ----------------------------------------------------

    if user_id not in PAID_USERS:

        print(
            "БЕЗ ОПЛАТЫ РЕЗУЛЬТАТ НЕ ВЫДАЁМ:",
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
    # ЧИТАЕМ ДАННЫЕ ТЕСТА
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
            "Ошибка JSON:",
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
        "PARSED RESULT:",
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )

    action = result.get(
        "action"
    )

    # ----------------------------------------------------
    # ПРОВЕРКА ТИПА РЕЗУЛЬТАТА
    # ----------------------------------------------------

    if action != "quiz_result":

        print(
            "НЕИЗВЕСТНОЕ ДЕЙСТВИЕ:",
            action
        )

        return "ok"

    # ----------------------------------------------------
    # ПОЛУЧАЕМ КНИГУ
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
        "=============================================="
    )
    print(
        "РЕЗУЛЬТАТ ТЕСТА"
    )
    print(
        "ТИПАЖ:",
        archetype
    )
    print(
        "КНИГА:",
        book_title
    )
    print(
        "СОВПАДЕНИЕ:",
        match
    )
    print(
        "=============================================="
    )

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

    # ----------------------------------------------------
    # АВТОМАТИЧЕСКИ НАХОДИМ И ОТПРАВЛЯЕМ КНИГУ
    # ----------------------------------------------------

    send_book(
        chat_id,
        book_title
    )

    return "ok"

# ========================================================
# START
# ========================================================

if message.get(
    "text"
) == "/start":

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
print()
print("=" * 70)
print("BOOK QUIZ BOT STARTING")
print("=" * 70)
print(
    "Database:",
    DATABASE_FILE
)
print(
    "Books directory:",
    BOOKS_DIR
)
print(
    "Paid users:",
    len(PAID_USERS)
)
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
