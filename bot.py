import json
import logging
import os
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("book-quiz")
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://book-quiz.onrender.com").strip().rstrip("/")
WEB_APP_URL = os.getenv("WEB_APP_URL", f"{RENDER_EXTERNAL_URL}/").strip()
TEST_MODE = os.getenv("TEST_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}
PRICE_STARS = 200
BOOKS_DIR = Path(os.getenv("BOOKS_DIR", "books"))
DB_PATH = Path(os.getenv("DB_PATH", "quiz_users.json"))
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/telegram-webhook"
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
app = Flask(__name__)

def tg(method, payload=None, files=None):
    response = requests.post(f"{API}/{method}", data=payload or {}, files=files, timeout=120)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(data)
    return data

def load_users():
    if not DB_PATH.exists(): return {}
    try: return json.loads(DB_PATH.read_text(encoding="utf-8"))
    except Exception:
        log.exception("Cannot read users database")
        return {}

def save_users(users):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

def set_paid(user_id, value=True):
    users = load_users(); key = str(user_id); item = users.get(key, {})
    item["paid"] = bool(value); users[key] = item; save_users(users)

def is_paid(user_id): return TEST_MODE or bool(load_users().get(str(user_id), {}).get("paid"))

def save_result(user, result):
    users = load_users(); key = str(user["id"]); item = users.get(key, {})
    item.update({"username": user.get("username", ""), "first_name": user.get("first_name", ""), "result": result})
    users[key] = item; save_users(users)

def web_app_keyboard():
    return {"keyboard": [[{"text": "🎲 Пройти тест", "web_app": {"url": WEB_APP_URL}}]], "resize_keyboard": True, "is_persistent": True}

def payment_keyboard():
    return {"inline_keyboard": [[{"text": f"⭐ Оплатить {PRICE_STARS} Stars", "callback_data": "pay_quiz"}]]}

def send_start(chat_id):
    text = ("📚 <b>Какая книга тебя ждёт?</b>\n\n12 вопросов → твой типаж → персональная рекомендация.\n\n" +
            ("🧪 <b>ТЕСТОВЫЙ РЕЖИМ</b>\nОплата отключена. Доступ открыт.\n\n" if TEST_MODE else f"Стоимость — <b>{PRICE_STARS} ⭐</b>.\nСначала оплати прохождение.\n\n") +
            "После теста результат автоматически придёт сюда вместе с книгой.")
    tg("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": web_app_keyboard()})
    if not TEST_MODE: tg("sendMessage", {"chat_id": chat_id, "text": "Нажми кнопку ниже для оплаты:", "reply_markup": payment_keyboard()})

def send_invoice(chat_id):
    if TEST_MODE: set_paid(chat_id, True); send_start(chat_id); return
    tg("sendInvoice", {"chat_id": chat_id, "title": "Прохождение теста", "description": "12 вопросов и персональная рекомендация книги.", "payload": f"quiz_access:{chat_id}", "currency": "XTR", "prices": [{"label": "Прохождение теста", "amount": PRICE_STARS}]})

def normalize(text):
    chars = '.,!?;:()[]{}"\'–—-_/\\'; value = str(text or "").lower()
    for ch in chars: value = value.replace(ch, " ")
    return " ".join(value.split())

