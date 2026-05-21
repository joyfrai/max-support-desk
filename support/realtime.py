from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger("support.realtime")

SUPPORT_GROUP = "support_staff"


def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("realtime_no_channel_layer event_type=%s", event_type)
        return
    async_to_sync(channel_layer.group_send)(
        SUPPORT_GROUP,
        {
            "type": "support.event",
            "event": event_type,
            "payload": payload,
        },
    )


def message_created_payload(message) -> dict[str, Any]:
    return {
        "conversation_id": message.conversation_id,
        "message_id": message.id,
        "last_message_id": message.id,
    }


def message_status_payload(message) -> dict[str, Any]:
    return {
        "conversation_id": message.conversation_id,
        "message_id": message.id,
        "send_status": message.send_status,
    }

