import json
import os

DATABASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "recommendation_database.json"
)

RESULT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "last_test_result.json"
)


QUESTIONS = [
    ("Как часто вы откладываете важные дела?", "прокрастинация"),
    ("Насколько трудно вам начать сложное дело?", "прокрастинация"),

    ("Как часто вам не хватает желания действовать?", "мотивация"),
    ("Как часто вы теряете интерес после начала дела?", "мотивация"),

    ("Как часто вы сомневаетесь в своих способностях?", "самооценка"),
    ("Насколько сильно вы зависите от мнения других?", "самооценка"),

    ("Как часто вы испытываете сильное беспокойство?", "тревога"),
    ("Как часто тревожные мысли мешают действовать?", "тревога"),

    ("Насколько часто возникают сложности в отношениях?", "отношения"),
    ("Как часто вам сложно понять другого человека?", "отношения"),

    ("Насколько трудно сформировать полезные привычки?", "привычки"),
    ("Как часто вы возвращаетесь к старым привычкам?", "привычки"),

    ("Как часто вам трудно принять решение?", "мышление"),
    ("Насколько трудно сосредоточиться и закончить дело?", "мышление"),

    ("Насколько легко вам выражать свои мысли?", "общение"),
]


PROBLEMS = [
    "прокрастинация",
    "мотивация",
    "самооценка",
    "тревога",
    "отношения",
    "привычки",
    "мышление",
    "общение",
]


def load_books():
    if not os.path.exists(DATABASE):
        print()
        print("ОШИБКА: база не найдена:")
        print(DATABASE)
        return []

    try:
        with open(
            DATABASE,
            "r",
            encoding="utf-8-sig"
        ) as f:
            data = json.load(f)

    except Exception as e:
        print()
        print("ОШИБКА загрузки базы:")
        print(e)
        return []

    if not isinstance(data, dict):
        print("ОШИБКА: база имеет неправильную структуру.")
        return []

    books = data.get("books", [])

    if not isinstance(books, list):
        print("ОШИБКА: поле books не является списком.")
        return []

    books = [
        book
        for book in books
        if isinstance(book, dict)
    ]

    return books


def normalize_themes(book):
    themes = book.get("themes", [])

    if not isinstance(themes, list):
        return set()

    return {
        str(theme).strip().lower()
        for theme in themes
        if str(theme).strip()
    }


def is_valid_book(book):
    title = str(
        book.get(
            "title",
            ""
        )
    ).strip()

    if not title:
        return False

    themes = normalize_themes(book)

    if not themes:
        return False

    return True


def get_themes(book):
    possible_fields = [
        "themes",
        "theme",
        "problems",
        "problem",
        "tags",
        "categories",
    ]

    for field in possible_fields:

        value = book.get(field)

        if isinstance(value, list):

            return {
                str(item).strip().lower()
                for item in value
                if str(item).strip()
            }

        if isinstance(value, str):

            return {
                item.strip().lower()
                for item in value.replace(
                    ";",
                    ","
                ).split(",")
                if item.strip()
            }

    return set()


def calculate_score(
    book,
    profile,
    main_problem
):
    """
    Финальный персональный рейтинг книги.

    Основа:

    1. Главная проблема пользователя.
    2. Сила выраженности проблемы.
    3. Совпадение дополнительных проблем.
    4. Точность попадания.
    5. Штраф за слишком универсальные книги.
    6. Покрытие профиля.
    """

    title = str(
        book.get(
            "title",
            ""
        )
    ).strip()

    if not title:
        return 0, []

    themes = normalize_themes(book)

    if not themes:
        return 0, []

    matched = [
        problem
        for problem in PROBLEMS
        if (
            problem in themes
            and profile.get(
                problem,
                0
            ) >= 3
        )
    ]

    if not matched:
        return 0, []

    main_score = profile.get(
        main_problem,
        0
    )

    total = 0

    # ========================================================
    # 1. ОСНОВНОЙ БАЛЛ
    # ========================================================

    if main_problem in matched:

        total += main_score * 200

    else:

        total -= 300

    # ========================================================
    # 2. ВТОРИЧНЫЕ ПРОБЛЕМЫ
    # ========================================================

    for problem in matched:

        if problem == main_problem:
            continue

        user_score = profile.get(
            problem,
            0
        )

        total += user_score * 50

    # ========================================================
    # 3. БОНУС ЗА СИЛЬНОЕ ПОПАДАНИЕ
    # ========================================================

    strong_matches = sum(
        1
        for problem in matched
        if profile.get(
            problem,
            0
        ) >= 5
    )

    total += strong_matches * 40

    # ========================================================
    # 4. БОНУС ЗА ТОЧНОЕ ПОПАДАНИЕ
    # ========================================================

    if main_problem in matched:

        total += (
            main_score
            * main_score
            * 10
        )

    # ========================================================
    # 5. ШТРАФ ЗА СЛИШКОМ УНИВЕРСАЛЬНЫЕ КНИГИ
    # ========================================================

    extra_themes = max(
        0,
        len(themes) - len(matched)
    )

    total -= extra_themes * 10

    # ========================================================
    # 6. ПОКРЫТИЕ ПРОФИЛЯ
    # ========================================================

    profile_problems = [
        problem
        for problem in PROBLEMS
        if profile.get(
            problem,
            0
        ) >= 3
    ]

    if profile_problems:

        coverage = (
            len(matched)
            / len(profile_problems)
        )

        total += int(
            coverage * 100
        )

    return total, matched


