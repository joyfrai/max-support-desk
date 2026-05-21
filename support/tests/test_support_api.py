from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from support.models import Conversation, ManagerActionLog, MaxContact, Message


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(
        username="staff",
        first_name="Staff",
        last_name="Manager",
        password="secret",
        is_staff=True,
    )


@pytest.fixture
def other_staff(db):
    return get_user_model().objects.create_user(
        username="other",
        password="secret",
        is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    return get_user_model().objects.create_user(username="regular", password="secret")


@pytest.fixture
def contact(db) -> MaxContact:
    return MaxContact.objects.create(max_user_id="1001", username="client")


@pytest.fixture
def conversation(contact: MaxContact) -> Conversation:
    return Conversation.objects.create(contact=contact, status=Conversation.Status.OPEN)


def as_json(response):
    return json.loads(response.content.decode("utf-8"))


@pytest.mark.django_db
def test_conversations_api_requires_staff(client, regular_user) -> None:
    client.force_login(regular_user)

    response = client.get(reverse("api_conversations"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_conversations_api_lists_all_chats_for_staff(client, staff_user, conversation) -> None:
    client.force_login(staff_user)

    response = client.get(reverse("api_conversations"))

    assert response.status_code == 200
    payload = as_json(response)
    assert payload["conversations"][0]["id"] == conversation.id
    assert payload["conversations"][0]["contact"]["username"] == "client"


@pytest.mark.django_db
def test_messages_api_orders_by_display_order(client, staff_user, conversation, contact) -> None:
    now = timezone.now()
    later = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        text="later",
        provider_created_at=now - timedelta(seconds=5),
    )
    earlier = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        text="earlier",
        provider_created_at=now - timedelta(seconds=10),
    )
    client.force_login(staff_user)

    response = client.get(reverse("api_conversation_messages", args=[conversation.id]))

    assert response.status_code == 200
    payload = as_json(response)
    assert [item["id"] for item in payload["messages"]] == [earlier.id, later.id]
    assert payload["messages"][0]["author_display"] == "MAX: @client"


@pytest.mark.django_db
def test_staff_can_create_queued_outgoing_message_and_audit_log(
    client,
    staff_user,
    conversation,
    contact,
) -> None:
    client.force_login(staff_user)

    response = client.post(
        reverse("api_conversation_messages", args=[conversation.id]),
        data={"text": "Hello from support"},
        content_type="application/json",
    )

    assert response.status_code == 201
    message = Message.objects.get(direction=Message.Direction.OUTGOING)
    assert message.text == "Hello from support"
    assert message.manager == staff_user
    assert message.send_status == Message.SendStatus.QUEUED
    assert conversation.messages.filter(id=message.id).exists()
    assert ManagerActionLog.objects.filter(
        manager=staff_user,
        conversation=conversation,
        message=message,
        action="message.send",
    ).exists()


@pytest.mark.django_db
def test_assigned_to_does_not_lock_replies(
    client,
    staff_user,
    other_staff,
    conversation,
) -> None:
    conversation.assigned_to = other_staff
    conversation.save(update_fields=["assigned_to"])
    client.force_login(staff_user)

    response = client.post(
        reverse("api_conversation_messages", args=[conversation.id]),
        data={"text": "I can still reply"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert Message.objects.get(direction=Message.Direction.OUTGOING).manager == staff_user


@pytest.mark.django_db
def test_retry_failed_message_reuses_same_message_id(client, staff_user, conversation, contact) -> None:
    failed = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        manager=staff_user,
        text="retry",
        send_status=Message.SendStatus.FAILED,
        last_error_code="timeout",
        last_error_text="MAX timeout",
    )
    client.force_login(staff_user)

    response = client.post(reverse("api_message_retry", args=[failed.id]))

    assert response.status_code == 200
    failed.refresh_from_db()
    assert failed.send_status == Message.SendStatus.QUEUED
    assert Message.objects.count() == 1
    assert ManagerActionLog.objects.filter(action="message.retry", message=failed).exists()


@pytest.mark.django_db
def test_assign_and_close_conversation_create_audit_logs(client, staff_user, conversation) -> None:
    client.force_login(staff_user)

    assign_response = client.post(reverse("api_conversation_assign", args=[conversation.id]))
    close_response = client.post(reverse("api_conversation_close", args=[conversation.id]))

    assert assign_response.status_code == 200
    assert close_response.status_code == 200
    conversation.refresh_from_db()
    assert conversation.assigned_to == staff_user
    assert conversation.status == Conversation.Status.CLOSED
    assert ManagerActionLog.objects.filter(action="conversation.assign", conversation=conversation).exists()
    assert ManagerActionLog.objects.filter(action="conversation.close", conversation=conversation).exists()
