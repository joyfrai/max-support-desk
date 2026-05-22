from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from support.max_payloads import (
    build_dedupe_key,
    get_attachments,
    get_chat_id,
    get_message,
    get_message_body,
    get_message_id,
    get_sender,
    get_text,
    normalize_user,
    unix_seconds_to_datetime,
)
from support.models import Conversation, MaxContact, Message, MessageAttachment, RawUpdate
from support.realtime import message_created_payload, publish_event
from support.services.notifications import notify_new_incoming_message

logger = logging.getLogger("support.webhook")


@dataclass(frozen=True)
class IngestResult:
    raw_update: RawUpdate
    duplicate: bool = False
    message: Message | None = None


def sanitized_headers(headers: dict[str, str]) -> dict[str, str]:
    blocked = {"x-max-bot-api-secret", "authorization", "cookie"}
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in blocked and not key.lower().startswith("x-csrftoken")
    }


def ingest_max_update(payload: dict[str, Any], *, headers: dict[str, str]) -> IngestResult:
    update_type = str(payload.get("update_type") or "")
    dedupe_key = build_dedupe_key(payload)
    chat_id = get_chat_id(payload)
    raw_update = RawUpdate(
        update_type=update_type,
        max_timestamp=unix_seconds_to_datetime(payload.get("timestamp")),
        max_chat_id=chat_id,
        dedupe_key=dedupe_key,
        payload=payload,
        headers=sanitized_headers(headers),
    )

    try:
        with transaction.atomic():
            raw_update.save()
            if update_type == "message_created":
                message = _process_message_created(raw_update, payload)
                raw_update.status = RawUpdate.Status.PROCESSED
                raw_update.processed_at = timezone.now()
                raw_update.save(update_fields=["status", "processed_at"])
                transaction.on_commit(
                    lambda: publish_event("message.created", message_created_payload(message))
                )
                transaction.on_commit(lambda: notify_new_incoming_message(message.id))
                logger.info(
                    "max_webhook_processed update_type=%s raw_update_id=%s message_id=%s",
                    update_type,
                    raw_update.id,
                    message.id,
                )
                return IngestResult(raw_update=raw_update, message=message)

            raw_update.status = RawUpdate.Status.IGNORED
            raw_update.processed_at = timezone.now()
            raw_update.save(update_fields=["status", "processed_at"])
            logger.info(
                "max_webhook_ignored update_type=%s raw_update_id=%s",
                update_type,
                raw_update.id,
            )
            return IngestResult(raw_update=raw_update)
    except IntegrityError:
        existing = RawUpdate.objects.get(dedupe_key=dedupe_key)
        logger.info(
            "max_webhook_duplicate update_type=%s raw_update_id=%s",
            update_type,
            existing.id,
        )
        return IngestResult(raw_update=existing, duplicate=True)
    except Exception as exc:
        if raw_update.pk:
            raw_update.status = RawUpdate.Status.FAILED
            raw_update.error_text = str(exc)[:2000]
            raw_update.processed_at = timezone.now()
            raw_update.save(update_fields=["status", "error_text", "processed_at"])
        logger.exception("max_webhook_failed update_type=%s raw_update_id=%s", update_type, raw_update.pk)
        raise


def _process_message_created(raw_update: RawUpdate, payload: dict[str, Any]) -> Message:
    message_payload = get_message(payload)
    sender_payload = get_sender(payload)
    normalized_user = normalize_user(sender_payload)
    if normalized_user is None:
        raise ValueError("message_created update has no sender.user_id")

    contact, _ = MaxContact.objects.update_or_create(
        max_user_id=normalized_user.max_user_id,
        defaults={
            "first_name": normalized_user.first_name,
            "last_name": normalized_user.last_name,
            "username": normalized_user.username,
            "is_bot": normalized_user.is_bot,
            "last_activity_time": normalized_user.last_activity_time,
            "legacy_name": normalized_user.legacy_name,
            "raw_user": normalized_user.raw_user,
            "last_seen_at": timezone.now(),
        },
    )

    conversation, _ = Conversation.objects.get_or_create(
        contact=contact,
        status__in=[Conversation.Status.NEW, Conversation.Status.OPEN, Conversation.Status.PENDING],
        defaults={
            "max_chat_id": get_chat_id(payload),
            "recipient_type": Conversation.RecipientType.CHAT if get_chat_id(payload) else Conversation.RecipientType.USER,
            "status": Conversation.Status.OPEN,
        },
    )
    if conversation.status == Conversation.Status.NEW:
        conversation.status = Conversation.Status.OPEN

    message = Message.objects.create(
        conversation=conversation,
        contact=contact,
        raw_update=raw_update,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        max_sender_user_id=normalized_user.max_user_id,
        max_message_id=get_message_id(message_payload),
        external_event_key=raw_update.dedupe_key,
        text=get_text(message_payload),
        content_type=_content_type_for_message(message_payload),
        raw_message=message_payload,
        provider_created_at=unix_seconds_to_datetime(message_payload.get("timestamp")),
        received_at=raw_update.received_at,
    )

    for attachment in get_attachments(message_payload):
        if not isinstance(attachment, dict):
            continue
        attachment_type = str(attachment.get("type") or MessageAttachment.AttachmentType.UNKNOWN)
        payload_data = attachment.get("payload")
        MessageAttachment.objects.create(
            message=message,
            conversation=conversation,
            contact=contact,
            direction=Message.Direction.INCOMING,
            sender_kind=Message.SenderKind.MAX_USER,
            attachment_type=_normalize_attachment_type(attachment_type),
            max_payload=payload_data if isinstance(payload_data, dict) else {},
            raw_attachment=attachment,
        )

    conversation.last_message = message
    conversation.last_message_at = message.provider_created_at or message.created_at
    conversation.unread_count = conversation.unread_count + 1
    conversation.save(update_fields=["status", "last_message", "last_message_at", "unread_count", "updated_at"])
    return message


def _content_type_for_message(message: dict[str, Any]) -> str:
    has_text = bool(get_text(message))
    has_attachments = bool(get_attachments(message))
    if has_text and has_attachments:
        return Message.ContentType.MIXED
    if has_attachments:
        return Message.ContentType.FILE
    return Message.ContentType.TEXT


def _normalize_attachment_type(value: str) -> str:
    allowed = {choice.value for choice in MessageAttachment.AttachmentType}
    return value if value in allowed else MessageAttachment.AttachmentType.UNKNOWN
