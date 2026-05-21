from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from support.realtime import SUPPORT_GROUP


class SupportEventsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self) -> None:
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not user.is_staff:
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(SUPPORT_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(SUPPORT_GROUP, self.channel_name)

    async def support_event(self, event: dict) -> None:
        await self.send_json(
            {
                "event": event["event"],
                "payload": event["payload"],
            }
        )

