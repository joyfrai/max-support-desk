from __future__ import annotations

from pathlib import Path


def test_support_desk_renders_plain_messages_as_text() -> None:
    source = Path("frontend/src/SupportDeskApp.tsx").read_text(encoding="utf-8")

    assert 'type: message.attachments.length > 0 ? "custom" : "text"' in source
    assert 'type: message.attachments.length > 0 ? "custom" : "html"' not in source
