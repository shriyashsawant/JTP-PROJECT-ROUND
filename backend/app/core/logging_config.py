"""
AuraMatch AI - Structured logging configuration using structlog.
Every log line is emitted as JSON with request_id, event name, and
structured context — machine-parseable by default, human-readable via
`python -m structlog.dev`.

The existing `logging.getLogger(__name__)` pattern continues to work;
structlog patches the standard library to emit JSON automatically.
"""

import logging
import sys
from contextvars import ContextVar

import structlog

from app.core.config import settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def add_request_id(logger: logging.Logger, method_name: str, event_dict: dict) -> dict:
    event_dict["request_id"] = request_id_var.get()
    return event_dict


def setup_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_request_id,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(logging.StreamHandler(sys.stdout))

    for noisy in ("httpx", "httpcore", "asyncio", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
