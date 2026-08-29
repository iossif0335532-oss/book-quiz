import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from flask import Flask, jsonify, request, send_from_directory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("book-quiz")
APP_VERSION = "2026.08.30-production-v2"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "https://book-quiz.onrender.com").strip().rstrip("/")
WEB_APP_URL = f"{BASE_URL}/app"
PRICE_STARS = 200
DB_PATH = Path(os.getenv("DB_PATH", "/var/data/quiz_users.json"))
BOOKS_DB_PATH = Path(os.getenv("BOOKS_DB_PATH", "/var/data/telegram_books.json"))
EVENTS_PATH = Path(os.getenv("EVENTS_PATH", "/var/data/telegram_events.json"))
RECOMMENDATION_DB = Path(os.getenv("RECOMMENDATION_DB", "recommendation_database.json"))
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEBHOOK_URL = f"{BASE_URL}/telegram-webhook"
ALLOWED_UPDATES = ["message", "channel_post", "edited_channel_post", "callback_query", "pre_checkout_query"]
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
app = Flask(__name__)

def tg(method, payload=None):
    response = requests.post(f"{API}/{method}", json=payload or {}, timeout=60)
    response.raise_for_status()
    data = response.json()
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

def users(): return load_json(DB_PATH, {})
def books(): return load_json(BOOKS_DB_PATH, {})
def events(): return load_json(EVENTS_PATH, {})
def save_users(data): save_json(DB_PATH, data)
def save_books(data): save_json(BOOKS_DB_PATH, data)
def save_events(data): save_json(EVENTS_PATH, data)
def user_record(user_id): return users().get(str(user_id), {})
def grant_test(user_id):
    data = users(); item = data.setdefault(str(user_id), {}); item["test_access"] = True; save_users(data)
def grant_paid(user_id, payment):
    data = users(); item = data.setdefault(str(user_id), {}); item["paid"] = True; item["telegram_payment_charge_id"] = payment.get("telegram_payment_charge_id"); save_users(data)
def has_access(user_id): return bool(user_record(user_id).get("paid") or user_record(user_id).get("test_access"))

