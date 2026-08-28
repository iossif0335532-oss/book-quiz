import os
import json
import requests
from flask import Flask, request

# ============================================================
# НАСТРОЙКИ
# ============================================================

TOKEN = os.environ["BOT_TOKEN"]

API = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

# ============================================================
# ПОДКЛЮЧАЕМ ТВОЙ ГОТОВЫЙ АЛГОРИТМ
# ============================================================

import final_recommendation as engine

# На Render нет C:\Users\User\Desktop\
# Поэтому используем файл из текущей папки проекта.

engine.DATABASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "recommendation_database.json"
)

# Результаты будем сохранять рядом с ботом.
engine.RESULT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "last_test_result.json"
)

# ============================================================
# ВОПРОСЫ
# ============================================================

QUESTIONS = engine.QUESTIONS

PROBLEMS = engine.PROBLEMS

# ============================================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ ОТВЕТОВ
#
# Для первого запуска этого достаточно.
# Позже можно заменить на SQLite/PostgreSQL.
# ============================================================

users = {}


# ============================================================
# TELEGRAM API
# ============================================================

def tg(method, data=None):
    try:
        response = requests.post(
            f"{API}/{method}",
            json=data or {},
            timeout=30
        )

        return response.json()

    except Exception as e:
        print("Telegram API error:", e)
        return None


# ============================================================
# КЛАВИАТУРА ОТВЕТА
# ============================================================

def answer_keyboard(question_number):

    return {
        "inline_keyboard": [
            [
                {
                    "text": "1 — Совсем не про меня",
                    "callback_data": f"answer_{question_number}_1"
                }
            ],
            [
                {
                    "text": "2 — Скорее не про меня",
                    "callback_data": f"answer_{question_number}_2"
                }
            ],
            [
                {
                    "text": "3 — Иногда",
                    "callback_data": f"answer_{question_number}_3"
                }
            ],
            [
                {
                    "text": "4 — Скорее про меня",
                    "callback_data": f"answer_{question_number}_4"
                }
            ],
            [
                {
                    "text": "5 — Полностью про меня",
                    "callback_data": f"answer_{question_number}_5"
                }
            ]
        ]
    }


# ============================================================
# НАЧАЛО ТЕСТА
# ============================================================

def start_test(chat_id):

    users[chat_id] = {
        "question": 0,
        "answers": []
    }

    send_question(chat_id)


# ============================================================
# ОТПРАВКА ВОПРОСА
# ============================================================

def send_question(chat_id):

    user = users.get(chat_id)

    if not user:
        start_test(chat_id)
        return

    question_number = user["question"]

    if question_number >= len(QUESTIONS):
        finish_test(chat_id)
        return

    question_text, problem = QUESTIONS[question_number]

    text = (
        f"📚 Вопрос {question_number + 1} из {len(QUESTIONS)}\n\n"
        f"{question_text}\n\n"
        "Выберите вариант ответа:"
    )

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": answer_keyboard(question_number)
        }
    )


# ============================================================
# ОБРАБОТКА ОТВЕТА
# ============================================================

def process_answer(chat_id, question_number, answer):

    user = users.get(chat_id)

    if not user:
        start_test(chat_id)
        return

    # Защита от повторного/старого нажатия
    if question_number != user["question"]:
        return

    user["answers"].append(answer)

    user["question"] += 1

    if user["question"] < len(QUESTIONS):

        send_question(chat_id)

    else:

        finish_test(chat_id)


# ============================================================
# ФОРМИРОВАНИЕ ПРОФИЛЯ
# ============================================================

def calculate_profile(answers):

    scores = {
        problem: 0
        for problem in PROBLEMS
    }

    for index, answer in enumerate(answers):

        question, problem = QUESTIONS[index]

        # Последний вопрос положительный:
        #
        # 1 -> 5
        # 2 -> 4
        # 3 -> 3
        # 4 -> 2
        # 5 -> 1

        if problem == "общение":

            scores[problem] += 6 - answer

        else:

            scores[problem] += answer

    return scores


# ============================================================
# ПОЛУЧЕНИЕ РЕКОМЕНДАЦИЙ
# ============================================================

