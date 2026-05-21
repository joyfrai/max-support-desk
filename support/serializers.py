from __future__ import annotations

from django.contrib.auth import get_user_model

from support.models import Conversation, MaxContact, Message


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
