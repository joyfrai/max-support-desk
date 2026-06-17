from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import mimetypes
import secrets
import socket
from email.message import Message as EmailMessage
from functools import wraps
from pathlib import PurePath
from urllib.parse import urlparse

import httpx
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
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


def external_api_bearer_required(view_func):
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        configured_token = settings.SUPPORT_EXTERNAL_API_TOKEN
        if not configured_token:
            logger.warning("external_api_disabled path=%s", request.path)
            return JsonResponse({"ok": False, "error": "external_api_disabled"}, status=503)

        provided_token = _extract_bearer_token(request.headers.get("Authorization", ""))
        if not provided_token or not secrets.compare_digest(provided_token, configured_token):
            logger.warning(
                "external_api_permission_denied path=%s remote_addr=%s",
                request.path,
                request.META.get("REMOTE_ADDR", ""),
            )
            response = JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
            response["WWW-Authenticate"] = 'Bearer realm="max-support-desk-external-api"'
            return response
        return view_func(request, *args, **kwargs)

    return wrapper


@require_GET
@staff_required_json
def conversations_api(request: HttpRequest) -> JsonResponse:
    limit = _positive_int(request.GET.get("limit"), default=100, maximum=100)
    offset = _positive_int(request.GET.get("offset"), default=0, maximum=100_000)
    search = (request.GET.get("search") or "").strip()
    return JsonResponse(_conversations_payload(limit=limit, offset=offset, search=search))


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
        return JsonResponse(
            _conversation_messages_payload(
                conversation=conversation,
                limit=limit,
                offset_value=offset_value,
                after_id=after_id,
            )
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


@require_GET
@external_api_bearer_required
def external_conversations_api(request: HttpRequest) -> JsonResponse:
    limit = _positive_int(request.GET.get("limit"), default=100, maximum=100)
    from_value = _pagination_from(request, default=0, maximum=100_000)
    search = (request.GET.get("search") or "").strip()
    sort = _parse_sort(request.GET.get("sort"), default="desc")
    return JsonResponse(
        _conversations_payload(
            limit=limit,
            offset=from_value,
            search=search,
            sort=sort,
            include_from_alias=True,
        )
    )


@require_GET
@external_api_bearer_required
def external_conversation_messages_api(request: HttpRequest, conversation_id: int) -> JsonResponse:
    conversation = get_object_or_404(
        Conversation.objects.select_related("contact", "assigned_to"),
        pk=conversation_id,
    )
    after_id = request.GET.get("after_id")
    limit = _positive_int(request.GET.get("limit"), default=100, maximum=500)
    from_value = _pagination_from(request, default=0, maximum=1_000_000)
    sort = _parse_sort(request.GET.get("sort"), default="desc")
    return JsonResponse(
        _conversation_messages_payload(
            conversation=conversation,
            limit=limit,
            offset_value=str(from_value),
            after_id=after_id,
            sort=sort,
            default_latest_window=False,
            include_from_alias=True,
        )
    )


@require_GET
def external_api_openapi(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        _external_openapi_schema(request),
        json_dumps_params={"ensure_ascii": False},
        content_type="application/vnd.oai.openapi+json",
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
        _store_remote_attachment_file(attachment)
        attachment.refresh_from_db()
    if not attachment.stored_file:
        raise Http404("Attachment file is not stored")
    _ensure_attachment_download_filename(attachment)
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


def _extract_bearer_token(header_value: str) -> str:
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def _parse_sort(value: str | None, *, default: str) -> str:
    if value and value.lower() in {"asc", "desc"}:
        return value.lower()
    return default


def _pagination_from(request: HttpRequest, *, default: int, maximum: int) -> int:
    raw_value = request.GET.get("from")
    if raw_value is None:
        raw_value = request.GET.get("offset")
    return _positive_int(raw_value, default=default, maximum=maximum)


def _conversations_payload(
    *,
    limit: int,
    offset: int,
    search: str,
    sort: str = "desc",
    include_from_alias: bool = False,
) -> dict:
    ordering = ["-last_message_at", "-updated_at", "id"]
    if sort == "asc":
        ordering = ["last_message_at", "updated_at", "id"]
    conversations = (
        Conversation.objects.select_related("contact", "assigned_to", "last_message")
        .all()
        .order_by(*ordering)
    )
    if search:
        conversations = _filter_conversations(conversations, search)

    page = list(conversations[offset : offset + limit + 1])
    items = page[:limit]
    has_more = len(page) > limit
    payload = {
        "conversations": [conversation_to_dict(item) for item in items],
        "offset": offset,
        "limit": limit,
        "next_offset": offset + len(items),
        "has_more": has_more,
    }
    if include_from_alias:
        payload["from"] = offset
        payload["next_from"] = offset + len(items)
    return payload


def _conversation_messages_payload(
    *,
    conversation: Conversation,
    limit: int,
    offset_value: str | None,
    after_id: str | None,
    sort: str = "asc",
    default_latest_window: bool = True,
    include_from_alias: bool = False,
) -> dict:
    messages = (
        Message.objects.select_related("contact", "manager")
        .prefetch_related("attachments")
        .filter(conversation=conversation)
    )
    if after_id and after_id.isdigit():
        messages = messages.filter(id__gt=int(after_id))
    messages = messages.for_display(descending=sort == "desc")
    total = messages.count()
    if offset_value is None and not after_id:
        if default_latest_window and sort == "asc":
            offset = max(total - limit, 0)
        else:
            offset = 0
    else:
        offset = _positive_int(offset_value, default=0, maximum=1_000_000)
    page = list(messages[offset : offset + limit])
    payload = {
        "conversation": conversation_to_dict(conversation),
        "messages": [message_to_dict(item) for item in page],
        "offset": offset,
        "limit": limit,
        "sort": sort,
        "next_offset": offset + len(page),
        "total": total,
        "has_more_before": offset > 0,
        "has_more_after": offset + len(page) < total,
    }
    if include_from_alias:
        payload["from"] = offset
        payload["next_from"] = offset + len(page)
    return payload


def _external_openapi_schema(request: HttpRequest) -> dict:
    server_url = (settings.SUPPORT_DESK_PUBLIC_URL or request.build_absolute_uri("/")).rstrip("/")
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "MAX Support Desk External API",
            "version": "1.0.0",
            "description": "Read-only API for exporting conversations and messages from MAX Support Desk.",
        },
        "servers": [{"url": server_url}],
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "API token",
                    "description": "Use Authorization: Bearer <SUPPORT_EXTERNAL_API_TOKEN>.",
                }
            },
            "schemas": {
                "ApiError": {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "error": {"type": "string"},
                    },
                    "required": ["ok", "error"],
                },
                "Contact": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "max_user_id": {"type": "string"},
                        "username": {"type": "string"},
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "is_bot": {"type": "boolean"},
                        "last_seen_at": {"type": "string", "format": "date-time", "nullable": True},
                    },
                    "required": ["id", "max_user_id", "username", "first_name", "last_name", "is_bot", "last_seen_at"],
                },
                "Conversation": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "max_chat_id": {"type": "string"},
                        "recipient_type": {"type": "string"},
                        "contact": {"$ref": "#/components/schemas/Contact"},
                        "status": {"type": "string"},
                        "assigned_to_id": {"type": "integer", "nullable": True},
                        "last_message_id": {"type": "integer", "nullable": True},
                        "last_message_at": {"type": "string", "format": "date-time", "nullable": True},
                        "unread_count": {"type": "integer"},
                        "closed_at": {"type": "string", "format": "date-time", "nullable": True},
                        "created_at": {"type": "string", "format": "date-time", "nullable": True},
                        "updated_at": {"type": "string", "format": "date-time", "nullable": True},
                    },
                    "required": [
                        "id",
                        "max_chat_id",
                        "recipient_type",
                        "contact",
                        "status",
                        "assigned_to_id",
                        "last_message_id",
                        "last_message_at",
                        "unread_count",
                        "closed_at",
                        "created_at",
                        "updated_at",
                    ],
                },
                "Attachment": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "file_name": {"type": "string"},
                        "mime_type": {"type": "string"},
                        "size_bytes": {"type": "integer", "nullable": True},
                        "download_url": {"type": "string"},
                    },
                    "required": ["id", "file_name", "mime_type", "size_bytes", "download_url"],
                },
                "Message": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "conversation_id": {"type": "integer"},
                        "contact_id": {"type": "integer"},
                        "direction": {"type": "string"},
                        "sender_kind": {"type": "string"},
                        "author_kind": {"type": "string"},
                        "author_display": {"type": "string"},
                        "manager_id": {"type": "integer", "nullable": True},
                        "max_message_id": {"type": "string"},
                        "max_sender_user_id": {"type": "string"},
                        "external_event_key": {"type": "string"},
                        "reply_to_message_id": {"type": "integer", "nullable": True},
                        "text": {"type": "string"},
                        "text_format": {"type": "string"},
                        "content_type": {"type": "string"},
                        "send_status": {"type": "string"},
                        "provider_created_at": {"type": "string", "format": "date-time", "nullable": True},
                        "created_at": {"type": "string", "format": "date-time", "nullable": True},
                        "received_at": {"type": "string", "format": "date-time", "nullable": True},
                        "sent_at": {"type": "string", "format": "date-time", "nullable": True},
                        "sort_key": {"type": "string", "format": "date-time", "nullable": True},
                        "attachments": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Attachment"},
                        },
                    },
                    "required": [
                        "id",
                        "conversation_id",
                        "contact_id",
                        "direction",
                        "sender_kind",
                        "author_kind",
                        "author_display",
                        "manager_id",
                        "max_message_id",
                        "max_sender_user_id",
                        "external_event_key",
                        "reply_to_message_id",
                        "text",
                        "text_format",
                        "content_type",
                        "send_status",
                        "provider_created_at",
                        "created_at",
                        "received_at",
                        "sent_at",
                        "sort_key",
                        "attachments",
                    ],
                },
            },
        },
        "paths": {
            reverse("external_api_conversations"): {
                "get": {
                    "operationId": "listConversations",
                    "summary": "Get all conversations",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 100, "minimum": 0, "maximum": 100},
                        },
                        {
                            "name": "from",
                            "in": "query",
                            "schema": {"type": "integer", "default": 0, "minimum": 0, "maximum": 100000},
                            "description": "Pagination start offset. `offset` is still accepted as a backward-compatible alias.",
                        },
                        {
                            "name": "search",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": "Search by MAX user id, username, name, legacy name, or max_chat_id.",
                        },
                        {
                            "name": "sort",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["desc", "asc"], "default": "desc"},
                            "description": "Sort by last activity time. Default is newest conversations first.",
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Conversation list",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "conversations": {
                                                "type": "array",
                                                "items": {"$ref": "#/components/schemas/Conversation"},
                                            },
                                            "from": {"type": "integer"},
                                            "offset": {"type": "integer"},
                                            "limit": {"type": "integer"},
                                            "next_from": {"type": "integer"},
                                            "next_offset": {"type": "integer"},
                                            "has_more": {"type": "boolean"},
                                        },
                                        "required": [
                                            "conversations",
                                            "from",
                                            "offset",
                                            "limit",
                                            "next_from",
                                            "next_offset",
                                            "has_more",
                                        ],
                                    }
                                }
                            },
                        },
                        "401": {
                            "description": "Missing or invalid bearer token",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}},
                        },
                        "503": {
                            "description": "External API token is not configured",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}},
                        },
                    },
                }
            },
            reverse("external_api_conversation_messages", args=[0]).replace("/0/", "/{conversation_id}/"): {
                "get": {
                    "operationId": "listConversationMessages",
                    "summary": "Get messages for a conversation",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "conversation_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 100, "minimum": 0, "maximum": 500},
                        },
                        {
                            "name": "from",
                            "in": "query",
                            "schema": {"type": "integer", "default": 0, "minimum": 0, "maximum": 1000000},
                            "description": "Pagination start offset. `offset` is still accepted as a backward-compatible alias.",
                        },
                        {
                            "name": "after_id",
                            "in": "query",
                            "schema": {"type": "integer"},
                            "description": "Return only messages with id greater than this value.",
                        },
                        {
                            "name": "sort",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["desc", "asc"], "default": "desc"},
                            "description": "Sort by display timestamp. Default is newest messages first.",
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Conversation messages",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "conversation": {"$ref": "#/components/schemas/Conversation"},
                                            "messages": {
                                                "type": "array",
                                                "items": {"$ref": "#/components/schemas/Message"},
                                            },
                                            "from": {"type": "integer"},
                                            "offset": {"type": "integer"},
                                            "limit": {"type": "integer"},
                                            "sort": {"type": "string"},
                                            "next_from": {"type": "integer"},
                                            "next_offset": {"type": "integer"},
                                            "total": {"type": "integer"},
                                            "has_more_before": {"type": "boolean"},
                                            "has_more_after": {"type": "boolean"},
                                        },
                                        "required": [
                                            "conversation",
                                            "messages",
                                            "from",
                                            "offset",
                                            "limit",
                                            "sort",
                                            "next_from",
                                            "next_offset",
                                            "total",
                                            "has_more_before",
                                            "has_more_after",
                                        ],
                                    }
                                }
                            },
                        },
                        "401": {
                            "description": "Missing or invalid bearer token",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}},
                        },
                        "404": {"description": "Conversation not found"},
                        "503": {
                            "description": "External API token is not configured",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}},
                        },
                    },
                }
            },
        },
    }


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


