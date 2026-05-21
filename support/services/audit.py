from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AnonymousUser

from support.models import Conversation, ManagerActionLog, Message


def log_manager_action(
    *,
    manager,
    action: str,
    conversation: Conversation | None = None,
    message: Message | None = None,
    metadata: dict[str, Any] | None = None,
) -> ManagerActionLog:
    if isinstance(manager, AnonymousUser):
        manager = None
    return ManagerActionLog.objects.create(
        manager=manager,
        action=action,
        conversation=conversation,
        message=message,
        metadata=metadata or {},
    )

