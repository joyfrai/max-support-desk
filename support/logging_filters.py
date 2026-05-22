from __future__ import annotations

import logging
import re
from typing import Iterable

from django.conf import settings


TELEGRAM_BOT_URL_RE = re.compile(r"(https://api\.telegram\.org/bot)[^/\s\"]+")
AUTHORIZATION_RE = re.compile(r"((?:Authorization|authorization)['\"]?\s*[:=]\s*['\"]?)[^'\"\s,}]+")


class SecretRedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact_secrets(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configured_secrets() -> Iterable[str]:
    for name in ("MAX_BOT_TOKEN", "MAX_WEBHOOK_SECRET", "TELEGRAM_BOT_TOKEN"):
        value = getattr(settings, name, "")
        if isinstance(value, str) and len(value) >= 8:
            yield value


def redact_secrets(value: str) -> str:
    redacted = TELEGRAM_BOT_URL_RE.sub(r"\1<redacted>", value)
    redacted = AUTHORIZATION_RE.sub(r"\1<redacted>", redacted)
    for secret in configured_secrets():
        redacted = redacted.replace(secret, "<redacted>")
    return redacted
