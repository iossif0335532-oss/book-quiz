import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from flask import Flask, jsonify, request, send_from_directory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("book-quiz")
APP_VERSION = "2026.08.30-clean-v1"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://book-quiz.onrender.com").strip().rstrip("/")
WEB_APP_URL = os.getenv("WEB_APP_URL", f"{RENDER_EXTERNAL_URL}/app").strip().rstrip("/")
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
    response = requests.post(f"{API}/{method}", json=payload or {}, timeout=120) if method == "setWebhook" else requests.post(f"{API}/{method}", data=payload or {}, files=files, timeout=120)
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

def users(): return load_json(DB_PATH, {})
def books(): return load_json(BOOKS_DB_PATH, {})
def events(): return load_json(EVENTS_PATH, {})
def save_users(data): save_json(DB_PATH, data)
def save_books(data): save_json(BOOKS_DB_PATH, data)
def save_events(data): save_json(EVENTS_PATH, data)
def user_record(user_id): return users().get(str(user_id), {})
def grant_test(user_id):
    data=users(); item=data.get(str(user_id), {}); item["test_access"]=True; data[str(user_id)]=item; save_users(data)
def grant_paid(user_id, payment=None):
    data=users(); item=data.get(str(user_id), {}); item["paid"]=True
    if payment: item["telegram_payment_charge_id"]=payment.get("telegram_payment_charge_id")
    data[str(user_id)]=item; save_users(data)
def has_access(user_id):
    item=user_record(user_id); return bool(item.get("paid") or item.get("test_access"))

def record_event(kind, update):
    data=events(); data.update({"last_update_type":kind,"last_update_id":update.get("update_id"),"last_update_at":time.time()})
    if kind in {"channel_post","edited_channel_post"}:
        post=update.get(kind) or {}; doc=post.get("document") or {}
        data.update({"last_channel_chat_id":post.get("chat",{}).get("id"),"last_channel_title":post.get("chat",{}).get("title"),"last_channel_message_id":post.get("message_id"),"last_channel_has_document":bool(doc),"last_channel_file_name":doc.get("file_name"),"last_channel_mime_type":doc.get("mime_type")})
    save_events(data)

def normalize(text):
    value=str(text or "").lower().replace("ё","е")
    for ch in '.,!?;:()[]{}"\'–—-_/\\': value=value.replace(ch," ")
    return " ".join(value.split())

def title_key(text): return normalize(Path(str(text or "")).stem)

def register_book(message):
    doc=message.get("document") or {}; file_id=doc.get("file_id"); file_name=doc.get("file_name") or "book.pdf"; mime=doc.get("mime_type") or ""
    if not file_id or (mime and mime != "application/pdf" and not file_name.lower().endswith(".pdf")): return False
    title=Path(file_name).stem.strip()
    if not title: return False
    data=books(); data[title_key(title)]={"title":title,"file_id":file_id,"file_name":file_name,"mime_type":mime,"updated_at":message.get("date"),"source_chat_id":message.get("chat",{}).get("id"),"source_chat_title":message.get("chat",{}).get("title"),"source_message_id":message.get("message_id")}; save_books(data)
    log.info("BOOK INDEXED: %s; catalog=%s",file_name,len(data)); return True

def find_book(requested_title):
    data=books(); wanted=title_key(requested_title)
    if not wanted: return None
    if wanted in data: return data[wanted]
    wanted_words={w for w in wanted.split() if len(w)>=3}; best=None; best_score=0
    for key,item in data.items():
        common=len(wanted_words & set(key.split())); contains=sum(1 for w in wanted_words if w in key); score=common*4+contains
        if score>best_score: best_score=score; best=item
    return best if best and best_score>=max(2,len(wanted_words)) else None

def recommendation_meta():
    db=load_json(RECOMMENDATION_DB,{})
    return db.get("books",[]) if isinstance(db,dict) else []

def choose_book(requested_title, archetype=""):
    exact=find_book(requested_title)
    if exact: return exact
    catalog=list(books().values())
    if not catalog: return None
    if len(catalog)==1: return catalog[0]
    meta=recommendation_meta(); by_key={title_key(x.get("title")):x for x in meta if x.get("title")}
    target={w for w in title_key(requested_title).split() if len(w)>=3}; scored=[]
    for item in catalog:
        m=by_key.get(title_key(item.get("title")),{}); text=normalize(" ".join(m.get("themes",[]))+" "+str(m.get("category","")))
        score=sum(6 for w in target if w in title_key(item.get("title")))
        score+=sum(2 for w in normalize(archetype).split() if len(w)>=3 and w in text)
        scored.append((score,item))
    scored.sort(key=lambda x:x[0],reverse=True)
    return scored[0][1] if scored and scored[0][0]>0 else None

