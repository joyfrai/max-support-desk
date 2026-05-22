from __future__ import annotations

import json
import logging
import hashlib
from functools import wraps

from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from support.models import Conversation, Message, MessageAttachment
from support.realtime import message_created_payload, message_status_payload, publish_event
from support.serializers import conversation_to_dict, message_to_dict
from support.services.audit import log_manager_action

logger = logging.getLogger("support.api")


def staff_required_json(view_func):
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            logger.warning(
                "api_permission_denied path=%s user_id=%s",
                request.path,
                request.user.id if request.user.is_authenticated else "",
            )
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        return view_func(request, *args, **kwargs)

    return wrapper


def parse_json_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


@require_GET
@staff_required_json
def conversations_api(request: HttpRequest) -> JsonResponse:
    limit = _positive_int(request.GET.get("limit"), default=100, maximum=100)
    offset = _positive_int(request.GET.get("offset"), default=0, maximum=100_000)
    search = (request.GET.get("search") or "").strip()

    conversations = (
        Conversation.objects.select_related("contact", "assigned_to", "last_message")
        .all()
        .order_by("-last_message_at", "-updated_at", "id")
    )
    if search:
        conversations = _filter_conversations(conversations, search)

    page = list(conversations[offset : offset + limit + 1])
    items = page[:limit]
    has_more = len(page) > limit
    return JsonResponse(
        {
            "conversations": [conversation_to_dict(item) for item in items],
            "offset": offset,
            "limit": limit,
            "next_offset": offset + len(items),
            "has_more": has_more,
        }
    )


@require_http_methods(["GET", "POST"])
@staff_required_json
def conversation_messages_api(request: HttpRequest, conversation_id: int) -> JsonResponse:
    conversation = get_object_or_404(
        Conversation.objects.select_related("contact", "assigned_to"),
        pk=conversation_id,
    )

    if request.method == "GET":
        after_id = request.GET.get("after_id")
        limit = _positive_int(request.GET.get("limit"), default=200, maximum=500)
        offset_value = request.GET.get("offset")
        messages = (
            Message.objects.select_related("contact", "manager")
            .prefetch_related("attachments")
            .filter(conversation=conversation)
        )
        if after_id and after_id.isdigit():
            messages = messages.filter(id__gt=int(after_id))
        messages = messages.for_display()
        total = messages.count()
        if offset_value is None and not after_id:
            offset = max(total - limit, 0)
        else:
            offset = _positive_int(offset_value, default=0, maximum=1_000_000)
        page = list(messages[offset : offset + limit])
        return JsonResponse(
            {
                "messages": [message_to_dict(item) for item in page],
                "offset": offset,
                "limit": limit,
                "total": total,
                "has_more_before": offset > 0,
                "has_more_after": offset + len(page) < total,
            }
        )

    payload = parse_json_body(request) if request.content_type == "application/json" else request.POST
    text = str(payload.get("text") or "").strip()
    uploaded_files = list(request.FILES.values())
    if not text and not uploaded_files:
        return JsonResponse({"ok": False, "error": "text_required"}, status=400)

    with transaction.atomic():
        message = Message.objects.create(
            conversation=conversation,
            contact=conversation.contact,
            direction=Message.Direction.OUTGOING,
            sender_kind=Message.SenderKind.MANAGER,
            manager=request.user,
            text=text,
            content_type=_message_content_type(text=text, has_files=bool(uploaded_files)),
            send_status=Message.SendStatus.QUEUED,
        )
        for uploaded_file in uploaded_files:
            attachment = _create_outgoing_attachment(
                message=message,
                uploaded_file=uploaded_file,
                manager=request.user,
            )
            log_manager_action(
                manager=request.user,
                action="attachment.upload",
                conversation=conversation,
                message=message,
                metadata={"attachment_id": attachment.id, "file_name": attachment.original_file_name},
            )
        conversation.last_message = message
        conversation.last_message_at = message.created_at
        conversation.unread_count = 0
        if conversation.status == Conversation.Status.NEW:
            conversation.status = Conversation.Status.OPEN
        conversation.save(update_fields=["last_message", "last_message_at", "unread_count", "status", "updated_at"])
        log_manager_action(
            manager=request.user,
            action="message.send",
            conversation=conversation,
            message=message,
        )
        transaction.on_commit(
            lambda: publish_event("message.created", message_created_payload(message))
        )
        logger.info(
            "message_queued conversation_id=%s message_id=%s manager_id=%s",
            conversation.id,
            message.id,
            request.user.id,
        )

    return JsonResponse(
        {"message": message_to_dict(message), "conversation": conversation_to_dict(conversation)},
        status=201,
    )


