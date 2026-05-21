from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def unix_seconds_to_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def unix_milliseconds_to_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def stable_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def get_message(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message")
    return message if isinstance(message, dict) else {}


def get_message_body(message: dict[str, Any]) -> dict[str, Any]:
    body = message.get("body")
    return body if isinstance(body, dict) else {}


def get_sender(payload: dict[str, Any]) -> dict[str, Any]:
    message = get_message(payload)
    sender = message.get("sender") or payload.get("user")
    return sender if isinstance(sender, dict) else {}


def get_text(message: dict[str, Any]) -> str:
    body = get_message_body(message)
    text = body.get("text")
    return str(text) if text is not None else ""


def get_attachments(message: dict[str, Any]) -> list[dict[str, Any]]:
    body = get_message_body(message)
    attachments = body.get("attachments")
    return attachments if isinstance(attachments, list) else []


def get_chat_id(payload: dict[str, Any]) -> str:
    value = payload.get("chat_id")
    if value is None:
        recipient = get_message(payload).get("recipient")
        if isinstance(recipient, dict):
            value = recipient.get("chat_id") or recipient.get("user_id")
    return str(value) if value not in (None, "") else ""


def get_message_id(message: dict[str, Any]) -> str:
    for key in ("message_id", "mid", "id"):
        value = message.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def build_dedupe_key(payload: dict[str, Any]) -> str:
    update_type = str(payload.get("update_type") or "unknown")
    chat_id = get_chat_id(payload)
    message = get_message(payload)
    message_id = get_message_id(message)
    if message_id:
        return f"{update_type}:chat:{chat_id}:message:{message_id}"
    timestamp = payload.get("timestamp") or message.get("timestamp")
    if chat_id and timestamp:
        return f"{update_type}:chat:{chat_id}:timestamp:{timestamp}"
    return f"{update_type}:hash:{stable_payload_hash(payload)}"


@dataclass(frozen=True)
class NormalizedUser:
    max_user_id: str
    first_name: str
    last_name: str
    username: str
    is_bot: bool
    last_activity_time: datetime | None
    legacy_name: str
    raw_user: dict[str, Any]


def normalize_user(raw_user: dict[str, Any]) -> NormalizedUser | None:
    user_id = raw_user.get("user_id")
    if user_id in (None, ""):
        return None
    return NormalizedUser(
        max_user_id=str(user_id),
        first_name=str(raw_user.get("first_name") or ""),
        last_name=str(raw_user.get("last_name") or ""),
        username=str(raw_user.get("username") or ""),
        is_bot=bool(raw_user.get("is_bot", False)),
        last_activity_time=unix_milliseconds_to_datetime(raw_user.get("last_activity_time")),
        legacy_name=str(raw_user.get("name") or ""),
        raw_user=raw_user,
    )

