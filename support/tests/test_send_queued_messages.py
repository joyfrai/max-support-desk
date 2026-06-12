from __future__ import annotations

import pytest
from django.db.utils import OperationalError

from support.management.commands.send_queued_messages import Command


def test_worker_retries_after_operational_error(monkeypatch) -> None:
    events: list[object] = []

    def fake_process_next_queued_message():
        if not events:
            events.append("db_error")
            raise OperationalError("db down")
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        "support.management.commands.send_queued_messages.process_next_queued_message",
        fake_process_next_queued_message,
    )
    monkeypatch.setattr(
        "support.management.commands.send_queued_messages.connections.close_all",
        lambda: events.append("close_all"),
    )
    monkeypatch.setattr("support.management.commands.send_queued_messages.time.sleep", lambda seconds: events.append(seconds))

    with pytest.raises(KeyboardInterrupt):
        Command().handle(once=False, sleep=1.0, db_retry_sleep=7.5)

    assert events == ["db_error", "close_all", 7.5]


def test_worker_once_still_raises_operational_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "support.management.commands.send_queued_messages.process_next_queued_message",
        lambda: (_ for _ in ()).throw(OperationalError("db down")),
    )

    with pytest.raises(OperationalError):
        Command().handle(once=True, sleep=1.0, db_retry_sleep=7.5)
