from __future__ import annotations

import csv

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from unfold.admin import ModelAdmin

from .models import (
    Conversation,
    DeliveryAttempt,
    ManagerActionLog,
    MaxContact,
    Message,
    MessageAttachment,
    RawUpdate,
)


@admin.action(description="Export selected MAX users to CSV")
def export_max_contacts_csv(
    modeladmin: ModelAdmin,
    request: HttpRequest,
    queryset,
) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="max-users.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "max_user_id",
            "username",
            "first_name",
            "last_name",
            "is_bot",
            "last_activity_time",
            "first_seen_at",
            "last_seen_at",
        ]
    )
    for contact in queryset.order_by("max_user_id"):
        writer.writerow(
            [
                contact.max_user_id,
                contact.username,
                contact.first_name,
                contact.last_name,
                contact.is_bot,
                contact.last_activity_time,
                contact.first_seen_at,
                contact.last_seen_at,
            ]
        )
    return response


@admin.register(MaxContact)
class MaxContactAdmin(ModelAdmin):
    list_display = ("max_user_id", "username", "first_name", "last_name", "is_bot", "last_seen_at")
    search_fields = ("max_user_id", "username", "first_name", "last_name", "legacy_name")
    list_filter = ("is_bot",)
    readonly_fields = ("raw_user", "first_seen_at", "last_seen_at", "created_at", "updated_at")
    actions = [export_max_contacts_csv]


@admin.register(Conversation)
class ConversationAdmin(ModelAdmin):
    list_display = ("id", "contact", "status", "assigned_to", "last_message_at", "unread_count")
    search_fields = ("contact__max_user_id", "contact__username", "max_chat_id")
    list_filter = ("status", "recipient_type", "assigned_to")
    autocomplete_fields = ("contact", "assigned_to", "last_message")
    readonly_fields = ("created_at", "updated_at")


@admin.register(RawUpdate)
class RawUpdateAdmin(ModelAdmin):
    list_display = ("id", "update_type", "status", "dedupe_key", "received_at", "processed_at")
    search_fields = ("dedupe_key", "update_type", "max_chat_id")
    list_filter = ("status", "update_type")
    readonly_fields = ("payload", "headers", "received_at", "processed_at")


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = ("id", "conversation", "direction", "sender_kind", "manager", "send_status", "created_at")
    search_fields = ("text", "max_message_id", "external_event_key", "contact__max_user_id", "contact__username")
    list_filter = ("direction", "sender_kind", "send_status", "content_type", "text_format")
    autocomplete_fields = ("conversation", "contact", "raw_update", "manager", "reply_to_message")
    readonly_fields = ("raw_message", "created_at", "updated_at", "sent_at")


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(ModelAdmin):
    list_display = ("id", "message", "attachment_type", "upload_status", "original_file_name", "created_at")
    search_fields = ("original_file_name", "sha256", "message__text")
    list_filter = ("attachment_type", "upload_status", "direction")
    autocomplete_fields = ("message", "conversation", "contact", "manager")
    readonly_fields = ("max_payload", "raw_attachment", "created_at", "uploaded_at")


@admin.register(ManagerActionLog)
class ManagerActionLogAdmin(ModelAdmin):
    list_display = ("id", "action", "manager", "conversation", "message", "created_at")
    search_fields = ("action", "manager__username", "conversation__contact__max_user_id")
    list_filter = ("action", "created_at")
    autocomplete_fields = ("manager", "conversation", "message")
    readonly_fields = ("metadata", "created_at")


@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(ModelAdmin):
    list_display = ("id", "message", "attempt_no", "status", "http_status", "created_at")
    search_fields = ("message__text", "error_code", "error_text")
    list_filter = ("status", "http_status", "created_at")
    autocomplete_fields = ("message",)
    readonly_fields = ("request_payload", "response_payload", "created_at")
