"""
Structured logging configuration (Phase E9).

Provides:
  - JSON structured log format for production
  - Text format for development
  - Request correlation ID via contextvars
  - User/org context injection into every log line

Concept:
  Structured logging emits machine-parseable JSON lines. Each log entry
  carries a correlation `request_id` (UUID) that links all logs from a
  single HTTP request. Uses Python's `contextvars` module to propagate
  request context without threading issues in async/threaded environments.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Context variables — set per-request by middleware, read by formatter
# ---------------------------------------------------------------------------

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)
org_id_var: ContextVar[int | None] = ContextVar("org_id", default=None)


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------


class JSONFormatter(logging.Formatter):
    """
    Emits log records as single-line JSON objects.

    Fields:
      - timestamp: ISO 8601 UTC
      - level: DEBUG/INFO/WARNING/ERROR/CRITICAL
      - logger: logger name
      - message: formatted message
      - request_id: correlation UUID (from middleware)
      - user_id: authenticated user (from auth context)
      - org_id: active organization (from auth context)
      - module/funcName/lineno: source location
      - exc_info: exception traceback (if present)
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
            "org_id": org_id_var.get(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


# ---------------------------------------------------------------------------
# Text Formatter (development)
# ---------------------------------------------------------------------------


class TextFormatter(logging.Formatter):
    """Human-readable format for local development."""

    FORMAT = (
        "%(asctime)s %(levelname)-8s [%(request_id)s] "
        "%(name)s:%(funcName)s:%(lineno)d — %(message)s"
    )

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.org_id = org_id_var.get()
        self._fmt = self.FORMAT
        return super().format(record)


# ---------------------------------------------------------------------------
# Setup function
# ---------------------------------------------------------------------------


def setup_logging(log_level: str = "INFO", log_format: str = "text") -> None:
    """
    Configure the root logger for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format — "json" for production, "text" for development.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates on reload
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
