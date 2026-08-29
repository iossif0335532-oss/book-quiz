import logging

from bot import app, setup_webhook

log = logging.getLogger("book-quiz")

try:
    setup_webhook()
except Exception:
    log.exception("Webhook setup failed during application startup")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