def normalize(text):
    value = str(text or "").lower().replace("ё", "е")
    value = re.sub(r"[^\w\s]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())

def title_key(text): return normalize(Path(str(text or "")).stem)
def strip_prefix(text): return re.sub(r"^\s*\d+\s*[-_.:)]+\s*", "", str(text or "")).strip()

def record_event(kind, update):
    data = events(); data.update({"last_update_type": kind, "last_update_id": update.get("update_id"), "last_update_at": time.time()})
    if kind in {"channel_post", "edited_channel_post"}:
        post = update.get(kind) or {}; doc = post.get("document") or {}
        data.update({"last_channel_chat_id": (post.get("chat") or {}).get("id"), "last_channel_title": (post.get("chat") or {}).get("title"), "last_channel_message_id": post.get("message_id"), "last_channel_has_document": bool(doc), "last_channel_file_name": doc.get("file_name"), "last_channel_mime_type": doc.get("mime_type")})
    save_events(data)

def register_book(message):
    doc = message.get("document") or {}; file_id = doc.get("file_id"); file_name = doc.get("file_name") or "book.pdf"; mime = doc.get("mime_type") or ""
    if not file_id or not file_name.lower().endswith(".pdf"): return False
    title = strip_prefix(Path(file_name).stem)
    if not title: return False
    data = books(); data[title_key(title)] = {"title": title, "file_name": file_name, "file_id": file_id, "mime_type": mime, "source_chat_id": (message.get("chat") or {}).get("id"), "source_chat_title": (message.get("chat") or {}).get("title"), "source_message_id": message.get("message_id"), "updated_at": message.get("date")}; save_books(data)
    log.info("BOOK INDEXED: %s; catalog=%d", file_name, len(data)); return True

ARCHETYPE_THEMES = {"Запускатор": ["мотивация", "прокрастинация", "привычки", "бизнес"], "Архитектор": ["привычки", "бизнес", "образование", "лидерство"], "Обаятель": ["общение", "отношения", "лидерство"], "Магнат": ["деньги", "бизнес", "лидерство", "финансы"], "Мастер слова": ["общение", "образование", "мышление", "психология"], "Визионер": ["мышление", "образование", "бизнес", "саморазвитие"], "Берсерк": ["мотивация", "привычки", "самооценка", "прокрастинация"], "Биохакер": ["здоровье", "привычки", "самооценка"]}

def recommendation_books():
    data = load_json(RECOMMENDATION_DB, {}); return data.get("books", []) if isinstance(data, dict) else []

def choose_book(requested_title="", archetype=""):
    catalog = list(books().values())
    if not catalog: return None
    wanted = title_key(requested_title)
    if wanted and wanted in books(): return books()[wanted]
    metadata = recommendation_books(); by_title = {title_key(x.get("title")): x for x in metadata if x.get("title")}; by_filename = {title_key(x.get("filename")): x for x in metadata if x.get("filename")}
    for item in catalog:
        for candidate in (item.get("title"), item.get("file_name")):
            k = title_key(candidate)
            meta = by_title.get(k) or by_filename.get(k)
            if meta and wanted and (wanted == title_key(meta.get("title")) or wanted == title_key(meta.get("filename"))): return item
    target = set(ARCHETYPE_THEMES.get(archetype, [])); scored = []
    for item in catalog:
        meta = by_title.get(title_key(item.get("title"))) or by_filename.get(title_key(item.get("file_name")), {})
        themes = set(normalize(" ".join(meta.get("themes", []))).split()); category = normalize(meta.get("category", "")); score = len(target & themes) * 10
        if category in target: score += 4
        scored.append((score, item))
    scored.sort(key=lambda row: row[0], reverse=True)
    if scored and scored[0][0] > 0: return scored[0][1]
    return catalog[0] if len(catalog) == 1 else None

def send_book(chat_id, requested_title, archetype):
    item = choose_book(requested_title, archetype)
    if not item:
        tg("sendMessage", {"chat_id": chat_id, "text": f"📕 Результат: «{archetype}»\n\n❗ Подходящей PDF-книги пока нет в Telegram-каталоге."}); return False
    tg("sendDocument", {"chat_id": chat_id, "document": item["file_id"], "caption": f"📕 Твоя книга — «{item['title']}»"}); return True

def app_url(mode):
    parsed = list(urlparse(WEB_APP_URL)); query = dict(parse_qsl(parsed[4], keep_blank_values=True)); query["mode"] = mode; parsed[4] = urlencode(query); return urlunparse(parsed)
def quiz_keyboard(): return {"keyboard": [[{"text": "🧪 Тестовый запуск", "web_app": {"url": app_url("test")}}]], "resize_keyboard": True, "is_persistent": True}
def paid_keyboard(): return {"keyboard": [[{"text": "🎲 Пройти тест", "web_app": {"url": app_url("paid")}}]], "resize_keyboard": True, "is_persistent": True}

def send_start(chat_id):
    tg("sendMessage", {"chat_id": chat_id, "text": "📚 <b>Book Quiz</b>\n\n12 вопросов → твой типаж → персональная книга.\n\n🧪 Тестовый запуск — бесплатно.\n💳 Реальный тест — 200 ⭐.", "parse_mode": "HTML", "reply_markup": quiz_keyboard()})
    tg("sendMessage", {"chat_id": chat_id, "text": "💳 Реальный доступ:", "reply_markup": {"inline_keyboard": [[{"text": "⭐ Оплатить 200 Stars", "callback_data": "pay_quiz"}]]}})

def send_invoice(chat_id):
    tg("sendInvoice", {"chat_id": chat_id, "title": "Book Quiz", "description": "12 вопросов и персональная книга.", "payload": f"quiz_access:{chat_id}", "currency": "XTR", "prices": [{"label": "Book Quiz", "amount": PRICE_STARS}]})

def handle_message(message):
    user = message.get("from") or {}; user_id = user.get("id"); chat_id = (message.get("chat") or {}).get("id")
    if not chat_id: return
    if message.get("document"):
        if register_book(message): tg("sendMessage", {"chat_id": chat_id, "text": f"✅ PDF добавлен в каталог: {message['document'].get('file_name', 'book.pdf')}"})
        return
    payment = message.get("successful_payment")
    if payment:
        grant_paid(user_id or chat_id, payment); tg("sendMessage", {"chat_id": chat_id, "text": "✅ Оплата подтверждена Telegram Stars. Нажми «🎲 Пройти тест».", "reply_markup": paid_keyboard()}); return
    web_data = message.get("web_app_data")
    if web_data:
        if not has_access(user_id or chat_id):
            tg("sendMessage", {"chat_id": chat_id, "text": "🔒 Доступ закрыт. Используй /test или оплати 200 ⭐."}); return
        try: result = json.loads(web_data.get("data", ""))
        except Exception:
            tg("sendMessage", {"chat_id": chat_id, "text": "⚠️ Не удалось прочитать результат. Пройди тест ещё раз."}); return
        if result.get("action") != "quiz_result" or not result.get("archetype"):
            tg("sendMessage", {"chat_id": chat_id, "text": "⚠️ Некорректный результат теста."}); return
        data = users(); item = data.setdefault(str(user_id or chat_id), {}); item["result"] = result; item["username"] = user.get("username", ""); item["first_name"] = user.get("first_name", ""); save_users(data)
        archetype = result["archetype"]; requested = result.get("book", "")
        tg("sendMessage", {"chat_id": chat_id, "text": f"🎉 <b>Тест завершён!</b>\n\n🧠 Типаж: <b>{archetype}</b>", "parse_mode": "HTML"}); send_book(chat_id, requested, archetype); return
    text = (message.get("text") or "").strip()
    if text.startswith("/start") or text == "/help": send_start(chat_id)
    elif text == "/test": grant_test(user_id or chat_id); tg("sendMessage", {"chat_id": chat_id, "text": "🧪 <b>Тестовый доступ включён.</b> Нажми кнопку ниже.", "parse_mode": "HTML", "reply_markup": quiz_keyboard()})
    elif text == "/pay": send_invoice(chat_id)
    elif text == "/catalog":
        catalog = list(books().values()); names = "\n".join(f"• {x['title']}" for x in catalog[:30]) or "Пока пусто."; tg("sendMessage", {"chat_id": chat_id, "text": f"📚 В Telegram-каталоге: <b>{len(catalog)}</b> книг.\n\n{names}", "parse_mode": "HTML"})
    elif text == "/book":
        result = user_record(user_id or chat_id).get("result", {})
        if isinstance(result, dict) and result.get("archetype"): send_book(chat_id, result.get("book", ""), result["archetype"])
        else: tg("sendMessage", {"chat_id": chat_id, "text": "Сначала пройди тест."})
    elif text == "/debug":
        state = events(); state["catalog_count"] = len(books()); state["access"] = has_access(user_id or chat_id); tg("sendMessage", {"chat_id": chat_id, "text": "<pre>" + json.dumps(state, ensure_ascii=False, indent=2) + "</pre>", "parse_mode": "HTML"})

def handle_update(update):
    kind = next((name for name in ("channel_post", "edited_channel_post", "message", "callback_query", "pre_checkout_query") if name in update), "unknown"); record_event(kind, update)
    pre_checkout = update.get("pre_checkout_query")
    if pre_checkout:
        tg("answerPreCheckoutQuery", {"pre_checkout_query_id": pre_checkout["id"], "ok": True}); return
    callback = update.get("callback_query")
    if callback:
        tg("answerCallbackQuery", {"callback_query_id": callback["id"]})
        if callback.get("data") == "pay_quiz": send_invoice(((callback.get("message") or {}).get("chat") or {}).get("id"))
        return
    for name in ("channel_post", "edited_channel_post"):
        post = update.get(name)
        if post:
            register_book(post); return
    message = update.get("message")
    if message: handle_message(message)

@app.get("/")
def root(): return jsonify(ok=True, service="book-quiz", version=APP_VERSION, app=f"{BASE_URL}/app")
@app.get("/app")
def mini_app(): return send_from_directory(".", "index.html")
@app.get("/health")
def health():
    try: info = tg("getWebhookInfo").get("result", {})
    except Exception as exc: info = {"error": str(exc)}
    state = events(); return jsonify(ok=True, version=APP_VERSION, webhook_info=info, expected_allowed_updates=ALLOWED_UPDATES, web_app_url=WEB_APP_URL, telegram_book_count=len(books()), books_db_exists=BOOKS_DB_PATH.exists(), last_update_type=state.get("last_update_type"), last_channel_chat_id=state.get("last_channel_chat_id"), last_channel_title=state.get("last_channel_title"), last_channel_message_id=state.get("last_channel_message_id"), last_channel_has_document=state.get("last_channel_has_document"), last_channel_file_name=state.get("last_channel_file_name"))
@app.get("/check-access")
def check_access():
    user_id = request.args.get("user_id", "").strip(); item = user_record(user_id); return jsonify(ok=True, paid=bool(item.get("paid") or item.get("test_access")), test=bool(item.get("test_access")), real_paid=bool(item.get("paid")))
@app.get("/setup-webhook")
def setup_webhook():
    try:
        result = tg("setWebhook", {"url": WEBHOOK_URL, "drop_pending_updates": False, "allowed_updates": ALLOWED_UPDATES}); info = tg("getWebhookInfo").get("result", {}); return jsonify(ok=True, set_webhook=result, webhook_info=info, expected_allowed_updates=ALLOWED_UPDATES)
    except Exception as exc:
        log.exception("Webhook setup failed"); return jsonify(ok=False, error=str(exc)), 500
@app.post("/telegram-webhook")
def telegram_webhook():
    update = request.get_json(silent=True) or {}; log.info("TELEGRAM UPDATE keys=%s id=%s", sorted(update.keys()), update.get("update_id"))
    try: handle_update(update)
    except Exception: log.exception("Webhook update failed")
    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
