"""
Structured logging configuration.

Dev mode  → colored, human-readable lines to stdout.
Prod mode → JSON lines to stdout (one object per record, machine-parseable).

Usage:
    from utils.logging_config import configure_logging
    configure_logging(debug=settings.debug)   # call once at startup
"""

import json
import logging
import logging.config


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        if record.stack_info:
            obj["stack"] = self.formatStack(record.stack_info)
        return json.dumps(obj, ensure_ascii=False)


class _DevFormatter(logging.Formatter):
    """Human-readable colored output for development."""

    _COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35;1m", # bold magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelname, "")
        record = logging.makeLogRecord(record.__dict__)
        record.levelname = f"{color}{record.levelname:<8}{self._RESET}"
        return super().format(record)


def configure_logging(*, debug: bool = False) -> None:
    """Configure root logger and per-package levels. Call once at startup."""
    formatter = "dev" if debug else "json"
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": f"{__name__}._JsonFormatter"},
            "dev": {
                "()": f"{__name__}._DevFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s  %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": formatter,
            },
        },
        "root": {"handlers": ["console"], "level": "INFO"},
        "loggers": {
            # uvicorn already prints startup banners; silence its per-request access log
            # (our RequestLoggingMiddleware handles that with richer context)
            "uvicorn.access": {"propagate": False, "level": "WARNING"},
            "uvicorn.error":  {"propagate": True,  "level": "INFO"},
            # Suppress noisy low-level libraries in production
            "sqlalchemy.engine": {"propagate": True, "level": "WARNING"},
            "botocore":          {"propagate": True, "level": "WARNING"},
            "boto3":             {"propagate": True, "level": "WARNING"},
        },
    }
    logging.config.dictConfig(config)
