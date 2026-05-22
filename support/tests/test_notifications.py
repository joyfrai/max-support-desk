from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from support.models import Conversation, MaxContact, Message
from support.services.notifications import notify_new_incoming_message


@pytest.fixture
def contact(db) -> MaxContact:
    return MaxContact.objects.create(
        max_user_id="1001",
        username="client",
        first_name="Иван",
        last_name="Петров",
    )


@pytest.fixture
def incoming_message(contact: MaxContact) -> Message:
    conversation = Conversation.objects.create(contact=contact, max_chat_id="chat-1")
    return Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        max_sender_user_id=contact.max_user_id,
        text="Нужна помощь <с заказом>",
    )


@pytest.mark.django_db
@override_settings(
    TELEGRAM_BOT_TOKEN="",
    TELEGRAM_NOTIFICATION_CHAT_ID="",
    MAX_NOTIFICATION_CHAT_ID="",
)
def test_notify_new_incoming_message_skips_when_channels_are_not_configured(
    incoming_message,
    monkeypatch,
) -> None:
    telegram_calls = []
    max_calls = []
    monkeypatch.setattr("support.services.notifications.httpx.post", lambda *args, **kwargs: telegram_calls.append(args))
    monkeypatch.setattr("support.services.notifications.MaxClient", lambda: max_calls.append("created"))

    notify_new_incoming_message(incoming_message.id)

    assert telegram_calls == []
    assert max_calls == []


@pytest.mark.django_db
@override_settings(
    TELEGRAM_BOT_TOKEN="telegram-token",
    TELEGRAM_NOTIFICATION_CHAT_ID="-1001",
    MAX_BOT_TOKEN="max-token",
    MAX_NOTIFICATION_CHAT_ID="max-channel-1",
    SUPPORT_DESK_PUBLIC_URL="https://support.example.com",
)
def test_notify_new_incoming_message_sends_user_message_and_admin_link(
    incoming_message,
    monkeypatch,
) -> None:
    telegram_calls = []
    max_calls = []

    class FakeResponse:
        status_code = 200
        content = b'{"ok": true}'

        def raise_for_status(self) -> None:
            return None

    class FakeMaxClient:
        def send_message(self, *, chat_id: str, text: str, attachments=None) -> dict:
            max_calls.append({"chat_id": chat_id, "text": text, "attachments": attachments})
            return {"message_id": "notification-1"}

    def fake_post(url, *, json, timeout):
        telegram_calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("support.services.notifications.httpx.post", fake_post)
    monkeypatch.setattr("support.services.notifications.MaxClient", FakeMaxClient)

    notify_new_incoming_message(incoming_message.id)

    assert telegram_calls[0]["url"] == "https://api.telegram.org/bottelegram-token/sendMessage"
    telegram_text = telegram_calls[0]["json"]["text"]
    assert telegram_calls[0]["json"]["chat_id"] == "-1001"
    assert "Петров Иван" in telegram_text
    assert "@client" in telegram_text
    assert "Нужна помощь &lt;с заказом&gt;" in telegram_text
    assert "https://support.example.com/admin/support/chats/" in telegram_text
    assert max_calls == [
        {
            "chat_id": "max-channel-1",
            "text": telegram_text,
            "attachments": None,
        }
    ]


@pytest.mark.django_db
@override_settings(
    TELEGRAM_BOT_TOKEN="telegram-token",
    TELEGRAM_NOTIFICATION_CHAT_ID="-1001",
    MAX_NOTIFICATION_CHAT_ID="",
)
def test_notify_new_incoming_message_ignores_outgoing_messages(incoming_message, monkeypatch) -> None:
    manager = get_user_model().objects.create_user(username="manager", is_staff=True)
    incoming_message.direction = Message.Direction.OUTGOING
    incoming_message.sender_kind = Message.SenderKind.MANAGER
    incoming_message.manager = manager
    incoming_message.send_status = Message.SendStatus.QUEUED
    incoming_message.save(update_fields=["direction", "sender_kind", "manager", "send_status", "updated_at"])
    telegram_calls = []
    monkeypatch.setattr("support.services.notifications.httpx.post", lambda *args, **kwargs: telegram_calls.append(args))

    notify_new_incoming_message(incoming_message.id)

    assert telegram_calls == []