def ask_question(
    number,
    text
):
    print()
    print("=" * 60)
    print(
        "ВОПРОС "
        + str(number)
        + " ИЗ 15"
    )
    print("=" * 60)
    print()
    print(text)
    print()
    print(
        "1 — Совсем не про меня"
    )
    print(
        "2 — Скорее не про меня"
    )
    print(
        "3 — Иногда"
    )
    print(
        "4 — Скорее про меня"
    )
    print(
        "5 — Полностью про меня"
    )

    while True:

        answer = input(
            "\nВаш ответ: "
        ).strip()

        if answer in [
            "1",
            "2",
            "3",
            "4",
            "5"
        ]:

            return int(answer)

        print()
        print(
            "Введите число от 1 до 5."
        )


def print_profile(scores):

    sorted_profile = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    print()
    print("=" * 60)
    print(
        "                 ВАШ ПРОФИЛЬ"
    )
    print("=" * 60)

    for number, (
        problem,
        score
    ) in enumerate(
        sorted_profile,
        1
    ):

        print(
            str(number)
            + ". "
            + problem
            + ": "
            + str(score)
        )

    return sorted_profile


def recommendation_reason(
    main_problem,
    matched,
    profile
):

    if main_problem in matched:

        if len(matched) == 1:

            return (
                "Книга напрямую соответствует "
                "вашей главной зоне — "
                + main_problem
                + "."
            )

        secondary = [
            problem
            for problem in matched
            if problem != main_problem
        ]

        return (
            "Книга напрямую работает "
            "с вашей главной зоной — "
            + main_problem
            + ", и дополнительно закрывает: "
            + ", ".join(secondary)
            + "."
        )

    return (
        "Книга соответствует нескольким "
        "выраженным зонам вашего профиля."
    )


