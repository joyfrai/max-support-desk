from __future__ import annotations

from pathlib import Path


def test_support_desk_opens_staff_websocket_for_realtime_updates() -> None:
    source = Path("frontend/src/SupportDeskApp.tsx").read_text()

    assert "new WebSocket" in source
    assert "/ws/support/" in source
    assert "message.created" in source
    assert "loadMessages(conversationId)" in source
