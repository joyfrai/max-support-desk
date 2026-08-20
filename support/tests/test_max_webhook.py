from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from support.models import Conversation, MaxContact, Message, MessageAttachment, RawUpdate
from support.services.ingest import _update_conversation_after_incoming_message


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
def test_max_webhook_rejects_when_secret_is_not_configured(client) -> None:
    response = client.post(
        reverse("max_webhook"),
        data=max_message_created_payload(),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert RawUpdate.objects.count() == 0


@pytest.mark.django_db
@override_settings(
    DEMO_LOGIN_HINTS=True,
    DEMO_WEBHOOK_RATE_LIMIT=1,
    DEMO_WEBHOOK_RATE_WINDOW=60,
    MAX_WEBHOOK_SECRET="secret",
)
def test_demo_max_webhook_rate_limits_requests(client) -> None:
    cache.clear()

    first_response = client.post(
        reverse("max_webhook"),
        data={"invalid": "json payload"},
        content_type="application/json",
        HTTP_X_MAX_BOT_API_SECRET="secret",
    )
    second_response = client.post(
        reverse("max_webhook"),
        data={"invalid": "json payload"},
        content_type="application/json",
        HTTP_X_MAX_BOT_API_SECRET="secret",
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert second_response["Retry-After"] == "60"

@pytest.mark.django_db
@override_settings(MAX_WEBHOOK_SECRET="secret")
def test_max_webhook_message_created_saves_db_first_entities(
    client,
    monkeypatch,
    django_capture_on_commit_callbacks,
) -> None:
    notified_message_ids = []
    monkeypatch.setattr(
        "support.services.ingest.notify_new_incoming_message",
        lambda message_id: notified_message_ids.append(message_id),
    )

    with django_capture_on_commit_callbacks(execute=True):
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
    assert attachment.original_file_name == "Изображение MAX"
    assert attachment.max_payload == {"photo_id": "p1"}
    assert attachment.raw_attachment["type"] == "image"
    assert notified_message_ids == [message.id]


@pytest.mark.django_db
@override_settings(MAX_WEBHOOK_SECRET="secret")
def test_max_webhook_incoming_file_attachment_keeps_display_name(client) -> None:
    payload = max_message_created_payload()
    payload["message"]["body"]["attachments"] = [
        {
            "type": "file",
            "payload": {"filename": "invoice.pdf", "token": "max-file-token"},
        }
    ]

    response = client.post(
        reverse("max_webhook"),
        data=payload,
        content_type="application/json",
        HTTP_X_MAX_BOT_API_SECRET="secret",
    )

    assert response.status_code == 200
    attachment = MessageAttachment.objects.get()
    assert attachment.attachment_type == MessageAttachment.AttachmentType.FILE
    assert attachment.original_file_name == "invoice.pdf"


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


@pytest.mark.django_db
@override_settings(MAX_WEBHOOK_SECRET="secret")
def test_max_webhook_uses_existing_active_conversation_when_duplicates_exist(client) -> None:
    contact = MaxContact.objects.create(max_user_id="1001", username="alex_client")
    first = Conversation.objects.create(contact=contact, status=Conversation.Status.OPEN, max_chat_id="555")
    Conversation.objects.create(contact=contact, status=Conversation.Status.PENDING, max_chat_id="555")

    response = client.post(
        reverse("max_webhook"),
        data=max_message_created_payload(),
        content_type="application/json",
        HTTP_X_MAX_BOT_API_SECRET="secret",
    )

    assert response.status_code == 200
    assert Message.objects.get().conversation == first


@pytest.mark.django_db
def test_incoming_message_update_increments_unread_count_from_database_value() -> None:
    contact = MaxContact.objects.create(max_user_id="1001", username="alex_client")
    conversation = Conversation.objects.create(contact=contact, status=Conversation.Status.OPEN, unread_count=3)
    stale_conversation = Conversation.objects.get(pk=conversation.pk)
    Conversation.objects.filter(pk=conversation.pk).update(unread_count=7)
    message = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        text="Need help",
    )

    _update_conversation_after_incoming_message(conversation=stale_conversation, message=message)

    conversation.refresh_from_db()
    assert conversation.unread_count == 8