def save_result(
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

        result[
            "recommendations"
        ].append(
            {
                "book_id": book.get(
                    "book_id"
                ),

                "title": book.get(
                    "title",
                    ""
                ),

                "author": book.get(
                    "author",
                    ""
                ),

                "category": book.get(
                    "category",
                    ""
                ),

                "type": book.get(
                    "type",
                    book.get(
                        "book_type",
                        ""
                    )
                ),

                "score": item[
                    "score"
                ],

                "matched": item[
                    "matched"
                ],

                "themes": sorted(
                    normalize_themes(book)
                ),

                "filepath": book.get(
                    "filepath",
                    book.get(
                        "filename",
                        ""
                    )
                )
            }
        )

    try:

        with open(
            RESULT_FILE,
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

        print()
        print(
            "Ошибка сохранения результата:"
        )
        print(e)


def build_recommendations(
    scores
):

    sorted_profile = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    main_problem = sorted_profile[0][0]

    books = load_books()

    recommendations = []

    for book in books:

        score, matched = calculate_score(
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

    return (
        main_problem,
        recommendations
    )


def main():

    print()
    print("=" * 60)
    print(
        "        ПСИХОЛОГИЧЕСКИЙ ТЕСТ — ВАША КНИГА"
    )
    print("=" * 60)

    books = load_books()

    if not books:

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    print()
    print(
        "Книг в базе:",
        len(books)
    )

    print()
    print(
        "Ответьте на 15 вопросов."
    )
    print(
        "Используйте шкалу от 1 до 5."
    )

    scores = {
        problem: 0
        for problem in PROBLEMS
    }

    # ========================================================
    # ТЕСТ
    # ========================================================

    for number, (
        question,
        problem
    ) in enumerate(
        QUESTIONS,
        1
    ):

        answer = ask_question(
            number,
            question
        )

        if problem == "общение":

            scores[
                problem
            ] += 6 - answer

        else:

            scores[
                problem
            ] += answer

    # ========================================================
    # ПРОФИЛЬ
    # ========================================================

    sorted_profile = print_profile(
        scores
    )

    main_problem = sorted_profile[0][0]

    print()
    print(
        "Главная зона:",
        main_problem
    )

    # ========================================================
    # АНАЛИЗ
    # ========================================================

    print()
    print(
        "Анализируем",
        len(books),
        "книг..."
    )

    (
        main_problem,
        recommendations
    ) = build_recommendations(
        scores
    )

    # ========================================================
    # РЕЗУЛЬТАТ
    # ========================================================

    print()
    print("=" * 60)
    print(
        "                  ВАША КНИГА"
    )
    print("=" * 60)

    if not recommendations:

        print()
        print(
            "Подходящая книга не найдена."
        )
        print()

        save_result(
            scores,
            main_problem,
            []
        )

        input(
            "\nНажмите Enter для выхода..."
        )

        return

    first = recommendations[0]

    book = first["book"]

    matched = first["matched"]

    score = first["score"]

    print()
    print(
        book.get(
            "title",
            "Без названия"
        )
    )

    author = str(
        book.get(
            "author",
            ""
        )
    ).strip()

    if author:

        print(
            "Автор:",
            author
        )

    print(
        "Категория:",
        book.get(
            "category",
            "Не указана"
        )
    )

    book_type = book.get(
        "type",
        book.get(
            "book_type",
            ""
        )
    )

    if book_type:

        print(
            "Тип книги:",
            book_type
        )

    print(
        "Умный рейтинг:",
        score
    )

    print()
    print(
        "Книга подходит по проблемам:"
    )

    for problem in matched:

        print(
            "  •",
            problem
        )

    print()
    print(
        "Почему она выбрана:"
    )

    print()

    print(
        " ",
        recommendation_reason(
            main_problem,
            matched,
            scores
        )
    )

    themes = normalize_themes(
        book
    )

    if themes:

        print()
        print(
            "Темы книги:"
        )

        print(
            " ",
            ", ".join(
                sorted(themes)
            )
        )

    filepath = book.get(
        "filepath",
        book.get(
            "filename",
            ""
        )
    )

    print()
    print(
        "PDF-файл:"
    )

    print(filepath)

    # ========================================================
    # ЕЩЁ 5
    # ========================================================

    print()
    print("=" * 60)
    print(
        "              ЕЩЁ 5 РЕКОМЕНДАЦИЙ"
    )
    print("=" * 60)

    for number, item in enumerate(
        recommendations[1:6],
        2
    ):

        rec_book = item["book"]

        print()
        print(
            str(number)
            + ". "
            + rec_book.get(
                "title",
                "Без названия"
            )
        )

        author = str(
            rec_book.get(
                "author",
                ""
            )
        ).strip()

        if author:

            print(
                "   Автор:",
                author
            )

        print(
            "   Категория:",
            rec_book.get(
                "category",
                "Не указана"
            )
        )

        rec_type = rec_book.get(
            "type",
            rec_book.get(
                "book_type",
                ""
            )
        )

        if rec_type:

            print(
                "   Тип:",
                rec_type
            )

        print(
            "   Умный рейтинг:",
            item["score"]
        )

        print(
            "   Совпадения:",
            ", ".join(
                item["matched"]
            )
        )

        print(
            "   PDF:",
            rec_book.get(
                "filepath",
                rec_book.get(
                    "filename",
                    ""
                )
            )
        )

    # ========================================================
    # СОХРАНЕНИЕ
    # ========================================================

    save_result(
        scores,
        main_problem,
        recommendations
    )

    print()
    print("=" * 60)
    print(
        "             ТЕСТ ЗАВЕРШЁН"
    )
    print("=" * 60)

    print()
    print(
        "Результат сохранён:"
    )

    print(
        RESULT_FILE
    )

    input(
        "\nНажмите Enter для выхода..."
    )


if __name__ == "__main__":
    main()
