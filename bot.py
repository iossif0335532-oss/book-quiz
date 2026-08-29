import json
import logging
import os
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from flask import Flask, jsonify, request, send_from_directory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("book-quiz")

APP_VERSION = "2026.08.29-production-v1"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://book-quiz.onrender.com").strip().rstrip("/")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://iossif0335532-oss.github.io/book-quiz/").strip()
TEST_MODE = os.getenv("TEST_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
PRICE_STARS = 200
DB_PATH = Path(os.getenv("DB_PATH", "/var/data/quiz_users.json"))
BOOKS_DB_PATH = Path(os.getenv("BOOKS_DB_PATH", "/var/data/telegram_books.json"))
EVENTS_PATH = Path(os.getenv("EVENTS_PATH", "/var/data/telegram_events.json"))
RECOMMENDATION_DB = Path(os.getenv("RECOMMENDATION_DB", "recommendation_database.json"))
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/telegram-webhook"
ALLOWED_UPDATES = ["message", "channel_post", "edited_channel_post", "callback_query", "pre_checkout_query"]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

app = Flask(__name__)


def tg(method, payload=None, files=None):
    if method == "setWebhook":
        r = requests.post(f"{API}/{method}", json=payload or {}, timeout=120)
    else:
        r = requests.post(f"{API}/{method}", data=payload or {}, files=files, timeout=120)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data)
    return data


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        log.exception("Cannot read %s", path)
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_users():
    return load_json(DB_PATH, {})


def load_books():
    return load_json(BOOKS_DB_PATH, {})


def load_events():
    return load_json(EVENTS_PATH, {})


def save_users(data):
    save_json(DB_PATH, data)


def save_books(data):
    save_json(BOOKS_DB_PATH, data)


def save_events(data):
    save_json(EVENTS_PATH, data)


def set_paid(user_id, value=True):
    users = load_users()
    key = str(user_id)
    item = users.get(key, {})
    item["paid"] = bool(value)
    users[key] = item
    save_users(users)


def is_paid(user_id):
    return TEST_MODE or bool(load_users().get(str(user_id), {}).get("paid"))


def record_event(kind, update):
    events = load_events()
    events.update({
        "last_update_type": kind,
        "last_update_id": update.get("update_id"),
        "last_update_at": __import__("time").time(),
    })
    if kind in {"channel_post", "edited_channel_post"}:
        post = update.get(kind) or {}
        events["last_channel_chat_id"] = post.get("chat", {}).get("id")
        events["last_channel_message_id"] = post.get("message_id")
        events["last_channel_has_document"] = bool(post.get("document"))
        events["last_channel_file_name"] = (post.get("document") or {}).get("file_name")
    save_events(events)


def save_result(user, result):
    users = load_users()
    key = str(user["id"])
    item = users.get(key, {})
    item.update({"username": user.get("username", ""), "first_name": user.get("first_name", ""), "result": result})
    users[key] = item
    save_users(users)


def normalize(text):
    value = str(text or "").lower()
    for ch in '.,!?;:()[]{}"\'–—-_/\\':
        value = value.replace(ch, " ")
    return " ".join(value.split())


def book_key(title):
    return normalize(Path(str(title or "")).stem)


def register_book(message):
    document = message.get("document") or {}
    file_id = document.get("file_id")
    file_name = document.get("file_name") or "book.pdf"
    mime = document.get("mime_type", "")
    if not file_id:
        return False
    if mime and mime != "application/pdf" and not file_name.lower().endswith(".pdf"):
        return False
    title = Path(file_name).stem.strip()
    if not title:
        return False
    books = load_books()
    books[book_key(title)] = {
        "title": title,
        "file_id": file_id,
        "file_name": file_name,
        "updated_at": message.get("date"),
        "source_chat_id": message.get("chat", {}).get("id"),
        "source_message_id": message.get("message_id"),
    }
    save_books(books)
    log.info("Indexed PDF: %s; catalog size=%s", file_name, len(books))
    return True


