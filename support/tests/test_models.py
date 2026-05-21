from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from support.models import Conversation, MaxContact, Message


@pytest.fixture
def contact(db) -> MaxContact:
    return MaxContact.objects.create(max_user_id="1001", username="client")


@pytest.fixture
def conversation(contact: MaxContact) -> Conversation:
    return Conversation.objects.create(contact=contact, status=Conversation.Status.OPEN)


@pytest.fixture
def manager(db):
    return get_user_model().objects.create_user(
        username="manager",
        password="secret",
        is_staff=True,
    )


def test_outgoing_manager_message_requires_manager_id(
    conversation: Conversation,
    contact: MaxContact,
) -> None:
    message = Message(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        text="Hello",
        send_status=Message.SendStatus.QUEUED,
    )

    with pytest.raises(ValidationError) as exc_info:
        message.full_clean()

    assert "manager" in exc_info.value.message_dict


def test_incoming_message_defaults_to_not_applicable_send_status(
    conversation: Conversation,
    contact: MaxContact,
) -> None:
    message = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        text="Need help",
    )

    assert message.send_status == Message.SendStatus.NOT_APPLICABLE


def test_display_order_uses_provider_timestamp_then_id(
    conversation: Conversation,
    contact: MaxContact,
    manager,
) -> None:
    now = timezone.now()
    later_in_max = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        text="second by MAX",
        provider_created_at=now - timedelta(seconds=10),
    )
    earlier_in_max = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        text="first by MAX",
        provider_created_at=now - timedelta(seconds=20),
    )
    outgoing = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        manager=manager,
        text="queued reply",
        send_status=Message.SendStatus.QUEUED,
    )

    ordered = list(Message.objects.for_display().values_list("id", flat=True))

    assert ordered == [earlier_in_max.id, later_in_max.id, outgoing.id]


def test_retry_failed_message_keeps_same_message_id(
    conversation: Conversation,
    contact: MaxContact,
    manager,
) -> None:
    message = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        manager=manager,
        text="retry me",
        send_status=Message.SendStatus.FAILED,
        send_attempts=3,
        last_error_code="timeout",
        last_error_text="MAX timeout",
    )

    original_id = message.id
    message.mark_for_retry()

    message.refresh_from_db()
    assert message.id == original_id
    assert message.send_status == Message.SendStatus.QUEUED
    assert message.last_error_code == ""
    assert message.last_error_text == ""
