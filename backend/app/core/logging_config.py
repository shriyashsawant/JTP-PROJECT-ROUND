"""
AuraMatch AI - Logging configuration.
Central place to set up the root logger so every module's `logging.getLogger(__name__)`
gets consistent formatting without each one configuring handlers itself.
"""
import logging
import sys
from contextvars import ContextVar

from app.core.config import settings

# Set by the request-logging middleware for the duration of each request, so
# every log line emitted anywhere during that request - not just the
# middleware's own access-log line - carries the same request_id. Defaults to
# "-" for logs emitted outside a request context (startup, background tasks).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet the noisiest third-party loggers down to warnings only - they'd
    # otherwise drown out our own request/access logs at DEBUG level.
    for noisy in ("httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