@require_POST
@staff_required_json
def conversation_assign_api(request: HttpRequest, conversation_id: int) -> JsonResponse:
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    conversation.assigned_to = request.user
    conversation.save(update_fields=["assigned_to", "updated_at"])
    log_manager_action(manager=request.user, action="conversation.assign", conversation=conversation)
    return JsonResponse({"conversation": conversation_to_dict(conversation)})


@require_POST
@staff_required_json
def conversation_close_api(request: HttpRequest, conversation_id: int) -> JsonResponse:
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    conversation.status = Conversation.Status.CLOSED
    conversation.closed_at = timezone.now()
    conversation.save(update_fields=["status", "closed_at", "updated_at"])
    log_manager_action(manager=request.user, action="conversation.close", conversation=conversation)
    return JsonResponse({"conversation": conversation_to_dict(conversation)})


@require_POST
@staff_required_json
def message_retry_api(request: HttpRequest, message_id: int) -> JsonResponse:
    message = get_object_or_404(Message.objects.select_related("conversation", "contact"), pk=message_id)
    message.mark_for_retry()
    log_manager_action(
        manager=request.user,
        action="message.retry",
        conversation=message.conversation,
        message=message,
    )
    transaction.on_commit(
        lambda: publish_event("message.status_changed", message_status_payload(message))
    )
    logger.info("message_retry_queued message_id=%s manager_id=%s", message.id, request.user.id)
    return JsonResponse({"message": message_to_dict(message)})


@require_GET
@staff_required_json
def attachment_download_api(request: HttpRequest, attachment_id: int) -> HttpResponse:
    attachment = get_object_or_404(MessageAttachment.objects.select_related("conversation", "message"), pk=attachment_id)
    if not attachment.stored_file:
        raise Http404("Attachment file is not stored")
    log_manager_action(
        manager=request.user,
        action="attachment.download",
        conversation=attachment.conversation,
        message=attachment.message,
        metadata={"attachment_id": attachment.id},
    )
    return FileResponse(
        attachment.stored_file.open("rb"),
        as_attachment=True,
        filename=attachment.original_file_name or attachment.stored_file.name,
        content_type=attachment.mime_type or "application/octet-stream",
    )


def _message_content_type(*, text: str, has_files: bool) -> str:
    if text and has_files:
        return Message.ContentType.MIXED
    if has_files:
        return Message.ContentType.FILE
    return Message.ContentType.TEXT


def _positive_int(value: str | None, *, default: int, maximum: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(parsed, maximum))


def _filter_conversations(queryset, search: str):
    terms = [term for term in search.split() if term]
    for term in terms:
        queryset = queryset.filter(
            Q(contact__max_user_id__icontains=term)
            | Q(contact__username__icontains=term)
            | Q(contact__first_name__icontains=term)
            | Q(contact__last_name__icontains=term)
            | Q(contact__legacy_name__icontains=term)
            | Q(max_chat_id__icontains=term)
        )
    return queryset


def _create_outgoing_attachment(*, message: Message, uploaded_file, manager) -> MessageAttachment:
    digest = hashlib.sha256()
    size = 0
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
        size += len(chunk)
    uploaded_file.seek(0)

    attachment = MessageAttachment(
        message=message,
        conversation=message.conversation,
        contact=message.contact,
        direction=Message.Direction.OUTGOING,
        sender_kind=Message.SenderKind.MANAGER,
        manager=manager,
        attachment_type=_attachment_type_for_mime(getattr(uploaded_file, "content_type", "")),
        original_file_name=uploaded_file.name,
        mime_type=getattr(uploaded_file, "content_type", "") or "application/octet-stream",
        size_bytes=size,
        sha256=digest.hexdigest(),
        upload_status=MessageAttachment.UploadStatus.PENDING,
    )
    attachment.stored_file.save(uploaded_file.name, uploaded_file, save=False)
    attachment.save()
    return attachment


def _attachment_type_for_mime(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return MessageAttachment.AttachmentType.IMAGE
    if mime_type.startswith("video/"):
        return MessageAttachment.AttachmentType.VIDEO
    if mime_type.startswith("audio/"):
        return MessageAttachment.AttachmentType.AUDIO
    return MessageAttachment.AttachmentType.FILE
