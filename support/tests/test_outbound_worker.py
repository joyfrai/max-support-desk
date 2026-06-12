from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from support.max_client import MaxApiError
from support.models import Conversation, DeliveryAttempt, MaxContact, Message, MessageAttachment
from support.services.outbound import _queued_outgoing_messages_for_claim, process_next_queued_message


class FakeMaxClient:
    def __init__(self, *, response: dict | None = None, error: Exception | None = None) -> None:
        self.response = response or {"message_id": "max-mid-1"}
        self.error = error
        self.sent: list[dict] = []
        self.uploaded: list[dict] = []

    def upload_media(self, *, kind: str, data: bytes, filename: str, content_type: str) -> dict:
        self.uploaded.append(
            {
                "kind": kind,
                "data": data,
                "filename": filename,
                "content_type": content_type,
            }
        )
        return {"type": kind, "payload": {"token": f"uploaded-{filename}"}}

    def send_message(self, *, chat_id: str, text: str, attachments: list[dict] | None = None) -> dict:
        self.sent.append({"chat_id": chat_id, "text": text, "attachments": attachments or []})
        if self.error:
            raise self.error
        return self.response


class AttachmentNotReadyThenSuccessClient(FakeMaxClient):
    def __init__(self, *, failures: int) -> None:
        super().__init__(response={"message_id": "max-after-retry"})
        self.failures = failures

    def send_message(self, *, chat_id: str, text: str, attachments: list[dict] | None = None) -> dict:
        self.sent.append({"chat_id": chat_id, "text": text, "attachments": attachments or []})
        if len(self.sent) <= self.failures:
            raise MaxApiError(400, '{"code":"attachment.not.ready"}')
        return self.response


@pytest.fixture
def manager(db):
    return get_user_model().objects.create_user(username="manager", is_staff=True)


@pytest.fixture
def contact(db) -> MaxContact:
    return MaxContact.objects.create(max_user_id="1001", username="client")


@pytest.fixture
def conversation(contact: MaxContact) -> Conversation:
    return Conversation.objects.create(
        contact=contact,
        status=Conversation.Status.OPEN,
        max_chat_id="555",
    )


def queued_message(conversation: Conversation, contact: MaxContact, manager, text: str) -> Message:
    return Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        manager=manager,
        text=text,
        send_status=Message.SendStatus.QUEUED,
    )


@pytest.mark.django_db
def test_process_next_queued_message_sends_oldest_queued_message(
    conversation,
    contact,
    manager,
) -> None:
    first = queued_message(conversation, contact, manager, "first")
    queued_message(conversation, contact, manager, "second")
    client = FakeMaxClient()

    processed = process_next_queued_message(max_client=client)

    assert processed == first
    assert client.sent == [{"chat_id": "555", "text": "first", "attachments": []}]


@pytest.mark.django_db
def test_process_next_queued_message_success_marks_sent_and_records_attempt(
    conversation,
    contact,
    manager,
) -> None:
    message = queued_message(conversation, contact, manager, "hello")
    client = FakeMaxClient(response={"message_id": "max-mid-2"})

    process_next_queued_message(max_client=client)

    message.refresh_from_db()
    assert message.send_status == Message.SendStatus.SENT
    assert message.max_message_id == "max-mid-2"
    assert message.sent_at is not None
    assert message.send_attempts == 1
    attempt = DeliveryAttempt.objects.get(message=message)
    assert attempt.attempt_no == 1
    assert attempt.status == DeliveryAttempt.Status.SUCCESS


@pytest.mark.django_db
def test_process_next_queued_message_logs_warning_when_max_message_id_is_missing(
    conversation,
    contact,
    manager,
    monkeypatch,
) -> None:
    warning_calls: list[tuple[object, ...]] = []

    def fake_warning(message, *args):
        warning_calls.append((message, *args))

    monkeypatch.setattr("support.services.outbound.logger.warning", fake_warning)
    message = queued_message(conversation, contact, manager, "hello")
    client = FakeMaxClient(response={"success": True, "message": {"status": "accepted"}})

    process_next_queued_message(max_client=client)

    message.refresh_from_db()
    assert message.send_status == Message.SendStatus.SENT
    assert message.max_message_id == ""
    assert warning_calls
    assert warning_calls[0][0] == "worker_message_sent_without_max_message_id message_id=%s response_shape=%s"
    assert warning_calls[0][1] == message.id
    assert warning_calls[0][2] == {"response_keys": ["message", "success"], "nested_keys": {"message": ["status"]}}