def find_book(title):
    if not BOOKS_DIR.exists(): return None
    wanted = normalize(title); pdfs = list(BOOKS_DIR.rglob("*.pdf"))
    for pdf in pdfs:
        if normalize(pdf.stem) == wanted: return pdf
    for pdf in pdfs:
        if wanted and wanted in normalize(pdf.stem): return pdf
    words = [w for w in wanted.split() if len(w) >= 3]; best = None; best_score = 0
    for pdf in pdfs:
        stem = normalize(pdf.stem); score = sum(1 for word in words if word in stem)
        if score > best_score: best, best_score = pdf, score
    return best if best and best_score >= max(1, len(words) // 2) else None

def send_book(chat_id, title):
    pdf = find_book(title)
    if not pdf:
        log.warning("Book PDF not found: %s; BOOKS_DIR=%s", title, BOOKS_DIR)
        tg("sendMessage", {"chat_id": chat_id, "text": f"📕 Твоя книга: <b>{title}</b>\n\nРезультат сохранён. PDF этой книги пока отсутствует в каталоге бота.", "parse_mode": "HTML"})
        return False
    with pdf.open("rb") as fh:
        tg("sendDocument", {"chat_id": str(chat_id), "caption": f"📕 Твоя книга — «{title}»"}, {"document": (pdf.name, fh, "application/pdf")})
    log.info("Book sent: %s -> %s", pdf, chat_id); return True

def handle_message(message):
    user = message.get("from") or {}; chat_id = message.get("chat", {}).get("id")
    if not chat_id: return
    if message.get("successful_payment"):
        set_paid(user.get("id", chat_id), True)
        tg("sendMessage", {"chat_id": chat_id, "text": "✅ <b>Оплата прошла!</b>\n\nДоступ открыт. Нажми «🎲 Пройти тест».", "parse_mode": "HTML", "reply_markup": web_app_keyboard()}); return
    web_app_data = message.get("web_app_data")
    if web_app_data:
        user_id = user.get("id", chat_id)
        if not is_paid(user_id): tg("sendMessage", {"chat_id": chat_id, "text": "🔒 Сначала оплатите прохождение теста."}); return
        try: result = json.loads(web_app_data.get("data", "{}"))
        except json.JSONDecodeError: tg("sendMessage", {"chat_id": chat_id, "text": "⚠️ Не удалось прочитать результат теста. Пройди тест ещё раз."}); return
        if result.get("action") != "quiz_result" or not result.get("book"):
            tg("sendMessage", {"chat_id": chat_id, "text": "⚠️ Результат теста имеет неверный формат."}); return
        save_result(user, result); archetype = result.get("archetype", "Не определён"); book = result["book"]; match = result.get("match")
        text = f"🎉 <b>Тест завершён!</b>\n\n🧠 Типаж: <b>{archetype}</b>\n📕 Книга: <b>{book}</b>" + (f"\n✨ Совпадение: {match}%" if match is not None else "")
        tg("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}); send_book(chat_id, book); return
    text = (message.get("text") or "").strip()
    if text.startswith("/start") or text.startswith("/help"): send_start(chat_id)
    elif text == "/test":
        if not TEST_MODE: tg("sendMessage", {"chat_id": chat_id, "text": "❌ Тестовый режим отключён."})
        else: set_paid(user.get("id", chat_id), True); send_start(chat_id)
    elif text == "/book":
        result = load_users().get(str(user.get("id", chat_id)), {}).get("result", {}); book = result.get("book") if isinstance(result, dict) else None
        send_book(chat_id, book) if book else tg("sendMessage", {"chat_id": chat_id, "text": "Сначала пройди тест через «🎲 Пройти тест»."})

def handle_update(update):
    pre = update.get("pre_checkout_query")
    if pre: tg("answerPreCheckoutQuery", {"pre_checkout_query_id": pre["id"], "ok": pre.get("invoice_payload", "").startswith("quiz_access:")}); return
    callback = update.get("callback_query")
    if callback:
        if callback.get("data") == "pay_quiz": tg("answerCallbackQuery", {"callback_query_id": callback["id"]}); send_invoice(callback.get("message", {}).get("chat", {}).get("id"))
        return
    message = update.get("message")
    if message: handle_message(message)

@app.get("/")
def index(): return send_from_directory(".", "index.html")

@app.get("/health")
def health():
    try: webhook_info = tg("getWebhookInfo").get("result", {})
    except Exception as exc: webhook_info = {"error": str(exc)}
    return jsonify({"ok": True, "service": "book-quiz-bot", "test_mode": TEST_MODE, "webhook_url": WEBHOOK_URL, "webhook_info": webhook_info, "web_app_url": WEB_APP_URL, "pdf_count": len(list(BOOKS_DIR.rglob("*.pdf"))) if BOOKS_DIR.exists() else 0})

@app.get("/check-access")
def check_access():
    user_id = request.args.get("user_id", "").strip(); return jsonify({"ok": True, "paid": TEST_MODE or (bool(user_id) and is_paid(user_id)), "test_mode": TEST_MODE})

@app.post("/telegram-webhook")
def telegram_webhook():
    update = request.get_json(silent=True) or {}
    try: handle_update(update)
    except Exception: log.exception("Webhook update failed")
    return jsonify({"ok": True})

def setup_webhook():
    result = tg("setWebhook", {"url": WEBHOOK_URL, "drop_pending_updates": False, "allowed_updates": ["message", "callback_query", "pre_checkout_query"]}); log.info("Webhook set: %s", result); log.info("Webhook info: %s", tg("getWebhookInfo")); return result

if __name__ == "__main__": setup_webhook(); app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