def get_recommendations(scores):

    books = engine.load_books()

    if not books:
        raise Exception(
            "База recommendation_database.json не загружена."
        )

    print("Книг в базе:", len(books))

    # Главная проблема
    sorted_profile = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    main_problem = sorted_profile[0][0]

    recommendations = []

    for book in books:

        score, matched = engine.calculate_score(
            book,
            scores,
            main_problem
        )

        if score > 0:

            recommendations.append(
                {
                    "score": score,
                    "book": book,
                    "matched": matched
                }
            )

    recommendations.sort(
        key=lambda item: (
            item["score"],
            len(item["matched"]),
            float(
                item["book"].get(
                    "recommendation_score",
                    0
                ) or 0
            )
        ),
        reverse=True
    )

    return main_problem, recommendations


# ============================================================
# СОХРАНЕНИЕ РЕЗУЛЬТАТА
# ============================================================

def save_user_result(
    scores,
    main_problem,
    recommendations
):

    result = {
        "profile": scores,
        "main_problem": main_problem,
        "recommendations": []
    }

    for item in recommendations[:6]:

        book = item["book"]

        result["recommendations"].append(
            {
                "book_id": book.get("book_id"),
                "title": book.get("title", ""),
                "author": book.get("author", ""),
                "category": book.get("category", ""),
                "type": book.get(
                    "type",
                    book.get("book_type", "")
                ),
                "score": item["score"],
                "matched": item["matched"],
                "themes": sorted(
                    engine.normalize_themes(book)
                ),
                "filepath": book.get(
                    "filepath",
                    book.get("filename", "")
                )
            }
        )

    try:

        with open(
            engine.RESULT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                result,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:

        print("Ошибка сохранения:", e)


# ============================================================
# РЕЗУЛЬТАТ
# ============================================================

def finish_test(chat_id):

    user = users.get(chat_id)

    if not user:
        return

    answers = user["answers"]

    tg(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "🧠 Анализирую твои ответы...\n\n"
                "📚 Проверяю книги из библиотеки..."
            )
        }
    )

    try:

        scores = calculate_profile(answers)

        main_problem, recommendations = get_recommendations(
            scores
        )

        if not recommendations:

            tg(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": (
                        "😔 Я не смог найти подходящую книгу.\n\n"
                        "Попробуй пройти тест ещё раз."
                    )
                }
            )

            return

        # Сохраняем результат
        save_user_result(
            scores,
            main_problem,
            recommendations
        )

        # Главная книга
        first = recommendations[0]

        book = first["book"]

        title = book.get(
            "title",
            "Без названия"
        )

        author = str(
            book.get(
                "author",
                ""
            )
        ).strip()

        score = first["score"]

        matched = first["matched"]

        # ====================================================
        # ПРОФИЛЬ
        # ====================================================

        profile_text = "\n".join(
            [
                f"• {problem}: {value}"
                for problem, value in sorted(
                    scores.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ]
        )

        text = (
            "🎯 ТВОЙ РЕЗУЛЬТАТ\n\n"

            f"Главная зона:\n"
            f"🔥 {main_problem.upper()}\n\n"

            "Твой профиль:\n"
            f"{profile_text}\n\n"

            "━━━━━━━━━━━━━━━━━━\n\n"

            "📕 ТВОЯ КНИГА\n\n"

            f"📖 {title}\n"
        )

        if author:

            text += f"✍️ Автор: {author}\n"

        text += (
            f"\n🧠 Умный рейтинг: {score}\n\n"
            "Книга подходит по:\n"
            + "\n".join(
                [
                    f"• {problem}"
                    for problem in matched
                ]
            )
        )

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text
            }
        )

        # ====================================================
        # ЕЩЁ 5
        # ====================================================

        if len(recommendations) > 1:

            extra_text = (
                "📚 ЕЩЁ 5 КНИГ ДЛЯ ТЕБЯ\n\n"
            )

            for number, item in enumerate(
                recommendations[1:6],
                2
            ):

                rec_book = item["book"]

                rec_title = rec_book.get(
                    "title",
                    "Без названия"
                )

                rec_author = str(
                    rec_book.get(
                        "author",
                        ""
                    )
                ).strip()

                extra_text += (
                    f"{number}. 📖 {rec_title}\n"
                )

                if rec_author:

                    extra_text += (
                        f"   Автор: {rec_author}\n"
                    )

                extra_text += (
                    f"   Рейтинг: {item['score']}\n\n"
                )

            tg(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": extra_text
                }
            )

        # ====================================================
        # PDF
        # ====================================================

        filepath = book.get(
            "filepath",
            book.get(
                "filename",
                ""
            )
        )

        # ВАЖНО:
        # Пока отправляем путь только как информацию.
        # На Render Windows-пути C:\Users\User\Desktop\...
        # физически не существуют.
        #
        # Когда перенесём PDF в GitHub/хранилище,
        # здесь подключим реальную отправку PDF.

        if filepath:

            tg(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": (
                        "📕 Файл книги:\n"
                        f"{filepath}\n\n"
                        "⚠️ PDF подключим следующим этапом "
                        "после проверки рекомендаций."
                    )
                }
            )

    except Exception as e:

        print("ERROR finish_test:", e)

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "⚠️ Произошла ошибка при анализе.\n\n"
                    "Техническая информация:\n"
                    f"{str(e)}"
                )
            }
        )

    finally:

        # После завершения теста очищаем состояние пользователя.
        users.pop(chat_id, None)