def send_book(chat_id, requested_title, archetype=""):
    item=choose_book(requested_title,archetype)
    if not item:
        tg("sendMessage",{"chat_id":chat_id,"text":f"📕 Рекомендация: {requested_title}\n\n❗ Этой книги пока нет в Telegram-каталоге. Добавь PDF в канал и пройди тест ещё раз."}); return False
    tg("sendDocument",{"chat_id":chat_id,"document":item["file_id"],"caption":f"📕 Твоя книга — «{item['title']}»"}); return True

def app_url(test=False):
    parsed=list(urlparse(WEB_APP_URL)); query=dict(parse_qsl(parsed[4],keep_blank_values=True)); query["mode"]="test" if test else "paid"; parsed[4]=urlencode(query); return urlunparse(parsed)

def test_keyboard(): return {"keyboard":[[{"text":"🧪 Тестовый запуск","web_app":{"url":app_url(True)}}]],"resize_keyboard":True,"is_persistent":True}
def paid_keyboard(): return {"keyboard":[[{"text":"🎲 Пройти тест","web_app":{"url":app_url(False)}}]],"resize_keyboard":True,"is_persistent":True}
def payment_inline(): return {"inline_keyboard":[[{"text":f"⭐ Оплатить {PRICE_STARS} Stars","callback_data":"pay_quiz"}]]}

def send_start(chat_id):
    tg("sendMessage",{"chat_id":chat_id,"text":"📚 <b>Book Quiz</b>\n\n12 вопросов → твой типаж → персональная книга.\n\n🧪 Для проверки есть бесплатный тестовый запуск.\n💳 Реальный доступ — 200 ⭐.","parse_mode":"HTML","reply_markup":test_keyboard()})
    tg("sendMessage",{"chat_id":chat_id,"text":"💳 Реальный доступ:","reply_markup":payment_inline()})

def send_invoice(chat_id):
    tg("sendInvoice",{"chat_id":chat_id,"title":"Book Quiz","description":"12 вопросов и персональная рекомендация книги.","payload":f"quiz_access:{chat_id}","currency":"XTR","prices":[{"label":"Book Quiz","amount":PRICE_STARS}]})

def handle_message(message):
    user=message.get("from") or {}; chat_id=message.get("chat",{}).get("id")
    if not chat_id: return
    if message.get("document"):
        if register_book(message): tg("sendMessage",{"chat_id":chat_id,"text":f"✅ Книга добавлена в каталог: {message['document'].get('file_name','book.pdf')}"})
        return
    payment=message.get("successful_payment")
    if payment:
        grant_paid(user.get("id",chat_id),payment); tg("sendMessage",{"chat_id":chat_id,"text":"✅ Оплата подтверждена Telegram Stars. Теперь можно проходить тест.","reply_markup":paid_keyboard()}); return
    web_data=message.get("web_app_data")
    if web_data:
        if not has_access(user.get("id",chat_id)):
            tg("sendMessage",{"chat_id":chat_id,"text":"🔒 Доступ закрыт. Используй /test или оплати 200 ⭐."}); return
        try: result=json.loads(web_data.get("data","{}"))
        except json.JSONDecodeError:
            tg("sendMessage",{"chat_id":chat_id,"text":"⚠️ Результат повреждён. Запусти тест ещё раз."}); return
        if result.get("action")!="quiz_result" or not result.get("book"):
            tg("sendMessage",{"chat_id":chat_id,"text":"⚠️ Некорректный результат теста."}); return
        data=users(); item=data.get(str(user.get("id",chat_id)),{}); item["result"]=result; item["username"]=user.get("username",""); item["first_name"]=user.get("first_name",""); data[str(user.get("id",chat_id))]=item; save_users(data)
        archetype=result.get("archetype",""); book=result["book"]; text=f"🎉 <b>Тест завершён!</b>\n\n🧠 Типаж: <b>{archetype}</b>\n📕 Рекомендация: <b>{book}</b>"; match=result.get("match")
        if match is not None: text+=f"\n✨ Совпадение: {match}%"
        tg("sendMessage",{"chat_id":chat_id,"text":text,"parse_mode":"HTML"}); send_book(chat_id,book,archetype); return
    text=(message.get("text") or "").strip()
    if text.startswith("/start") or text=="/help": send_start(chat_id)
    elif text=="/test":
        grant_test(user.get("id",chat_id)); tg("sendMessage",{"chat_id":chat_id,"text":"🧪 <b>Тестовый доступ включён.</b> Нажми кнопку ниже.","parse_mode":"HTML","reply_markup":test_keyboard()})
    elif text=="/pay": send_invoice(chat_id)
    elif text=="/catalog":
        catalog=list(books().values()); names="\n".join(f"• {x['title']}" for x in catalog[:30]) or "Пока пусто."; tg("sendMessage",{"chat_id":chat_id,"text":f"📚 В Telegram-каталоге: <b>{len(catalog)}</b> книг.\n\n{names}","parse_mode":"HTML"})
    elif text=="/debug":
        state=events(); state["catalog_count"]=len(books()); state["access"]=has_access(user.get("id",chat_id)); tg("sendMessage",{"chat_id":chat_id,"text":"🔎 <pre>"+json.dumps(state,ensure_ascii=False,indent=2)+"</pre>","parse_mode":"HTML"})
    elif text=="/book":
        result=user_record(user.get("id",chat_id)).get("result",{})
        if isinstance(result,dict) and result.get("book"): send_book(chat_id,result["book"],result.get("archetype",""))
        else: tg("sendMessage",{"chat_id":chat_id,"text":"Сначала пройди тест."})

