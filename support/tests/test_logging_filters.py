from __future__ import annotations

import logging

from django.test import override_settings

from support.logging_filters import SecretRedactingFilter, redact_secrets


@override_settings(
    MAX_BOT_TOKEN="max-secret-token",
    MAX_WEBHOOK_SECRET="webhook-secret",
    TELEGRAM_BOT_TOKEN="123456:telegram-secret-token",
)
def test_redact_secrets_masks_configured_tokens_and_telegram_bot_urls() -> None:
    message = (
        "POST https://api.telegram.org/bot123456:telegram-secret-token/sendMessage "
        "Authorization=max-secret-token webhook-secret"
    )

    redacted = redact_secrets(message)

    assert "telegram-secret-token" not in redacted
    assert "max-secret-token" not in redacted
    assert "webhook-secret" not in redacted
    assert "https://api.telegram.org/bot<redacted>/sendMessage" in redacted


@override_settings(TELEGRAM_BOT_TOKEN="123456:telegram-secret-token")
def test_secret_redacting_filter_rewrites_log_record_message() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="GET https://api.telegram.org/bot123456:telegram-secret-token/getMe",
        args=(),
        exc_info=None,
    )

    assert SecretRedactingFilter().filter(record) is True
    assert record.getMessage() == "GET https://api.telegram.org/bot<redacted>/getMe"