# ============================================================
# ГЛАВНАЯ СТРАНИЦА RENDER
# ============================================================

@app.route("/")
def home():

    try:

        with open(
            "index.html",
            encoding="utf-8"
        ) as f:

            return f.read()

    except Exception:

        return "Book Quiz Bot is running."


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return "OK"


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():

    update = request.json or {}

    print("UPDATE:", update)

    # ========================================================
    # CALLBACK
    # ========================================================

    callback = update.get(
        "callback_query"
    )

    if callback:

        callback_id = callback["id"]

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
            "data",
            ""
        )

        # Убираем "часики" на кнопке
        tg(
            "answerCallbackQuery",
            {
                "callback_query_id": callback_id
            }
        )

        # ====================================================
        # ПОКУПКА ТЕСТА
        # ====================================================

        if data == "buy_test":

            tg(
                "sendInvoice",
                {
                    "chat_id": chat_id,
                    "title": "Book Quiz",
                    "description": (
                        "Одно прохождение "
                        "персонального теста "
                        "«Какая книга тебя ждёт?»"
                    ),
                    "payload": (
                        f"book_quiz_{chat_id}"
                    ),
                    "currency": "XTR",
                    "prices": [
                        {
                            "label": "Прохождение теста",
                            "amount": 200
                        }
                    ]
                }
            )

            return "ok"

        # ====================================================
        # ОТВЕТ НА ВОПРОС
        # ====================================================

        if data.startswith("answer_"):

            parts = data.split("_")

            if len(parts) == 3:

                try:

                    question_number = int(
                        parts[1]
                    )

                    answer = int(
                        parts[2]
                    )

                    process_answer(
                        chat_id,
                        question_number,
                        answer
                    )

                except Exception as e:

                    print(
                        "Answer error:",
                        e
                    )

            return "ok"

        return "ok"

    # ========================================================
    # PRE-CHECKOUT
    # ========================================================

    pre_checkout = update.get(
        "pre_checkout_query"
    )

    if pre_checkout:

        tg(
            "answerPreCheckoutQuery",
            {
                "pre_checkout_query_id":
                    pre_checkout["id"],
                "ok": True
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

    chat_id = message["chat"]["id"]

    # ========================================================
    # УСПЕШНАЯ ОПЛАТА
    # ========================================================

    successful_payment = message.get(
        "successful_payment"
    )

    if successful_payment:

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "✅ Оплата прошла!\n\n"
                    "Тест разблокирован.\n\n"
                    "📚 Готов? Начинаем."
                ),
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {
                                "text": "🚀 Начать тест",
                                "callback_data": "start_test"
                            }
                        ]
                    ]
                }
            }
        )

        return "ok"

    # ========================================================
    # /START
    # ========================================================

    if message.get("text") == "/start":

        tg(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "📚 BOOK QUIZ\n\n"
                    "Пройди персональный тест "
                    "из 15 вопросов.\n\n"
                    "Я определю твою главную зону "
                    "и найду книгу из библиотеки, "
                    "которая подходит именно тебе.\n\n"
                    "Стоимость прохождения — 200 ⭐"
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

    return "ok"


# ============================================================
# START SERVER
# ============================================================

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
