from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command

from support.models import Conversation, MaxContact, Message


def test_seed_demo_data_creates_preview_records(db) -> None:
    call_command("seed_demo_data", "--username", "demo-admin", "--password", "demo-pass-123", "--reset")

    User = get_user_model()
    user = User.objects.get(username="demo-admin")

    assert user.is_staff is True
    assert user.is_superuser is False
    assert user.has_perm("support.view_conversation")
    assert not user.has_perm("auth.view_user")
    assert MaxContact.objects.filter(max_user_id__startswith="demo-").count() == 10
    assert Conversation.objects.filter(contact__max_user_id__startswith="demo-").count() == 10
    assert Conversation.objects.filter(contact__max_user_id="demo-1006").first().messages.count() >= 15
    assert Conversation.objects.filter(contact__max_user_id="demo-1007").first().messages.count() >= 15
    assert Conversation.objects.filter(contact__max_user_id="demo-1008").first().messages.count() >= 15
    assert Conversation.objects.filter(contact__max_user_id="demo-1009").first().messages.count() >= 15
    assert Conversation.objects.filter(contact__max_user_id="demo-1010").first().messages.count() >= 15
    assert Message.objects.filter(direction=Message.Direction.INCOMING).exists()
    assert Message.objects.filter(direction=Message.Direction.OUTGOING, send_status=Message.SendStatus.FAILED).exists()
