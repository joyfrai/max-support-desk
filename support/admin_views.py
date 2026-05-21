from __future__ import annotations

import csv

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.db.models import Count, Max

from support.models import MaxContact
from support.services.audit import log_manager_action


def chats_admin_view(request: HttpRequest) -> HttpResponse:
    context = {
        **admin.site.each_context(request),
        "title": "Chats",
    }
    return TemplateResponse(request, "admin/support/chats.html", context)


def export_max_users_csv_view(request: HttpRequest) -> HttpResponse:
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
            "conversation_count",
            "message_count",
            "last_message_at",
            "active_conversation_status",
            "assigned_to",
        ]
    )
    contacts = MaxContact.objects.annotate(
        conversation_count=Count("conversations", distinct=True),
        message_count=Count("messages", distinct=True),
        last_message_at_value=Max("messages__created_at"),
    ).order_by("max_user_id")
    for contact in contacts:
        active_conversation = contact.conversations.exclude(status="closed").order_by("-updated_at").first()
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
                contact.conversation_count,
                contact.message_count,
                contact.last_message_at_value,
                active_conversation.status if active_conversation else "",
                active_conversation.assigned_to.username
                if active_conversation and active_conversation.assigned_to
                else "",
            ]
        )
    log_manager_action(manager=request.user, action="max_users.export_csv")
    return response
