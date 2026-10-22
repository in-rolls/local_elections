"""Structured event logging for repository commands.

Command reports remain on stdout for people to read. Operational events go to
stderr as JSON Lines so a long harvest or OCR run can be monitored, searched,
and resumed without scraping prose. The implementation uses the standard
library logging API and its documented ``extra`` fields.
"""

import functools
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime

LOGGER_NAME = "local_elections"
LOG_LEVEL_ENV = "LOCAL_ELECTIONS_LOG_LEVEL"
LOG_FORMAT_ENV = "LOCAL_ELECTIONS_LOG_FORMAT"

_STANDARD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "taskName",
    "thread",
    "threadName",
}


class JsonFormatter(logging.Formatter):
    """Render one LogRecord as one stable JSON object."""

    def format(self, record):
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if (
                key not in _STANDARD_FIELDS
                and key != "event"
                and not key.startswith("_")
            ):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


class _PackageHandler(logging.StreamHandler):
    """Identify the handler this module owns without mutating Logger."""


def configure(stream=None):
    """Configure the package logger once and return it."""
    package_logger = logging.getLogger(LOGGER_NAME)
    if any(isinstance(handler, _PackageHandler) for handler in package_logger.handlers):
        return package_logger

    level_name = os.environ.get(LOG_LEVEL_ENV, "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = _PackageHandler(stream or sys.stderr)
    if os.environ.get(LOG_FORMAT_ENV, "json").lower() == "console":
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    else:
        handler.setFormatter(JsonFormatter())
    package_logger.addHandler(handler)
    package_logger.setLevel(level)
    package_logger.propagate = False
    return package_logger


def get_logger(module_name):
    """Return the package logger for a module, including ``python -m`` runs."""
    if module_name == "__main__":
        spec = getattr(sys.modules.get("__main__"), "__spec__", None)
        module_name = getattr(spec, "name", None) or module_name
    if not module_name.startswith(f"{LOGGER_NAME}."):
        module_name = f"{LOGGER_NAME}.command.{module_name}"
    return logging.getLogger(module_name)


def command(phase, **context):
    """Log the lifecycle of a command-line ``main`` function."""

    def decorate(function):
        module_name = function.__module__
        if module_name == "__main__":
            spec = getattr(sys.modules.get("__main__"), "__spec__", None)
            module_name = getattr(spec, "name", None) or module_name
        logger = get_logger(module_name)

        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            configure()
            fields = {"phase": phase, "command": module_name, **context}
            logger.info(
                "command started",
                extra={"event": "command_started", **fields},
            )
            started = time.monotonic()
            try:
                result = function(*args, **kwargs)
            except BaseException:
                logger.exception(
                    "command failed",
                    extra={
                        "event": "command_failed",
                        "duration_ms": round((time.monotonic() - started) * 1000),
                        **fields,
                    },
                )
                raise
            exit_code = result if isinstance(result, int) else 0
            event = "command_completed" if exit_code == 0 else "command_failed"
            method = logger.info if exit_code == 0 else logger.error
            method(
                "command completed" if exit_code == 0 else "command failed",
                extra={
                    "event": event,
                    "exit_code": exit_code,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    **fields,
                },
            )
            return result

        return wrapped

    return decorate
