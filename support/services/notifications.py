from __future__ import annotations

import logging
from html import escape
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.urls import reverse

from support.max_client import MaxClient
from support.models import Message

logger = logging.getLogger("support.notifications")

TELEGRAM_API_BASE_URL = "https://api.telegram.org"
NOTIFICATION_TIMEOUT_SECONDS = 5.0


def notify_new_incoming_message(message_id: int) -> None:
    message = (
        Message.objects.select_related("conversation", "contact")
        .filter(id=message_id)
        .first()
    )
    if message is None or message.direction != Message.Direction.INCOMING:
        return

    text = build_incoming_message_notification(message)
    _send_telegram_notification(text)
    _send_max_notification(text)


def build_incoming_message_notification(message: Message) -> str:
    contact = message.contact
    display_name = " ".join(part for part in [contact.last_name, contact.first_name] if part)
    if not display_name:
        display_name = contact.legacy_name or contact.username or f"MAX user {contact.max_user_id}"

    username = f"@{contact.username}" if contact.username else "-"
    message_text = message.text.strip() or "[без текста]"
    admin_link = _admin_chat_link(message)

    return "\n".join(
        [
            "<b>Новое сообщение в MAX Support Desk</b>",
            "",
            f"<b>Пользователь:</b> {escape(display_name)}",
            f"<b>MAX ID:</b> {escape(contact.max_user_id)}",
            f"<b>Никнейм:</b> {escape(username)}",
            f"<b>Чат:</b> #{message.conversation_id}",
            "",
            "<b>Сообщение:</b>",
            escape(_truncate_message(message_text)),
            "",
            f'<a href="{escape(admin_link, quote=True)}">Открыть чат в админке Django</a>',
        ]
    )


def _admin_chat_link(message: Message) -> str:
    path = reverse("admin_support_chats")
    query = urlencode({"conversation_id": message.conversation_id})
    relative_url = f"{path}?{query}"
    public_url = settings.SUPPORT_DESK_PUBLIC_URL.rstrip("/")
    if not public_url:
        return relative_url
    return f"{public_url}{relative_url}"


def _truncate_message(value: str, *, limit: int = 1200) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit - 1]}…"


def _send_telegram_notification(text: str) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_NOTIFICATION_CHAT_ID
    if not token or not chat_id:
        return
    try:
        response = httpx.post(
            f"{TELEGRAM_API_BASE_URL}/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=NOTIFICATION_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        logger.info("telegram_notification_sent message_length=%s", len(text))
    except Exception as exc:
        logger.warning("telegram_notification_failed error=%s", str(exc)[:500])


def _send_max_notification(text: str) -> None:
    chat_id = settings.MAX_NOTIFICATION_CHAT_ID
    if not settings.MAX_BOT_TOKEN or not chat_id:
        return
    try:
        MaxClient().send_message(chat_id=chat_id, text=text)
        logger.info("max_notification_sent message_length=%s", len(text))
    except Exception as exc:
        logger.warning("max_notification_failed error=%s", str(exc)[:500])