def _store_remote_attachment_file(attachment: MessageAttachment) -> None:
    remote_url = _remote_attachment_url(attachment)
    if not remote_url:
        return

    response = _get_safe_remote_attachment(remote_url=remote_url, attachment_id=attachment.id)
    if response is None:
        return
    if response.status_code >= 400:
        logger.warning(
            "attachment_download_failed attachment_id=%s status_code=%s",
            attachment.id,
            response.status_code,
        )
        return

    data = response.content
    if not data:
        logger.warning("attachment_download_empty attachment_id=%s", attachment.id)
        return

    content_type = response.headers.get("content-type", "").split(";", 1)[0] or "application/octet-stream"
    file_name = _download_file_name(
        attachment=attachment,
        remote_url=remote_url,
        content_type=content_type,
        content_disposition=response.headers.get("content-disposition", ""),
    )

    attachment.stored_file.save(file_name, ContentFile(data), save=False)
    attachment.original_file_name = file_name
    attachment.mime_type = attachment.mime_type or content_type
    attachment.size_bytes = len(data)
    attachment.sha256 = hashlib.sha256(data).hexdigest()
    attachment.uploaded_at = timezone.now()
    attachment.save(
        update_fields=[
            "stored_file",
            "original_file_name",
            "mime_type",
            "size_bytes",
            "sha256",
            "uploaded_at",
        ]
    )


