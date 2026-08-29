import logging

from bot import app

log = logging.getLogger("book-quiz")

# Pure WSGI entrypoint. Webhook registration is intentionally NOT performed
# during every worker import; use /setup-webhook once after deployment.
log.info("Book Quiz WSGI application loaded")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
