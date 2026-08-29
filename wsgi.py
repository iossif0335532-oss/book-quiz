import logging

from bot import app, setup_webhook

log = logging.getLogger("book-quiz")

# Production entrypoint for Render/Gunicorn.
# Register the webhook when the worker starts so Telegram sends both user
# messages and channel posts to the same Flask endpoint.
try:
    result = setup_webhook()
    log.info("Telegram webhook configured: %s", result)
except Exception:
    log.exception("Webhook setup failed during application startup")

log.info("Book Quiz WSGI application loaded; production server should be Gunicorn")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
