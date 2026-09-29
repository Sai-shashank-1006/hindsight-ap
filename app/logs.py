"""Logging for the pipeline. Every step logs to "hindsight_ap"; API keys never reach a log line."""

from __future__ import annotations

import logging
import sys

from app.config import env

SECRET_VARS = ("GROQ_API_KEY", "HINDSIGHT_API_KEY")


class RedactSecrets(logging.Filter):
    """Replaces any configured API key in a log message with [redacted]."""

    def filter(self, record: logging.LogRecord) -> bool:
        secrets = [s for s in (env(name) for name in SECRET_VARS) if s]
        if secrets:
            message = record.getMessage()
            for secret in secrets:
                message = message.replace(secret, "[redacted]")
            record.msg, record.args = message, None
        return True


def configure_logging(fmt: str = "%(levelname)s hindsight_ap %(message)s") -> logging.Logger:
    """Idempotent: one console handler and one redaction filter, however often it is called."""
    logger = logging.getLogger("hindsight_ap")
    logger.setLevel(logging.INFO)
    if not any(isinstance(f, RedactSecrets) for f in logger.filters):
        logger.addFilter(RedactSecrets())
    if not any(getattr(h, "_hindsight_ap", False) for h in logger.handlers):
        try:  # a cp1252 console or pipe can't print ₹: escape it rather than raise inside logging
            sys.stderr.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt))
        handler._hindsight_ap = True
        logger.addHandler(handler)
    return logger
