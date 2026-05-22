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
    assert payload["limit"] == 100
    assert payload["offset"] == 0
    assert payload["has_more"] is False


@pytest.mark.django_db
def test_conversations_api_paginates_by_limit_and_offset(client, staff_user) -> None:
    contacts = [
        MaxContact.objects.create(max_user_id=f"user-{index}", first_name="Тест", last_name=str(index))
        for index in range(3)
    ]
    now = timezone.now()
    for index, contact_item in enumerate(contacts):
        Conversation.objects.create(
            contact=contact_item,
            status=Conversation.Status.OPEN,
            last_message_at=now - timedelta(minutes=index),
        )
    client.force_login(staff_user)

    first = client.get(reverse("api_conversations"), {"limit": "2", "offset": "0"})
    second = client.get(reverse("api_conversations"), {"limit": "2", "offset": "2"})

    first_payload = as_json(first)
    second_payload = as_json(second)
    assert [item["contact"]["max_user_id"] for item in first_payload["conversations"]] == ["user-0", "user-1"]
    assert first_payload["has_more"] is True
    assert first_payload["next_offset"] == 2
    assert [item["contact"]["max_user_id"] for item in second_payload["conversations"]] == ["user-2"]
    assert second_payload["has_more"] is False


@pytest.mark.django_db
def test_conversations_api_empty_page_stops_pagination(client, staff_user) -> None:
    client.force_login(staff_user)

    response = client.get(reverse("api_conversations"), {"limit": "100", "offset": "100"})

    assert response.status_code == 200
    payload = as_json(response)
    assert payload["conversations"] == []
    assert payload["next_offset"] == 100
    assert payload["has_more"] is False


@pytest.mark.django_db
def test_conversations_api_searches_contacts(client, staff_user) -> None:
    target = MaxContact.objects.create(max_user_id="1001", username="ivan_support", first_name="Иван", last_name="Петров")
    other = MaxContact.objects.create(max_user_id="1002", username="maria_max", first_name="Мария", last_name="Смирнова")
    Conversation.objects.create(contact=target, status=Conversation.Status.OPEN)
    Conversation.objects.create(contact=other, status=Conversation.Status.OPEN)
    client.force_login(staff_user)

    response = client.get(reverse("api_conversations"), {"search": "Петров Иван"})

    assert response.status_code == 200
    payload = as_json(response)
    assert [item["contact"]["max_user_id"] for item in payload["conversations"]] == ["1001"]


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
    assert payload["messages"][0]["author_display"] == "@client"


@pytest.mark.django_db
def test_messages_api_handles_more_than_1000_messages(client, staff_user, conversation, contact) -> None:
    messages = [
        Message(
            conversation=conversation,
            contact=contact,
            direction=Message.Direction.INCOMING,
            sender_kind=Message.SenderKind.MAX_USER,
            text=f"message {index}",
        )
        for index in range(1005)
    ]
    Message.objects.bulk_create(messages)
    client.force_login(staff_user)

    response = client.get(reverse("api_conversation_messages", args=[conversation.id]))

    assert response.status_code == 200
    payload = as_json(response)
    assert len(payload["messages"]) == 1005
    assert payload["messages"][0]["text"] == "message 0"
    assert payload["messages"][-1]["text"] == "message 1004"


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
    payload = as_json(response)
    message = Message.objects.get(direction=Message.Direction.OUTGOING)
    assert message.text == "Hello from support"
    assert message.manager == staff_user
    assert message.send_status == Message.SendStatus.QUEUED
    assert payload["message"]["author_display"] == "Staff Manager"
    assert conversation.messages.filter(id=message.id).exists()
    assert ManagerActionLog.objects.filter(
        manager=staff_user,
        conversation=conversation,
        message=message,
        action="message.send",
    ).exists()


@pytest.mark.django_db
def test_manager_reply_marks_conversation_answered_without_marking_on_view(
    client,
    staff_user,
    conversation,
) -> None:
    conversation.unread_count = 3
    conversation.save(update_fields=["unread_count"])
    client.force_login(staff_user)

    view_response = client.get(reverse("api_conversation_messages", args=[conversation.id]))
    assert view_response.status_code == 200
    conversation.refresh_from_db()
    assert conversation.unread_count == 3

    reply_response = client.post(
        reverse("api_conversation_messages", args=[conversation.id]),
        data={"text": "Отвечено"},
        content_type="application/json",
    )

    assert reply_response.status_code == 201
    conversation.refresh_from_db()
    assert conversation.unread_count == 0
    assert as_json(reply_response)["conversation"]["unread_count"] == 0


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
