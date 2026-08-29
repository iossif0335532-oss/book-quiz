import json
import logging
import os
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("book-quiz")
APP_VERSION = "2026.08.29-channel-v4"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://book-quiz.onrender.com").strip().rstrip("/")
WEB_APP_URL = os.getenv("WEB_APP_URL", f"{RENDER_EXTERNAL_URL}/").strip()
TEST_MODE = os.getenv("TEST_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}
PRICE_STARS = 200
DB_PATH = Path(os.getenv("DB_PATH", "/var/data/quiz_users.json"))
BOOKS_DB_PATH = Path(os.getenv("BOOKS_DB_PATH", "/var/data/telegram_books.json"))
BOOKS_DIR = Path(os.getenv("BOOKS_DIR", "books"))
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

def load_json(path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: log.exception("Cannot read %s", path); return default

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def load_users(): return load_json(DB_PATH, {})
def load_books(): return load_json(BOOKS_DB_PATH, {})
def save_users(data): save_json(DB_PATH, data)
def save_books(data): save_json(BOOKS_DB_PATH, data)
def set_paid(user_id, value=True):
    users=load_users(); key=str(user_id); item=users.get(key, {}); item["paid"]=bool(value); users[key]=item; save_users(users)
def is_paid(user_id): return TEST_MODE or bool(load_users().get(str(user_id), {}).get("paid"))
def save_result(user, result):
    users=load_users(); key=str(user["id"]); item=users.get(key, {}); item.update({"username":user.get("username",""),"first_name":user.get("first_name",""),"result":result}); users[key]=item; save_users(users)
def normalize(text):
    value=str(text or "").lower()
    for ch in '.,!?;:()[]{}"\'–—-_/\\': value=value.replace(ch," ")
    return " ".join(value.split())
def book_key(title): return normalize(Path(str(title or "")).stem)
def register_book(message):
    document=message.get("document") or {}; file_id=document.get("file_id"); file_name=document.get("file_name") or "book.pdf"; mime=document.get("mime_type","")
    if not file_id or (mime and mime!="application/pdf" and not file_name.lower().endswith(".pdf")): return False
    title=Path(file_name).stem.strip()
    if not title:return False
    books=load_books(); books[book_key(title)]={"title":title,"file_id":file_id,"file_name":file_name,"updated_at":message.get("date"),"source_chat_id":message.get("chat",{}).get("id"),"source_message_id":message.get("message_id")}; save_books(books)
    log.info("Indexed PDF: %s (catalog size=%s)",file_name,len(books)); return True
def find_telegram_book(title):
    books=load_books(); wanted=book_key(title)
    if not wanted:return None
    if wanted in books:return books[wanted]
    words=[w for w in wanted.split() if len(w)>=3]; best=None; best_score=0
    for key,item in books.items():
        score=sum(1 for word in words if word in key)
        if score>best_score:best,best_score=item,score
    return best if best and best_score>=max(1,len(words)//2) else None
def find_local_book(title):
    if not BOOKS_DIR.exists():return None
    wanted=book_key(title)
    for pdf in BOOKS_DIR.rglob("*.pdf"):
        if book_key(pdf.stem)==wanted:return pdf
    return None
def send_book(chat_id,title):
    item=find_telegram_book(title)
    if item:
        tg("sendDocument",{"chat_id":str(chat_id),"document":item["file_id"],"caption":f"📕 Твоя книга — «{item['title']}»"}); return True
    pdf=find_local_book(title)
    if pdf:
        with pdf.open("rb") as fh:tg("sendDocument",{"chat_id":str(chat_id),"caption":f"📕 Твоя книга — «{title}»"},{"document":(pdf.name,fh,"application/pdf")})
        return True
    tg("sendMessage",{"chat_id":chat_id,"text":f"📕 Рекомендованная книга: <b>{title}</b>\n\nPDF пока не найден в каталоге Telegram.","parse_mode":"HTML"}); return False
def web_app_keyboard():return {"keyboard":[[{"text":"🎲 Пройти тест","web_app":{"url":WEB_APP_URL}}]],"resize_keyboard":True,"is_persistent":True}
def payment_keyboard():return {"inline_keyboard":[[{"text":f"⭐ Оплатить {PRICE_STARS} Stars","callback_data":"pay_quiz"}]]}
def send_start(chat_id):
    text="📚 <b>Какая книга тебя ждёт?</b>\n\n12 вопросов → твой типаж → персональная рекомендация.\n\n"+("🧪 <b>ТЕСТОВЫЙ РЕЖИМ</b>\nОплата отключена. Доступ открыт.\n\n" if TEST_MODE else f"Стоимость — <b>{PRICE_STARS} ⭐</b>.\nСначала оплати прохождение.\n\n")+"После теста результат автоматически придёт сюда вместе с книгой."
    tg("sendMessage",{"chat_id":chat_id,"text":text,"parse_mode":"HTML","reply_markup":web_app_keyboard()})
    if not TEST_MODE:tg("sendMessage",{"chat_id":chat_id,"text":"Нажми кнопку ниже для оплаты:","reply_markup":payment_keyboard()})
def send_invoice(chat_id):
    if TEST_MODE:set_paid(chat_id,True);send_start(chat_id);return
    tg("sendInvoice",{"chat_id":chat_id,"title":"Прохождение теста","description":"12 вопросов и персональная рекомендация книги.","payload":f"quiz_access:{chat_id}","currency":"XTR","prices":[{"label":"Прохождение теста","amount":PRICE_STARS}]})
def handle_message(message):
    user=message.get("from") or {}; chat_id=message.get("chat",{}).get("id")
    if not chat_id:return
    if message.get("document"):
        if register_book(message):tg("sendMessage",{"chat_id":chat_id,"text":f"✅ Книга сохранена в каталоге бота: {message['document'].get('file_name','book.pdf')}"})
        return
    if message.get("successful_payment"):
        set_paid(user.get("id",chat_id),True);tg("sendMessage",{"chat_id":chat_id,"text":"✅ <b>Оплата прошла!</b>\n\nДоступ открыт. Нажми «🎲 Пройти тест»." ,"parse_mode":"HTML","reply_markup":web_app_keyboard()});return
    web_app_data=message.get("web_app_data")
    if web_app_data:
        user_id=user.get("id",chat_id)
        if not is_paid(user_id):tg("sendMessage",{"chat_id":chat_id,"text":"🔒 Сначала оплатите прохождение теста."});return
        try:result=json.loads(web_app_data.get("data","{}"))
        except json.JSONDecodeError:tg("sendMessage",{"chat_id":chat_id,"text":"⚠️ Не удалось прочитать результат теста. Пройди тест ещё раз."});return
        if result.get("action")!="quiz_result" or not result.get("book"):tg("sendMessage",{"chat_id":chat_id,"text":"⚠️ Результат теста имеет неверный формат."});return
        save_result(user,result);archetype=result.get("archetype","Не определён");book=result["book"];match=result.get("match")
        text=f"🎉 <b>Тест завершён!</b>\n\n🧠 Типаж: <b>{archetype}</b>\n📕 Книга: <b>{book}</b>"+(f"\n✨ Совпадение: {match}%" if match is not None else "")
        tg("sendMessage",{"chat_id":chat_id,"text":text,"parse_mode":"HTML"});send_book(chat_id,book);return
    text=(message.get("text") or "").strip()
    if text.startswith("/start") or text.startswith("/help"):send_start(chat_id)
    elif text=="/test":
        if TEST_MODE:set_paid(user.get("id",chat_id),True);send_start(chat_id)
        else:tg("sendMessage",{"chat_id":chat_id,"text":"🔒 Сначала оплатите прохождение теста."})
    elif text=="/catalog":tg("sendMessage",{"chat_id":chat_id,"text":f"📚 В Telegram-каталоге сохранено <b>{len(load_books())}</b> книг.","parse_mode":"HTML"})
    elif text=="/book":
        result=load_users().get(str(user.get("id",chat_id)),{}).get("result",{});book=result.get("book") if isinstance(result,dict) else None
        send_book(chat_id,book) if book else tg("sendMessage",{"chat_id":chat_id,"text":"Сначала пройди тест через «🎲 Пройти тест»."})
def handle_update(update):
    pre=update.get("pre_checkout_query")
    if pre:tg("answerPreCheckoutQuery",{"pre_checkout_query_id":pre["id"],"ok":pre.get("invoice_payload","").startswith("quiz_access:")});return
    callback=update.get("callback_query")
    if callback:
        if callback.get("data")=="pay_quiz":tg("answerCallbackQuery",{"callback_query_id":callback["id"]});send_invoice(callback.get("message",{}).get("chat",{}).get("id"))
        return
    channel_post=update.get("channel_post")
    if channel_post:
        register_book(channel_post);return
    message=update.get("message")
    if message:handle_message(message)
@app.get("/")
def index():return send_from_directory(".","index.html")
@app.get("/health")
def health():
    try:webhook_info=tg("getWebhookInfo").get("result",{})
    except Exception as exc:webhook_info={"error":str(exc)}
    return jsonify({"ok":True,"version":APP_VERSION,"service":"book-quiz-bot","test_mode":TEST_MODE,"webhook_url":WEBHOOK_URL,"webhook_info":webhook_info,"web_app_url":WEB_APP_URL,"telegram_book_count":len(load_books()),"books_db":str(BOOKS_DB_PATH),"books_db_exists":BOOKS_DB_PATH.exists()})
@app.get("/check-access")
def check_access():
    user_id=request.args.get("user_id","").strip();return jsonify({"ok":True,"paid":TEST_MODE or (bool(user_id) and is_paid(user_id)),"test_mode":TEST_MODE})
@app.post("/telegram-webhook")
def telegram_webhook():
    update=request.get_json(silent=True) or {}
    try:handle_update(update)
    except Exception:log.exception("Webhook update failed")
    return jsonify({"ok":True})
def setup_webhook():
    result=tg("setWebhook",{"url":WEBHOOK_URL,"drop_pending_updates":False,"allowed_updates":["message","channel_post","callback_query","pre_checkout_query"]});log.info("Webhook set: %s",result);return result
if __name__=="__main__":
    # If Render still has an old Start Command such as `python bot.py`,
    # transparently hand off to Gunicorn instead of starting Flask's dev server.
    os.execvp("gunicorn", ["gunicorn", "--workers", "1", "--bind", f"0.0.0.0:{os.getenv('PORT','10000')}", "wsgi:app"])
