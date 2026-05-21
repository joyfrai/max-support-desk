from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from support.models import Conversation, DeliveryAttempt, ManagerActionLog, MaxContact, Message


@pytest.mark.django_db
def test_cleanup_support_logs_keeps_only_retention_window() -> None:
    manager = get_user_model().objects.create_user(username="manager", is_staff=True)
    contact = MaxContact.objects.create(max_user_id="1001")
    conversation = Conversation.objects.create(contact=contact)
    message = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        manager=manager,
        text="hello",
        send_status=Message.SendStatus.SENT,
    )
    old_action = ManagerActionLog.objects.create(manager=manager, action="old")
    fresh_action = ManagerActionLog.objects.create(manager=manager, action="fresh")
    old_attempt = DeliveryAttempt.objects.create(message=message, attempt_no=1)
    fresh_attempt = DeliveryAttempt.objects.create(message=message, attempt_no=2)

    cutoff_time = timezone.now() - timedelta(days=8)
    ManagerActionLog.objects.filter(id=old_action.id).update(created_at=cutoff_time)
    DeliveryAttempt.objects.filter(id=old_attempt.id).update(created_at=cutoff_time)

    call_command("cleanup_support_logs", "--days", "7")

    assert not ManagerActionLog.objects.filter(id=old_action.id).exists()
    assert ManagerActionLog.objects.filter(id=fresh_action.id).exists()
    assert not DeliveryAttempt.objects.filter(id=old_attempt.id).exists()
    assert DeliveryAttempt.objects.filter(id=fresh_attempt.id).exists()