def handle_update(update):
    kind=next((k for k in ("channel_post","edited_channel_post","message","callback_query","pre_checkout_query") if k in update),"unknown"); record_event(kind,update)
    pre=update.get("pre_checkout_query")
    if pre:
        valid=str(pre.get("invoice_payload","")).startswith("quiz_access:"); payload={"pre_checkout_query_id":pre["id"],"ok":valid}
        if not valid: payload["error_message"]="Заказ не найден."
        tg("answerPreCheckoutQuery",payload); return
    callback=update.get("callback_query")
    if callback:
        if callback.get("data")=="pay_quiz": tg("answerCallbackQuery",{"callback_query_id":callback["id"]}); send_invoice(callback.get("message",{}).get("chat",{}).get("id"))
        return
    for key in ("channel_post","edited_channel_post"):
        post=update.get(key)
        if post:
            indexed=register_book(post); log.info("CHANNEL POST chat=%s title=%s file=%s indexed=%s",post.get("chat",{}).get("id"),post.get("chat",{}).get("title"),(post.get("document") or {}).get("file_name"),indexed); return
    message=update.get("message")
    if message: handle_message(message)

@app.get("/")
def root(): return jsonify({"ok":True,"service":"book-quiz","version":APP_VERSION,"app":f"{RENDER_EXTERNAL_URL}/app"})
@app.get("/app")
def mini_app(): return send_from_directory(".","index.html")
@app.get("/health")
def health():
    try: info=tg("getWebhookInfo").get("result",{})
    except Exception as exc: info={"error":str(exc)}
    state=events(); return jsonify({"ok":True,"version":APP_VERSION,"webhook_info":info,"expected_allowed_updates":ALLOWED_UPDATES,"web_app_url":WEB_APP_URL,"telegram_book_count":len(books()),"books_db":str(BOOKS_DB_PATH),"books_db_exists":BOOKS_DB_PATH.exists(),"last_update_type":state.get("last_update_type"),"last_channel_chat_id":state.get("last_channel_chat_id"),"last_channel_title":state.get("last_channel_title"),"last_channel_message_id":state.get("last_channel_message_id"),"last_channel_has_document":state.get("last_channel_has_document"),"last_channel_file_name":state.get("last_channel_file_name")})
@app.get("/check-access")
def check_access():
    user_id=request.args.get("user_id","").strip(); item=user_record(user_id); return jsonify({"ok":True,"paid":bool(user_id and (item.get("paid") or item.get("test_access"))),"test":bool(item.get("test_access")),"real_paid":bool(item.get("paid"))})
@app.get("/setup-webhook")
def setup_webhook_route():
    try:
        result=setup_webhook(); info=tg("getWebhookInfo").get("result",{}); return jsonify({"ok":True,"set_webhook":result,"webhook_info":info,"expected_allowed_updates":ALLOWED_UPDATES})
    except Exception as exc: log.exception("Webhook setup failed"); return jsonify({"ok":False,"error":str(exc)}),500
@app.post("/telegram-webhook")
def telegram_webhook():
    update=request.get_json(silent=True) or {}; log.info("TELEGRAM UPDATE keys=%s id=%s",sorted(update.keys()),update.get("update_id"))
    try: handle_update(update)
    except Exception: log.exception("Webhook update failed")
    return jsonify({"ok":True})

def setup_webhook():
    payload={"url":WEBHOOK_URL,"drop_pending_updates":False,"allowed_updates":ALLOWED_UPDATES}; result=tg("setWebhook",payload); log.info("Webhook configured: %s",result); return result

if __name__=="__main__": os.execvp("gunicorn",["gunicorn","--workers","1","--bind",f"0.0.0.0:{os.getenv('PORT','10000')}","wsgi:app"])
