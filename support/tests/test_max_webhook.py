from __future__ import annotations

import pytest
from django.test import override_settings
from django.urls import reverse

from support.models import Conversation, MaxContact, Message, RawUpdate


def max_message_created_payload() -> dict:
    return {
        "update_type": "message_created",
        "timestamp": 1_700_000_000,
        "chat_id": 555,
        "message": {
            "message_id": "mid-1",
            "timestamp": 1_700_000_005,
            "sender": {
                "user_id": 1001,
                "first_name": "Alex",
                "last_name": "Client",
                "username": "alex_client",
                "is_bot": False,
                "last_activity_time": 1_700_000_006_000,
                "name": "Alex legacy",
            },
            "recipient": {"chat_id": 555, "type": "chat"},
            "body": {
                "text": "Need help",
                "attachments": [
                    {
                        "type": "image",
                        "payload": {"photo_id": "p1"},
                    }
                ],
            },
        },
    }


@pytest.mark.django_db
@override_settings(MAX_WEBHOOK_SECRET="secret")
def test_max_webhook_rejects_invalid_secret(client) -> None:
    response = client.post(
        reverse("max_webhook"),
        data=max_message_created_payload(),
        content_type="application/json",
        HTTP_X_MAX_BOT_API_SECRET="wrong",
    )

    assert response.status_code == 403
    assert RawUpdate.objects.count() == 0


@pytest.mark.django_db
@override_settings(MAX_WEBHOOK_SECRET="secret")
def test_max_webhook_message_created_saves_db_first_entities(client) -> None:
    response = client.post(
        reverse("max_webhook"),
        data=max_message_created_payload(),
        content_type="application/json",
        HTTP_X_MAX_BOT_API_SECRET="secret",
    )

    assert response.status_code == 200

    raw_update = RawUpdate.objects.get()
    assert raw_update.update_type == "message_created"
    assert raw_update.status == RawUpdate.Status.PROCESSED
    assert raw_update.payload["message"]["body"]["text"] == "Need help"

    contact = MaxContact.objects.get()
    assert contact.max_user_id == "1001"
    assert contact.username == "alex_client"
    assert contact.legacy_name == "Alex legacy"
    assert contact.raw_user["user_id"] == 1001

    conversation = Conversation.objects.get()
    assert conversation.contact == contact
    assert conversation.max_chat_id == "555"
    assert conversation.status == Conversation.Status.OPEN
    assert conversation.unread_count == 1

    message = Message.objects.get()
    assert message.raw_update == raw_update
    assert message.conversation == conversation
    assert message.contact == contact
    assert message.direction == Message.Direction.INCOMING
    assert message.sender_kind == Message.SenderKind.MAX_USER
    assert message.max_sender_user_id == "1001"
    assert message.max_message_id == "mid-1"
    assert message.text == "Need help"
    assert message.provider_created_at is not None
    assert message.attachments.count() == 1

    attachment = message.attachments.get()
    assert attachment.attachment_type == "image"
    assert attachment.max_payload == {"photo_id": "p1"}
    assert attachment.raw_attachment["type"] == "image"


@pytest.mark.django_db
@override_settings(MAX_WEBHOOK_SECRET="secret")
def test_max_webhook_duplicate_dedupe_key_does_not_duplicate_message(client) -> None:
    payload = max_message_created_payload()
    for _ in range(2):
        response = client.post(
            reverse("max_webhook"),
            data=payload,
            content_type="application/json",
            HTTP_X_MAX_BOT_API_SECRET="secret",
        )
        assert response.status_code == 200

    assert RawUpdate.objects.count() == 1
    assert Message.objects.count() == 1
    assert Conversation.objects.count() == 1
    assert MaxContact.objects.count() == 1
