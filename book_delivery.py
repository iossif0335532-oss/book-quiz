import json
import os
from pathlib import Path

import requests

BOOKS_DIR = Path(os.getenv("BOOKS_DIR", "books"))
BOOK_FILE_IDS = json.loads(os.getenv("BOOK_FILE_IDS", "{}") or "{}")


def normalize(value):
    chars = '.,!?;:()[]{}"\'–—-_/\\'
    text = str(value or "").lower()
    for ch in chars:
        text = text.replace(ch, " ")
    return " ".join(text.split())


def find_pdf(title):
    if not BOOKS_DIR.exists():
        return None
    wanted = normalize(title)
    for pdf in BOOKS_DIR.rglob("*.pdf"):
        stem = normalize(pdf.stem)
        if stem == wanted or (wanted and wanted in stem):
            return pdf
    words = [w for w in wanted.split() if len(w) >= 3]
    best = None
    best_score = 0
    for pdf in BOOKS_DIR.rglob("*.pdf"):
        stem = normalize(pdf.stem)
        score = sum(word in stem for word in words)
        if score > best_score:
            best, best_score = pdf, score
    return best if best and best_score >= max(1, len(words) // 2) else None


def send_book(bot_api, chat_id, title):
    file_id = BOOK_FILE_IDS.get(title)
    if file_id:
        response = requests.post(
            f"{bot_api}/sendDocument",
            data={"chat_id": chat_id, "document": file_id, "caption": f"📕 Твоя книга — «{title}»"},
            timeout=120,
        )
        response.raise_for_status()
        return True

    pdf = find_pdf(title)
    if not pdf:
        return False

    with pdf.open("rb") as fh:
        response = requests.post(
            f"{bot_api}/sendDocument",
            data={"chat_id": chat_id, "caption": f"📕 Твоя книга — «{title}»"},
            files={"document": (pdf.name, fh, "application/pdf")},
            timeout=120,
        )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(data)
    return True
