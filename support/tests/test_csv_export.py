from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from support.models import Conversation, ManagerActionLog, MaxContact, Message


@pytest.mark.django_db
def test_max_users_csv_export_requires_staff(client) -> None:
    response = client.get(reverse("admin_export_max_users_csv"))

    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


@pytest.mark.django_db
def test_max_users_csv_export_contains_support_columns(client) -> None:
    manager = get_user_model().objects.create_user(username="manager", is_staff=True)
    contact = MaxContact.objects.create(max_user_id="1001", username="client", first_name="Иван")
    conversation = Conversation.objects.create(
        contact=contact,
        status=Conversation.Status.OPEN,
        assigned_to=manager,
    )
    Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        text="hello",
    )
    client.force_login(manager)

    response = client.get(reverse("admin_export_max_users_csv"))

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv; charset=utf-8")
    assert response.content.startswith("\ufeff".encode("utf-8"))
    body = response.content.decode("utf-8-sig")
    assert "max_user_id,username,first_name,last_name,is_bot,last_activity_time" in body
    assert "conversation_count,message_count,last_message_at,active_conversation_status,assigned_to" in body
    assert "1001,client,Иван" in body
    assert ManagerActionLog.objects.filter(action="max_users.export_csv", manager=manager).exists()