def find_telegram_book(title):
    books = load_books()
    wanted = book_key(title)
    if not wanted:
        return None
    if wanted in books:
        return books[wanted]
    wanted_words = [w for w in wanted.split() if len(w) >= 3]
    best = None
    best_score = 0
    for key, item in books.items():
        score = sum(1 for word in wanted_words if word in key)
        if score > best_score:
            best, best_score = item, score
    if best and best_score >= max(1, len(wanted_words) // 2):
        return best
    return None


def choose_book_from_catalog(requested_title, archetype):
    exact = find_telegram_book(requested_title)
    if exact:
        return exact
    books = list(load_books().values())
    if not books:
        return None
    # If the catalog contains only one PDF, it is the only available deliverable.
    if len(books) == 1:
        return books[0]
    try:
        db = load_json(RECOMMENDATION_DB, {})
        db_books = db.get("books", []) if isinstance(db, dict) else []
        by_title = {book_key(x.get("title")): x for x in db_books if x.get("title")}
        archetype_words = set(normalize(archetype).split())
        scored = []
        for item in books:
            meta = by_title.get(book_key(item.get("title")), {})
            text = " ".join(meta.get("themes", [])) + " " + str(meta.get("category", ""))
            score = sum(1 for word in archetype_words if word in normalize(text))
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored and scored[0][0] > 0:
            return scored[0][1]
    except Exception:
        log.exception("Recommendation database matching failed")
    return None


def send_book(chat_id, title, archetype=""):
    item = choose_book_from_catalog(title, archetype)
    if item:
        tg("sendDocument", {
            "chat_id": str(chat_id),
            "document": item["file_id"],
            "caption": f"📕 Твоя книга — «{item['title']}»",
        })
        return True
    tg("sendMessage", {
        "chat_id": chat_id,
        "text": f"📕 Результат: <b>{title}</b>\n\nКнига ещё не найдена в Telegram-каталоге. Перешли PDF в канал — бот сохранит его автоматически.",
        "parse_mode": "HTML",
    })
    return False


def add_query(url, **params):
    parts = list(urlparse(url))
    query = dict()
    from urllib.parse import parse_qsl
    query.update(parse_qsl(parts[4], keep_blank_values=True))
    query.update({k: str(v) for k, v in params.items()})
    parts[4] = urlencode(query)
    return urlunparse(parts)


def web_app_keyboard():
    url = add_query(WEB_APP_URL, test="1") if TEST_MODE else WEB_APP_URL
    return {
        "keyboard": [[{"text": "🎲 Пройти тест", "web_app": {"url": url}}]],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def payment_keyboard():
    return {"inline_keyboard": [[{"text": f"⭐ Оплатить {PRICE_STARS} Stars", "callback_data": "pay_quiz"}]]}


def send_start(chat_id):
    if TEST_MODE:
        text = "📚 <b>Какая книга тебя ждёт?</b>\n\n12 вопросов → твой типаж → персональная книга.\n\n🧪 Тестовый запуск открыт.\n💳 Оплата Stars также доступна для проверки."
    else:
        text = "📚 <b>Какая книга тебя ждёт?</b>\n\n12 вопросов → твой типаж → персональная книга.\n\nСтоимость — <b>200 ⭐</b>. Сначала оплати прохождение."
    tg("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": web_app_keyboard(),
    })
    tg("sendMessage", {
        "chat_id": chat_id,
        "text": "💳 Оплата прохождения:" if not TEST_MODE else "🧪 Тест выше. Если хочешь проверить реальную оплату Stars — нажми ниже:",
        "reply_markup": payment_keyboard(),
    })


def send_invoice(chat_id):
    tg("sendInvoice", {
        "chat_id": chat_id,
        "title": "Прохождение Book Quiz",
        "description": "12 вопросов и персональная рекомендация книги.",
        "payload": f"quiz_access:{chat_id}",
        "currency": "XTR",
        "prices": [{"label": "Прохождение теста", "amount": PRICE_STARS}],
    })


def handle_message(message):
    user = message.get("from") or {}
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return

    if message.get("document"):
        if register_book(message):
            tg("sendMessage", {"chat_id": chat_id, "text": f"✅ PDF сохранён в каталоге: {message['document'].get('file_name', 'book.pdf')}"})
        return

    successful = message.get("successful_payment")
    if successful:
        set_paid(user.get("id", chat_id), True)
        tg("sendMessage", {
            "chat_id": chat_id,
            "text": "✅ <b>Оплата прошла!</b>\n\nДоступ к тесту открыт.",
            "parse_mode": "HTML",
            "reply_markup": web_app_keyboard(),
        })
        return

    web_app_data = message.get("web_app_data")
    if web_app_data:
        user_id = user.get("id", chat_id)
        if not is_paid(user_id):
            tg("sendMessage", {"chat_id": chat_id, "text": "🔒 Сначала оплати прохождение теста."})
            return
        try:
            result = json.loads(web_app_data.get("data", "{}"))
        except json.JSONDecodeError:
            tg("sendMessage", {"chat_id": chat_id, "text": "⚠️ Не удалось прочитать результат. Пройди тест ещё раз."})
            return
        if result.get("action") != "quiz_result" or not result.get("book"):
            tg("sendMessage", {"chat_id": chat_id, "text": "⚠️ Некорректный результат теста."})
            return
        save_result(user, result)
        archetype = result.get("archetype", "Не определён")
        book = result["book"]
        match = result.get("match")
        text = f"🎉 <b>Тест завершён!</b>\n\n🧠 Типаж: <b>{archetype}</b>\n📕 Рекомендация: <b>{book}</b>"
        if match is not None:
            text += f"\n✨ Совпадение: {match}%"
        tg("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
        send_book(chat_id, book, archetype)
        return

    text = (message.get("text") or "").strip()
    if text.startswith("/start") or text.startswith("/help"):
        send_start(chat_id)
    elif text == "/test":
        send_start(chat_id)
    elif text == "/pay":
        send_invoice(chat_id)
    elif text == "/catalog":
        books = list(load_books().values())
        names = "\n".join(f"• {x['title']}" for x in books[:20])
        suffix = f"\n\n{names}" if names else "\n\nПока пусто."
        tg("sendMessage", {"chat_id": chat_id, "text": f"📚 В Telegram-каталоге сохранено <b>{len(books)}</b> книг.{suffix}", "parse_mode": "HTML"})
    elif text == "/debug":
        events = load_events()
        tg("sendMessage", {"chat_id": chat_id, "text": "🔎 <b>Диагностика</b>\n" + json.dumps(events, ensure_ascii=False, indent=2), "parse_mode": "HTML"})
    elif text == "/book":
        result = load_users().get(str(user.get("id", chat_id)), {}).get("result", {})
        book = result.get("book") if isinstance(result, dict) else None
        if book:
            send_book(chat_id, book, result.get("archetype", ""))
        else:
            tg("sendMessage", {"chat_id": chat_id, "text": "Сначала пройди тест."})


def handle_update(update):
    record_event(next((k for k in ("channel_post", "edited_channel_post", "message", "callback_query", "pre_checkout_query") if k in update), "unknown"), update)
    pre = update.get("pre_checkout_query")
    if pre:
        payload = pre.get("invoice_payload", "")
        ok = payload.startswith("quiz_access:")
        tg("answerPreCheckoutQuery", {"pre_checkout_query_id": pre["id"], "ok": ok, **({} if ok else {"error_message": "Заказ не найден."})})
        return

    callback = update.get("callback_query")
    if callback:
        if callback.get("data") == "pay_quiz":
            tg("answerCallbackQuery", {"callback_query_id": callback["id"]})
            send_invoice(callback.get("message", {}).get("chat", {}).get("id"))
        return

    for key in ("channel_post", "edited_channel_post"):
        post = update.get(key)
        if post:
            log.info("Received %s: chat_id=%s message_id=%s has_document=%s", key, post.get("chat", {}).get("id"), post.get("message_id"), bool(post.get("document")))
            register_book(post)
            return

    message = update.get("message")
    if message:
        handle_message(message)


@app.get("/")
def index():
    return send_from_directory(".", "index.html")


@app.get("/health")
def health():
    try:
        webhook_info = tg("getWebhookInfo").get("result", {})
    except Exception as exc:
        webhook_info = {"error": str(exc)}
    events = load_events()
    return jsonify({
        "ok": True,
        "version": APP_VERSION,
        "test_mode": TEST_MODE,
        "webhook_url": WEBHOOK_URL,
        "webhook_info": webhook_info,
        "expected_allowed_updates": ALLOWED_UPDATES,
        "web_app_url": WEB_APP_URL,
        "telegram_book_count": len(load_books()),
        "books_db": str(BOOKS_DB_PATH),
        "books_db_exists": BOOKS_DB_PATH.exists(),
        "last_update_type": events.get("last_update_type"),
        "last_channel_chat_id": events.get("last_channel_chat_id"),
        "last_channel_message_id": events.get("last_channel_message_id"),
        "last_channel_has_document": events.get("last_channel_has_document"),
        "last_channel_file_name": events.get("last_channel_file_name"),
    })


@app.get("/setup-webhook")
def setup_webhook_route():
    try:
        result = setup_webhook()
        info = tg("getWebhookInfo").get("result", {})
        return jsonify({"ok": True, "set_webhook": result, "webhook_info": info, "expected_allowed_updates": ALLOWED_UPDATES})
    except Exception as exc:
        log.exception("Manual webhook setup failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/check-access")
def check_access():
    user_id = request.args.get("user_id", "").strip()
    return jsonify({"ok": True, "paid": TEST_MODE or (bool(user_id) and is_paid(user_id)), "test_mode": TEST_MODE})


@app.post("/telegram-webhook")
def telegram_webhook():
    update = request.get_json(silent=True) or {}
    try:
        handle_update(update)
    except Exception:
        log.exception("Webhook update failed")
    return jsonify({"ok": True})


def setup_webhook():
    try:
        tg("deleteWebhook", {"drop_pending_updates": False})
    except Exception:
        log.exception("deleteWebhook failed")
    payload = {
        "url": WEBHOOK_URL,
        "drop_pending_updates": False,
        "allowed_updates": json.dumps(ALLOWED_UPDATES, separators=(",", ":")),
    }
    result = tg("setWebhook", payload)
    log.info("Webhook configured: %s", result)
    return result


if __name__ == "__main__":
    os.execvp("gunicorn", ["gunicorn", "--workers", "1", "--bind", f"0.0.0.0:{os.getenv('PORT', '10000')}", "wsgi:app"])
