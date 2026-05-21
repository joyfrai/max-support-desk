from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command

from support.models import Conversation, MaxContact, Message


def test_seed_demo_data_creates_preview_records(db) -> None:
    call_command("seed_demo_data", "--username", "demo-admin", "--password", "demo-pass-123", "--reset")

    User = get_user_model()
    user = User.objects.get(username="demo-admin")

    assert user.is_staff is True
    assert user.is_superuser is True
    assert MaxContact.objects.filter(max_user_id__startswith="demo-").count() == 3
    assert Conversation.objects.filter(contact__max_user_id__startswith="demo-").count() == 3
    assert Message.objects.filter(direction=Message.Direction.INCOMING).exists()
    assert Message.objects.filter(direction=Message.Direction.OUTGOING, send_status=Message.SendStatus.FAILED).exists()
