from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path
from django.views.generic import RedirectView

from max_support_desk.demo_views import demo_admin_route_disabled
from support.admin_views import chats_admin_view, export_max_users_csv_view
from support import views_api
from support.views_webhook import max_webhook


urlpatterns = [
    path(
        "favicon.ico",
        RedirectView.as_view(url=f"{settings.STATIC_URL}favicon.ico", permanent=True),
        name="favicon",
    ),
    path("support/", lambda request: redirect("admin_support_chats"), name="support_home"),
    path("webhooks/max/", max_webhook, name="max_webhook"),
    path("api/conversations/", views_api.conversations_api, name="api_conversations"),
    path("api/external/openapi.json", views_api.external_api_openapi, name="external_api_openapi"),
    path("api/external/conversations/", views_api.external_conversations_api, name="external_api_conversations"),
    path(
        "api/external/conversations/<int:conversation_id>/messages/",
        views_api.external_conversation_messages_api,
        name="external_api_conversation_messages",
    ),
    path(
        "api/conversations/<int:conversation_id>/messages/",
        views_api.conversation_messages_api,
        name="api_conversation_messages",
    ),
    path(
        "api/conversations/<int:conversation_id>/assign/",
        views_api.conversation_assign_api,
        name="api_conversation_assign",
    ),
    path(
        "api/conversations/<int:conversation_id>/close/",
        views_api.conversation_close_api,
        name="api_conversation_close",
    ),
    path("api/messages/<int:message_id>/retry/", views_api.message_retry_api, name="api_message_retry"),
    path(
        "api/attachments/<int:attachment_id>/download/",
        views_api.attachment_download_api,
        name="api_attachment_download",
    ),
    path(
        "admin/support/chats/",
        admin.site.admin_view(chats_admin_view),
        name="admin_support_chats",
    ),
    path(
        "admin/export/max-users.csv",
        admin.site.admin_view(export_max_users_csv_view),
        name="admin_export_max_users_csv",
    ),
    *(
        [
            path("admin/password_change/", demo_admin_route_disabled, name="demo_password_change_disabled"),
            path("admin/password_change/done/", demo_admin_route_disabled, name="demo_password_change_done_disabled"),
            path("admin/auth/", demo_admin_route_disabled, name="demo_auth_disabled"),
            path("admin/auth/<path:subpath>", demo_admin_route_disabled, name="demo_auth_subpath_disabled"),
        ]
        if settings.DEMO_LOGIN_HINTS
        else []
    ),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
