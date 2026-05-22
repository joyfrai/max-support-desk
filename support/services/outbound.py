from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from support.max_client import MaxApiError, MaxClient
from support.models import DeliveryAttempt, Message, MessageAttachment
from support.realtime import message_status_payload, publish_event

logger = logging.getLogger("support.worker")


def process_next_queued_message(*, max_client: MaxClient | None = None) -> Message | None:
    max_client = max_client or MaxClient()
    with transaction.atomic():
        message = (
            Message.objects.select_related("conversation", "contact", "manager")
            .prefetch_related("attachments")
            .filter(direction=Message.Direction.OUTGOING, send_status=Message.SendStatus.QUEUED)
            .order_by("id")
            .first()
        )
        if message is None:
            return None
        message.send_status = Message.SendStatus.SENDING
        message.send_attempts += 1
        message.save(update_fields=["send_status", "send_attempts", "updated_at"])
        attempt = DeliveryAttempt.objects.create(
            message=message,
            attempt_no=message.send_attempts,
            status=DeliveryAttempt.Status.STARTED,
            request_payload={
                "chat_id": message.conversation.max_chat_id,
                "message_id": message.id,
                "has_text": bool(message.text),
                "attachments_count": message.attachments.count(),
            },
        )

    logger.info(
        "worker_message_picked message_id=%s conversation_id=%s attempt_no=%s",
        message.id,
        message.conversation_id,
        message.send_attempts,
    )

    try:
        if not message.conversation.max_chat_id:
            raise ValueError("Conversation has no max_chat_id")
        attachments = _upload_message_attachments(message=message, max_client=max_client)
        response_payload = max_client.send_message(
            chat_id=message.conversation.max_chat_id,
            text=message.text,
            attachments=attachments,
        )
    except Exception as exc:
        _mark_failed(message=message, attempt=attempt, exc=exc)
        return message

    max_message_id = str(
        response_payload.get("message_id")
        or response_payload.get("id")
        or response_payload.get("message", {}).get("message_id")
        or ""
    )
    with transaction.atomic():
        message.send_status = Message.SendStatus.SENT
        message.max_message_id = max_message_id
        message.sent_at = timezone.now()
        message.last_error_code = ""
        message.last_error_text = ""
        message.save(
            update_fields=[
                "send_status",
                "max_message_id",
                "sent_at",
                "last_error_code",
                "last_error_text",
                "updated_at",
            ]
        )
        attempt.status = DeliveryAttempt.Status.SUCCESS
        attempt.response_payload = response_payload
        attempt.http_status = 200
        attempt.save(update_fields=["status", "response_payload", "http_status"])
        transaction.on_commit(
            lambda: publish_event("message.status_changed", message_status_payload(message))
        )

    logger.info("worker_message_sent message_id=%s max_message_id=%s", message.id, max_message_id)
    return message


def _upload_message_attachments(*, message: Message, max_client: MaxClient) -> list[dict]:
    uploaded: list[dict] = []
    for attachment in message.attachments.all():
        if attachment.upload_status == MessageAttachment.UploadStatus.UPLOADED and attachment.max_payload:
            uploaded.append(attachment.max_payload)
            continue
        try:
            with attachment.stored_file.open("rb") as file_obj:
                data = file_obj.read()
            payload = max_client.upload_media(
                kind=_max_attachment_kind(attachment),
                data=data,
                filename=attachment.original_file_name or attachment.stored_file.name.rsplit("/", 1)[-1],
                content_type=attachment.mime_type or "application/octet-stream",
            )
        except Exception as exc:
            attachment.upload_status = MessageAttachment.UploadStatus.FAILED
            attachment.last_error_text = str(exc)[:2000]
            attachment.save(update_fields=["upload_status", "last_error_text"])
            raise

        attachment.max_payload = payload
        attachment.upload_status = MessageAttachment.UploadStatus.UPLOADED
        attachment.uploaded_at = timezone.now()
        attachment.last_error_text = ""
        attachment.save(
            update_fields=[
                "max_payload",
                "upload_status",
                "uploaded_at",
                "last_error_text",
            ]
        )
        uploaded.append(payload)
    return uploaded


def _max_attachment_kind(attachment: MessageAttachment) -> str:
    if attachment.attachment_type in {
        MessageAttachment.AttachmentType.IMAGE,
        MessageAttachment.AttachmentType.VIDEO,
        MessageAttachment.AttachmentType.AUDIO,
    }:
        return str(attachment.attachment_type)
    return MessageAttachment.AttachmentType.FILE


def _mark_failed(*, message: Message, attempt: DeliveryAttempt, exc: Exception) -> None:
    error_code = "max_api_error" if isinstance(exc, MaxApiError) else exc.__class__.__name__
    error_text = str(exc)[:2000]
    http_status = exc.status_code if isinstance(exc, MaxApiError) else None
    response_payload = {"body": exc.body} if isinstance(exc, MaxApiError) else {}
    with transaction.atomic():
        message.send_status = Message.SendStatus.FAILED
        message.last_error_code = error_code
        message.last_error_text = error_text
        message.save(update_fields=["send_status", "last_error_code", "last_error_text", "updated_at"])
        attempt.status = DeliveryAttempt.Status.FAILED
        attempt.http_status = http_status
        attempt.error_code = error_code
        attempt.error_text = error_text
        attempt.response_payload = response_payload
        attempt.save(
            update_fields=[
                "status",
                "http_status",
                "error_code",
                "error_text",
                "response_payload",
            ]
        )
        transaction.on_commit(
            lambda: publish_event("message.status_changed", message_status_payload(message))
        )
    logger.warning(
        "worker_message_failed message_id=%s error_code=%s error_text=%s",
        message.id,
        error_code,
        error_text,
    )