def _remote_attachment_url(attachment: MessageAttachment) -> str:
    for payload in (attachment.max_payload, attachment.raw_attachment):
        found = _find_url_in_payload(payload)
        if found:
            return found
    return ""


def _find_url_in_payload(payload) -> str:
    if isinstance(payload, dict):
        for key in ("download_url", "file_url", "media_url", "url", "link"):
            value = payload.get(key)
            if isinstance(value, str) and value.startswith("https://"):
                return value
        for value in payload.values():
            found = _find_url_in_payload(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _find_url_in_payload(value)
            if found:
                return found
    return ""


def _get_safe_remote_attachment(*, remote_url: str, attachment_id: int) -> httpx.Response | None:
    current_url = remote_url
    for _ in range(4):
        parsed = urlparse(current_url)
        if not _is_safe_remote_download_url(current_url):
            logger.warning("attachment_download_blocked attachment_id=%s host=%s", attachment_id, parsed.hostname)
            return None

        headers = {}
        if parsed.hostname == "platform-api.max.ru" and settings.MAX_BOT_TOKEN:
            headers["Authorization"] = settings.MAX_BOT_TOKEN

        response = httpx.get(current_url, headers=headers, follow_redirects=False, timeout=120.0)
        if response.is_redirect:
            redirect_url = response.headers.get("location", "")
            if not redirect_url:
                return response
            current_url = str(httpx.URL(current_url).join(redirect_url))
            continue
        return response
    logger.warning("attachment_download_too_many_redirects attachment_id=%s", attachment_id)
    return None


def _is_safe_remote_download_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    return _host_resolves_to_public_ips(parsed.hostname)


def _host_resolves_to_public_ips(hostname: str) -> bool:
    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    if not addresses:
        return False
    for address in addresses:
        ip_value = address[4][0]
        try:
            ip_address = ipaddress.ip_address(ip_value)
        except ValueError:
            return False
        if not ip_address.is_global:
            return False
    return True


def _filename_from_url(url: str) -> str:
    name = PurePath(urlparse(url).path).name
    return name if name and "." in name else ""


def _ensure_attachment_download_filename(attachment: MessageAttachment) -> None:
    if "." in PurePath(attachment.original_file_name).name:
        return
    extension = _extension_for_content_type(attachment.mime_type)
    if not extension:
        return
    attachment.original_file_name = f"{attachment.original_file_name or 'Вложение MAX'}{extension}"
    attachment.save(update_fields=["original_file_name"])


def _download_file_name(
    *,
    attachment: MessageAttachment,
    remote_url: str,
    content_type: str,
    content_disposition: str,
) -> str:
    content_disposition_name = _filename_from_content_disposition(content_disposition)
    url_name = _filename_from_url(remote_url)
    base_name = content_disposition_name or attachment.original_file_name or url_name or f"max-attachment-{attachment.id}"
    if "." in PurePath(base_name).name:
        return base_name
    extension = _extension_for_content_type(content_type)
    return f"{base_name}{extension}" if extension else base_name


def _filename_from_content_disposition(value: str) -> str:
    if not value:
        return ""
    message = EmailMessage()
    message["content-disposition"] = value
    filename = message.get_filename()
    return filename or ""


def _extension_for_content_type(content_type: str) -> str:
    if not content_type or content_type == "application/octet-stream":
        return ""
    return mimetypes.guess_extension(content_type) or ""