@pytest.mark.django_db
def test_process_next_queued_message_uploads_attachments_before_sending(
    conversation,
    contact,
    manager,
    tmp_path,
    settings,
) -> None:
    settings.MEDIA_ROOT = tmp_path
    message = queued_message(conversation, contact, manager, "file attached")
    attachment = MessageAttachment.objects.create(
        message=message,
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        manager=manager,
        attachment_type=MessageAttachment.AttachmentType.FILE,
        original_file_name="report.txt",
        mime_type="text/plain",
        upload_status=MessageAttachment.UploadStatus.PENDING,
    )
    attachment.stored_file.save("report.txt", SimpleUploadedFile("report.txt", b"report", "text/plain"))
    client = FakeMaxClient(response={"message_id": "max-with-file"})

    process_next_queued_message(max_client=client)

    message.refresh_from_db()
    attachment.refresh_from_db()
    attempt = DeliveryAttempt.objects.get(message=message)
    assert client.uploaded == [
        {
            "kind": "file",
            "data": b"report",
            "filename": "report.txt",
            "content_type": "text/plain",
        }
    ]
    assert client.sent == [
        {
            "chat_id": "555",
            "text": "file attached",
            "attachments": [{"type": "file", "payload": {"token": "uploaded-report.txt"}}],
        }
    ]
    assert message.send_status == Message.SendStatus.SENT
    assert attachment.upload_status == MessageAttachment.UploadStatus.UPLOADED
    assert attachment.max_payload == {"type": "file", "payload": {"token": "uploaded-report.txt"}}
    assert attachment.uploaded_at is not None
    assert attempt.request_payload["attachments_count"] == 1


@pytest.mark.django_db
def test_process_next_queued_message_retries_when_max_attachment_is_not_ready(
    conversation,
    contact,
    manager,
    monkeypatch,
) -> None:
    message = queued_message(conversation, contact, manager, "file attached")
    MessageAttachment.objects.create(
        message=message,
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        manager=manager,
        attachment_type=MessageAttachment.AttachmentType.FILE,
        original_file_name="report.csv",
        mime_type="text/csv",
        upload_status=MessageAttachment.UploadStatus.UPLOADED,
        max_payload={"type": "file", "payload": {"token": "uploaded-report"}},
    )
    sleeps = []
    monkeypatch.setattr("support.services.outbound.time.sleep", lambda seconds: sleeps.append(seconds))
    client = AttachmentNotReadyThenSuccessClient(failures=2)

    process_next_queued_message(max_client=client)

    message.refresh_from_db()
    assert message.send_status == Message.SendStatus.SENT
    assert message.max_message_id == "max-after-retry"
    assert sleeps == [10.0, 10.0]
    assert client.sent == [
        {
            "chat_id": "555",
            "text": "file attached",
            "attachments": [{"type": "file", "payload": {"token": "uploaded-report"}}],
        },
        {
            "chat_id": "555",
            "text": "file attached",
            "attachments": [{"type": "file", "payload": {"token": "uploaded-report"}}],
        },
        {
            "chat_id": "555",
            "text": "file attached",
            "attachments": [{"type": "file", "payload": {"token": "uploaded-report"}}],
        },
    ]
    attempt = DeliveryAttempt.objects.get(message=message)
    assert attempt.status == DeliveryAttempt.Status.SUCCESS


@pytest.mark.django_db
def test_process_next_queued_message_failure_marks_failed_and_records_attempt(
    conversation,
    contact,
    manager,
) -> None:
    message = queued_message(conversation, contact, manager, "hello")
    client = FakeMaxClient(error=RuntimeError("MAX is down"))

    process_next_queued_message(max_client=client)

    message.refresh_from_db()
    assert message.send_status == Message.SendStatus.FAILED
    assert message.send_attempts == 1
    assert message.last_error_text == "MAX is down"
    attempt = DeliveryAttempt.objects.get(message=message)
    assert attempt.status == DeliveryAttempt.Status.FAILED
    assert attempt.error_text == "MAX is down"


@pytest.mark.django_db
def test_process_next_queued_message_returns_none_when_queue_empty() -> None:
    assert process_next_queued_message(max_client=FakeMaxClient()) is None


@pytest.mark.django_db
def test_queued_outgoing_messages_for_claim_uses_row_lock_when_supported() -> None:
    queryset = _queued_outgoing_messages_for_claim(skip_locked=True)

    assert queryset.query.select_for_update is True
    assert queryset.query.select_for_update_skip_locked is True
