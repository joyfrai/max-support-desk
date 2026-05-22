from __future__ import annotations

import hashlib

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from support.models import Conversation, ManagerActionLog, MaxContact, Message, MessageAttachment
from support.serializers import attachment_to_dict


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(username="staff", password="secret", is_staff=True)


@pytest.fixture
def contact(db) -> MaxContact:
    return MaxContact.objects.create(max_user_id="1001", username="client")


@pytest.fixture
def conversation(contact: MaxContact) -> Conversation:
    return Conversation.objects.create(contact=contact, status=Conversation.Status.OPEN, max_chat_id="555")


@pytest.mark.django_db
def test_manager_can_upload_attachment_with_outgoing_message(client, staff_user, conversation, tmp_path, settings) -> None:
    settings.MEDIA_ROOT = tmp_path
    client.force_login(staff_user)
    payload = b"hello file"
    upload = SimpleUploadedFile("hello.txt", payload, content_type="text/plain")

    response = client.post(
        reverse("api_conversation_messages", args=[conversation.id]),
        data={"text": "See file", "file": upload},
    )

    assert response.status_code == 201
    message = Message.objects.get(direction=Message.Direction.OUTGOING)
    assert message.content_type == Message.ContentType.MIXED
    attachment = MessageAttachment.objects.get(message=message)
    assert attachment.original_file_name == "hello.txt"
    assert attachment.mime_type == "text/plain"
    assert attachment.size_bytes == len(payload)
    assert attachment.sha256 == hashlib.sha256(payload).hexdigest()
    assert attachment.upload_status == MessageAttachment.UploadStatus.PENDING
    response_payload = response.json()
    assert response_payload["message"]["attachments"] == [
        {
            "id": attachment.id,
            "file_name": "hello.txt",
            "mime_type": "text/plain",
            "size_bytes": len(payload),
            "download_url": reverse("api_attachment_download", args=[attachment.id]),
        }
    ]
    assert ManagerActionLog.objects.filter(action="attachment.upload", message=message).exists()


@pytest.mark.django_db
def test_manager_can_upload_attachment_without_text(client, staff_user, conversation, tmp_path, settings) -> None:
    settings.MEDIA_ROOT = tmp_path
    client.force_login(staff_user)
    file_payload = b"file only"
    upload = SimpleUploadedFile("only.txt", file_payload, content_type="text/plain")

    response = client.post(
        reverse("api_conversation_messages", args=[conversation.id]),
        data={"file": upload},
    )

    assert response.status_code == 201
    message = Message.objects.get(direction=Message.Direction.OUTGOING)
    attachment = MessageAttachment.objects.get(message=message)
    assert message.text == ""
    assert message.content_type == Message.ContentType.FILE
    assert response.json()["message"]["attachments"][0]["download_url"] == reverse(
        "api_attachment_download",
        args=[attachment.id],
    )


@pytest.mark.django_db
def test_attachment_download_is_staff_protected(client, staff_user, conversation, contact, tmp_path, settings) -> None:
    settings.MEDIA_ROOT = tmp_path
    message = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        manager=staff_user,
        text="file",
        send_status=Message.SendStatus.QUEUED,
    )
    attachment = MessageAttachment.objects.create(
        message=message,
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        manager=staff_user,
        original_file_name="hello.txt",
        mime_type="text/plain",
    )
    attachment.stored_file.save("hello.txt", SimpleUploadedFile("hello.txt", b"hello", "text/plain"))

    anonymous_response = client.get(reverse("api_attachment_download", args=[attachment.id]))
    assert anonymous_response.status_code == 403

    client.force_login(staff_user)
    response = client.get(reverse("api_attachment_download", args=[attachment.id]))

    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain"


@pytest.mark.django_db
def test_incoming_attachment_without_stored_file_has_non_empty_display_name(conversation, contact) -> None:
    message = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        text="",
    )
    attachment = MessageAttachment.objects.create(
        message=message,
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        attachment_type=MessageAttachment.AttachmentType.FILE,
    )

    payload = attachment_to_dict(attachment)

    assert payload["file_name"] == "Вложение MAX"
    assert payload["download_url"] == ""


@pytest.mark.django_db
def test_incoming_attachment_with_max_url_is_downloaded_on_first_staff_click(
    client,
    staff_user,
    conversation,
    contact,
    tmp_path,
    settings,
    monkeypatch,
) -> None:
    settings.MEDIA_ROOT = tmp_path
    message = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        text="",
    )
    attachment = MessageAttachment.objects.create(
        message=message,
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        attachment_type=MessageAttachment.AttachmentType.FILE,
        original_file_name="invoice.pdf",
        max_payload={"url": "https://files.max.ru/invoice.pdf"},
    )

    class FakeResponse:
        status_code = 200
        content = b"pdf bytes"
        headers = {"content-type": "application/pdf"}
        is_redirect = False

    http_calls = []

    def fake_get(url, *, headers, follow_redirects, timeout):
        http_calls.append(
            {
                "url": url,
                "headers": headers,
                "follow_redirects": follow_redirects,
                "timeout": timeout,
            }
        )
        return FakeResponse()

    monkeypatch.setattr("support.views_api._host_resolves_to_public_ips", lambda hostname: True)
    monkeypatch.setattr("support.views_api.httpx.get", fake_get)
    client.force_login(staff_user)

    payload = attachment_to_dict(attachment)
    response = client.get(payload["download_url"])

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"pdf bytes"
    assert response["Content-Type"] == "application/pdf"
    assert http_calls == [
        {
            "url": "https://files.max.ru/invoice.pdf",
            "headers": {},
            "follow_redirects": False,
            "timeout": 120.0,
        }
    ]
    attachment.refresh_from_db()
    assert attachment.stored_file
    assert attachment.size_bytes == len(b"pdf bytes")
    assert attachment.sha256 == hashlib.sha256(b"pdf bytes").hexdigest()
    assert ManagerActionLog.objects.filter(action="attachment.download", message=message).exists()


@pytest.mark.django_db
def test_incoming_attachment_download_blocks_private_network_urls(
    client,
    staff_user,
    conversation,
    contact,
    tmp_path,
    settings,
    monkeypatch,
) -> None:
    settings.MEDIA_ROOT = tmp_path
    message = Message.objects.create(
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        text="",
    )
    attachment = MessageAttachment.objects.create(
        message=message,
        conversation=conversation,
        contact=contact,
        direction=Message.Direction.INCOMING,
        sender_kind=Message.SenderKind.MAX_USER,
        attachment_type=MessageAttachment.AttachmentType.FILE,
        original_file_name="private.txt",
        max_payload={"url": "https://127.0.0.1/private.txt"},
    )

    http_calls = []
    monkeypatch.setattr("support.views_api.httpx.get", lambda *args, **kwargs: http_calls.append(args))
    client.force_login(staff_user)

    response = client.get(attachment_to_dict(attachment)["download_url"])

    assert response.status_code == 404
    assert http_calls == []
