from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from support.models import Conversation, DeliveryAttempt, MaxContact, Message
from support.services.outbound import process_next_queued_message


class FakeMaxClient:
    def __init__(self, *, response: dict | None = None, error: Exception | None = None) -> None:
        self.response = response or {"message_id": "max-mid-1"}
        self.error = error
        self.sent: list[tuple[str, str]] = []

    def send_message(self, *, chat_id: str, text: str) -> dict:
        self.sent.append((chat_id, text))
        if self.error:
            raise self.error
        return self.response


@pytest.fixture
def manager(db):
    return get_user_model().objects.create_user(username="manager", is_staff=True)


@pytest.fixture
def contact(db) -> MaxContact:
    return MaxContact.objects.create(max_user_id="1001", username="client")


@pytest.fixture
def conversation(contact: MaxContact) -> Conversation:
    return Conversation.objects.create(
        contact=contact,
        status=Conversation.Status.OPEN,
        max_chat_id="555",
    )


def queued_message(conversation: Conversation, contact: MaxContact, manager, text: str) -> Message:
    return Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        manager=manager,
        text=text,
        send_status=Message.SendStatus.QUEUED,
    )


@pytest.mark.django_db
def test_process_next_queued_message_sends_oldest_queued_message(
    conversation,
    contact,
    manager,
) -> None:
    first = queued_message(conversation, contact, manager, "first")
    queued_message(conversation, contact, manager, "second")
    client = FakeMaxClient()

    processed = process_next_queued_message(max_client=client)

    assert processed == first
    assert client.sent == [("555", "first")]


@pytest.mark.django_db
def test_process_next_queued_message_success_marks_sent_and_records_attempt(
    conversation,
    contact,
    manager,
) -> None:
    message = queued_message(conversation, contact, manager, "hello")
    client = FakeMaxClient(response={"message_id": "max-mid-2"})

    process_next_queued_message(max_client=client)

    message.refresh_from_db()
    assert message.send_status == Message.SendStatus.SENT
    assert message.max_message_id == "max-mid-2"
    assert message.sent_at is not None
    assert message.send_attempts == 1
    attempt = DeliveryAttempt.objects.get(message=message)
    assert attempt.attempt_no == 1
    assert attempt.status == DeliveryAttempt.Status.SUCCESS


@pytest.mark.django_db
def test_process_next_queued_message_failure_marks_failed_and_records_attempt(
    conversation,
    contact,
    manager,
) -> None:
    message = queued_message(conversation, contact, manager, "hello")
    client = FakeMaxClient(error=RuntimeError("MAX is down"))

    process_next_queued_message(max_client=client)

    message.refresh_from_db()
    assert message.send_status == Message.SendStatus.FAILED
    assert message.send_attempts == 1
    assert message.last_error_text == "MAX is down"
    attempt = DeliveryAttempt.objects.get(message=message)
    assert attempt.status == DeliveryAttempt.Status.FAILED
    assert attempt.error_text == "MAX is down"


@pytest.mark.django_db
def test_process_next_queued_message_returns_none_when_queue_empty() -> None:
    assert process_next_queued_message(max_client=FakeMaxClient()) is None
