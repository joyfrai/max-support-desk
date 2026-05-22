from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse

from support.models import Conversation, MaxContact, Message, MessageAttachment


def contact_to_dict(contact: MaxContact) -> dict:
    return {
        "id": contact.id,
        "max_user_id": contact.max_user_id,
        "username": contact.username,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "is_bot": contact.is_bot,
        "last_seen_at": contact.last_seen_at.isoformat() if contact.last_seen_at else None,
    }


def manager_display(manager: get_user_model()) -> str:
    full_name = manager.get_full_name().strip()
    return full_name or manager.get_username()


def author_display(message: Message) -> str:
    if message.direction == Message.Direction.INCOMING:
        contact = message.contact
        if contact.username:
            return f"@{contact.username}"
        full_name = " ".join(part for part in [contact.last_name, contact.first_name] if part)
        return full_name or f"MAX user {contact.max_user_id}"
    if message.sender_kind == Message.SenderKind.MANAGER and message.manager:
        return manager_display(message.manager)
    return "Система"


def attachment_to_dict(attachment: MessageAttachment) -> dict:
    file_name = attachment.original_file_name or attachment.stored_file.name.rsplit("/", 1)[-1] or "Вложение MAX"
    can_download = bool(attachment.stored_file) or _has_remote_attachment_url(attachment)
    return {
        "id": attachment.id,
        "file_name": file_name,
        "mime_type": attachment.mime_type,
        "size_bytes": attachment.size_bytes,
        "download_url": reverse("api_attachment_download", args=[attachment.id]) if can_download else "",
    }


def message_to_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "contact_id": message.contact_id,
        "direction": message.direction,
        "sender_kind": message.sender_kind,
        "author_kind": message.sender_kind,
        "author_display": author_display(message),
        "manager_id": message.manager_id,
        "text": message.text,
        "text_format": message.text_format,
        "content_type": message.content_type,
        "send_status": message.send_status,
        "provider_created_at": message.provider_created_at.isoformat() if message.provider_created_at else None,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        "sort_key": (
            message.provider_created_at.isoformat()
            if message.direction == Message.Direction.INCOMING and message.provider_created_at
            else message.created_at.isoformat()
        ),
        "attachments": [attachment_to_dict(attachment) for attachment in message.attachments.all()],
    }


def conversation_to_dict(conversation: Conversation) -> dict:
    return {
        "id": conversation.id,
        "contact": contact_to_dict(conversation.contact),
        "status": conversation.status,
        "assigned_to_id": conversation.assigned_to_id,
        "last_message_id": conversation.last_message_id,
        "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
        "unread_count": conversation.unread_count,
    }


def _has_remote_attachment_url(attachment: MessageAttachment) -> bool:
    return bool(_find_remote_url(attachment.max_payload) or _find_remote_url(attachment.raw_attachment))


def _find_remote_url(payload) -> str:
    if isinstance(payload, dict):
        for key in ("download_url", "file_url", "media_url", "url", "link"):
            value = payload.get(key)
            if isinstance(value, str) and value.startswith("https://"):
                return value
        for value in payload.values():
            found = _find_remote_url(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _find_remote_url(value)
            if found:
                return found
    return ""
