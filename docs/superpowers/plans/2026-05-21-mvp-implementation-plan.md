# MAX Support Desk MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a DB-first self-hosted MAX support desk on Django/Admin/Unfold with Chatscope chat UI, MAX webhook ingest, queued outbound delivery, retries, files, CSV export, Docker, and tests.

**Architecture:** Django owns auth, admin, data model, APIs, webhook, and worker command. MySQL is the production database; SQLite is used for automated tests. React/Chatscope is built by Vite and mounted inside an Unfold custom admin page so managers stay inside the Django admin shell.

**Tech Stack:** Python, Django, Django ORM/Admin/session auth, django-unfold, mysqlclient, Django Channels, `channels_redis`, React, Vite, `@chatscope/chat-ui-kit-react`, Docker, external MySQL.

---

## Execution Rules

- Work on `main` as explicitly approved by the user.
- Do not push unless the user explicitly asks in this chat.
- Implement natively by documentation. Before using a framework/library feature, check official docs or Context7.
- Use Context7 anchors:
  - Django: `/websites/djangoproject_en_5_2`
  - Django package/source docs: `/django/django`
  - Django Unfold: `/unfoldadmin/django-unfold`
  - Django Channels: `/django/channels`
  - Vite: `/vitejs/vite`
  - Chatscope React UI Kit: `/chatscope/chat-ui-kit-react`
- Use local references:
  - MAX: `/root/projects/repost_bot-main/max_bot/main.py`, `services/max_client.py`, `worker/repost_worker.py`, `poster/`, `cabinet/`
  - Chatscope: `/root/projects/telegram-mtproto-web-gateway/frontend/src/components/ChatShell.tsx`, `frontend/src/chat/`, `frontend/src/chatscope-native-theme.scss`, `docs/CHATSCOPE_UI_CONTRACT_RU.md`
- Use TDD for behavior code: write a failing test, verify it fails, implement, verify it passes.
- Keep implementation 80/20: no omnichannel, no SLA, no departments, no AI, no CRM.
- Log important manager actions to `ManagerActionLog` and important service events through sanitized structured application logs.
- Retain audit/service logs for 7 days by default; cleanup automation can be a management command.

## Phase 0: Project Scaffold And Tooling

**Outcome:** The repo has a runnable Django project, dependency files, Docker config, env config, and test command.

**Files:**
- Create: `pyproject.toml`
- Create: `manage.py`
- Create: `max_support_desk/__init__.py`
- Create: `max_support_desk/settings.py`
- Create: `max_support_desk/urls.py`
- Create: `max_support_desk/asgi.py`
- Create: `max_support_desk/wsgi.py`
- Create: `support/__init__.py`
- Create: `support/apps.py`
- Create: `.env.example`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Create: `.gitignore`

Steps:

- [ ] Add Python dependencies: `Django`, `django-unfold`, `mysqlclient`, `httpx`, `channels`, `daphne`, `python-dotenv` or equivalent env loader, `pytest`, `pytest-django`.
- [ ] Configure Django settings from env: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL` or `MYSQL_*`, `MAX_BOT_TOKEN`, `MAX_WEBHOOK_SECRET`, `MEDIA_ROOT`, `MEDIA_URL`.
- [ ] Configure SQLite when `DATABASE_URL`/`MYSQL_*` is absent or when tests run.
- [ ] Configure production MySQL via `ENGINE = "django.db.backends.mysql"` and `mysqlclient`.
- [ ] Enable installed apps: Django core apps, `unfold`, `support`, `channels`.
- [ ] Configure static/media paths for Docker and Vite build output.
- [ ] Configure standard Python logging for Docker/systemd stdout with sanitized structured event fields.
- [ ] Add Dockerfile with system packages needed for `mysqlclient`.
- [ ] Add compose app service only; do not require a MySQL service because production DB is external.
- [ ] Verify: `python manage.py check`.

## Phase 1: Domain Models, Migrations, Admin

**Outcome:** DB schema represents the MVP domain and all core tables are visible in Django Admin/Unfold.

**Files:**
- Create: `support/models.py`
- Create: `support/admin.py`
- Create: `support/migrations/0001_initial.py`
- Create: `support/tests/test_models.py`

Models:

- `MaxContact`
- `Conversation`
- `RawUpdate`
- `Message`
- `MessageAttachment`
- `ManagerActionLog`
- `DeliveryAttempt`

Steps:

- [ ] Write model tests for required invariants:
  - outgoing manager message requires `manager_id`;
  - incoming message uses `send_status=not_applicable`;
  - failed retry keeps the same `Message.id`;
  - message ordering uses MAX `provider_created_at` and then `id`;
  - `assigned_to` does not restrict who can create outgoing messages.
- [ ] Run tests and confirm they fail because models/logic do not exist.
- [ ] Implement enums/choices for conversation status, direction, sender kind, content type, send status, attachment type, upload status, raw update status, delivery attempt status.
- [ ] Implement fields and indexes from `docs/technical_spec.md`.
- [ ] Add DB constraints where Django/MySQL can enforce them simply:
  - unique `MaxContact.max_user_id`;
  - unique `RawUpdate.dedupe_key`;
  - conditional validation in `Message.clean()` for outgoing manager messages.
- [ ] Generate migration.
- [ ] Review migration for MySQL safety: no data backfills, no destructive operations, index names acceptable.
- [ ] Register models in Unfold admin using `unfold.admin.ModelAdmin`.
- [ ] Add admin list displays, search fields, filters, readonly raw JSON fields.
- [ ] Add `MaxContact` CSV export using native Django admin action/custom admin URL.
- [ ] Add audit helper for `ManagerActionLog` so manager actions are logged consistently.
- [ ] Add cleanup policy hook/management command placeholder for 7-day retention of audit and delivery diagnostics.
- [ ] Verify: `python manage.py makemigrations --check --dry-run`, `python manage.py migrate`, `pytest`.

## Phase 2: Manager Admin UX With Unfold

**Outcome:** Staff users enter through Django/Admin login, see MAX users, export CSV, and open Chats page from the sidebar.

**Files:**
- Modify: `max_support_desk/settings.py`
- Modify: `max_support_desk/urls.py`
- Modify: `support/admin.py`
- Create: `support/admin_views.py`
- Create: `support/templates/admin/support/chats.html`
- Create: `support/tests/test_admin_views.py`

Steps:

- [ ] Check Unfold docs for sidebar/custom pages before implementation.
- [ ] Configure Unfold theme and sidebar navigation:
  - MAX users;
  - Chats;
  - service/log tables for superuser.
- [ ] Add custom admin view `/admin/support/chats/` protected by `admin_site.admin_view`.
- [ ] Add `/support/` redirect to `/admin/support/chats/`.
- [ ] Ensure staff access works and anonymous users are redirected to login.
- [ ] Ensure non-staff users cannot access admin/chat pages.
- [ ] Log CSV export and security-relevant denied access events without leaking sensitive data.
- [ ] Verify admin pages with Django test client.

## Phase 3: MAX Webhook Ingest

**Outcome:** `POST /webhooks/max/` validates secret, saves raw update, dedupes, creates contact/conversation/message/attachments, and returns fast `200 OK`.

**Files:**
- Create: `support/max_payloads.py`
- Create: `support/services/ingest.py`
- Create: `support/views_webhook.py`
- Modify: `max_support_desk/urls.py`
- Create: `support/tests/test_max_webhook.py`

Steps:

- [ ] Inspect local reference `repost_bot-main` MAX code before implementation.
- [ ] Check official MAX docs for `Update`, `User`, `Message`, webhook secret header, message timestamp, attachments.
- [ ] Write tests:
  - invalid/missing secret returns forbidden;
  - valid `message_created` creates `RawUpdate`, `MaxContact`, `Conversation`, `Message`;
  - duplicate `dedupe_key` does not create a second message;
  - MAX `Message.timestamp` is saved into `provider_created_at`;
  - raw payload and headers are stored without logging full payload.
- [ ] Write tests or assertions that duplicate/failed webhook processing emits sanitized service logs.
- [ ] Run tests and confirm they fail.
- [ ] Implement constant-time `MAX_WEBHOOK_SECRET` comparison.
- [ ] Implement dedupe key generation from stable MAX fields, with raw payload hash fallback.
- [ ] Implement contact upsert using normalized MAX user fields plus `raw_user`.
- [ ] Implement active conversation lookup/create.
- [ ] Implement message and attachment creation inside one DB transaction.
- [ ] Emit sanitized service logs for webhook received/processed/duplicate/failed.
- [ ] Use `transaction.on_commit()` hook placeholder for future socket event.
- [ ] Verify: targeted webhook tests and full test suite.

## Phase 4: Staff JSON API

**Outcome:** Chatscope can load conversations/messages and create queued outgoing messages through session-authenticated JSON endpoints.

**Files:**
- Create: `support/serializers.py`
- Create: `support/views_api.py`
- Modify: `max_support_desk/urls.py`
- Create: `support/tests/test_support_api.py`

Endpoints:

- `GET /api/conversations/`
- `GET /api/conversations/<id>/messages/?after_id=...`
- `POST /api/conversations/<id>/messages/`
- `POST /api/conversations/<id>/assign/`
- `POST /api/conversations/<id>/close/`
- `POST /api/messages/<id>/retry/`
- `GET /api/attachments/<id>/download/`

Steps:

- [ ] Write API tests for staff-only access, conversation list, message ordering, outgoing message creation, `manager_id`, assign/close, retry same ID, protected downloads.
- [ ] Run tests and confirm they fail.
- [ ] Implement serializers with `author_display`, `author_kind`, `sort_key`, `send_status`, `manager_id`, `contact_id`.
- [ ] Implement conversation list visible to all staff managers.
- [ ] Implement message list ordering:
  - incoming: `provider_created_at`, tie-break `id`;
  - outgoing: stable internal order, no retroactive reordering after MAX response.
- [ ] Implement outgoing create as DB-first `Message(direction=outgoing, send_status=queued, manager_id=request.user)`.
- [ ] Implement retry by updating the existing failed message to `queued` without creating a new row.
- [ ] Implement protected attachment download with staff permission.
- [ ] Write `ManagerActionLog` rows for send, assign, close/reopen, retry, attachment download, and CSV export.
- [ ] Emit sanitized permission-denied logs for staff-only/API failures.
- [ ] Verify targeted API tests and full test suite.

## Phase 5: Outbound MAX Client And Worker

**Outcome:** A simple worker sends queued outgoing messages to MAX sequentially per conversation and records `DeliveryAttempt`.

**Files:**
- Create: `support/max_client.py`
- Create: `support/services/outbound.py`
- Create: `support/management/__init__.py`
- Create: `support/management/commands/__init__.py`
- Create: `support/management/commands/send_queued_messages.py`
- Create: `support/tests/test_outbound_worker.py`

Steps:

- [ ] Inspect `/root/projects/repost_bot-main/services/max_client.py` and `worker/repost_worker.py`.
- [ ] Check MAX docs for `POST /messages`, uploads, and rate limit.
- [ ] Write worker tests:
  - sends oldest queued message first;
  - does not send a later queued message in same conversation while earlier one is queued/sending;
  - success sets `sent`, `sent_at`, `max_message_id`;
  - failure sets `failed`, `last_error_*`, increments attempts;
  - every attempt creates `DeliveryAttempt`;
  - worker emits sanitized logs for picked/sent/failed/retried messages;
  - retry sends the same `Message.id`.
- [ ] Run tests and confirm they fail.
- [ ] Implement thin `MaxClient` with `httpx`, token from env, controlled logging, and 30 rps guard.
- [ ] Implement single-process worker loop/management command.
- [ ] Implement status transitions with DB transaction boundaries.
- [ ] Emit service logs for MAX API result metadata without token or full payload dumps.
- [ ] Use `transaction.on_commit()` placeholder for `message.status_changed`.
- [ ] Verify worker tests and full test suite.

## Phase 6: Chatscope Frontend Inside Admin

**Outcome:** Managers can open the Chats admin page, see conversations/messages, send text, see author footer and status, and retry failed messages.

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/SupportDeskApp.tsx`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/styles.scss`
- Modify: `support/templates/admin/support/chats.html`
- Create: `support/tests/test_chats_admin_page.py`

Steps:

- [ ] Inspect local Chatscope reference project files from the TЗ.
- [ ] Check Context7/official docs for Chatscope installation, styles, core components.
- [ ] Install frontend dependencies:
  - React;
  - Vite;
  - `@chatscope/chat-ui-kit-react`;
  - `@chatscope/chat-ui-kit-styles`.
- [ ] Build a minimal Chatscope layout:
  - conversation/sidebar list;
  - message list;
  - message input;
  - footer/status display;
  - retry action on failed outgoing message.
- [ ] Use Django session auth and CSRF token for POST.
- [ ] Use polling fallback first for 80/20 reliability.
- [ ] Keep UI inside Unfold admin content area; do not create a separate visual shell.
- [ ] Verify build output loads in Django template.
- [ ] Run a browser smoke test after implementation.

## Phase 7: Realtime With Channels

**Outcome:** Socket events notify clients after DB commit; polling remains fallback.

**Files:**
- Modify: `max_support_desk/asgi.py`
- Create: `support/routing.py`
- Create: `support/consumers.py`
- Create: `support/realtime.py`
- Modify: `support/services/ingest.py`
- Modify: `support/services/outbound.py`
- Create: `support/tests/test_realtime_events.py`

Steps:

- [ ] Check Channels docs for ASGI routing, session auth, consumers, channel layers.
- [ ] Add minimal WebSocket endpoint for staff users.
- [ ] Publish events only via `transaction.on_commit()`.
- [ ] Keep payloads minimal: IDs plus display fields.
- [ ] Frontend reconnects by resyncing via API.
- [ ] Verify socket tests where practical; keep polling fallback tested even if socket tests are limited.

## Phase 8: Files MVP

**Outcome:** Incoming attachment metadata is stored; manager uploads are stored with `FileField`; protected download works; worker can send files via MAX uploads.

**Files:**
- Modify: `support/models.py`
- Modify: `support/views_api.py`
- Modify: `support/services/ingest.py`
- Modify: `support/services/outbound.py`
- Modify: `support/max_client.py`
- Create: `support/tests/test_files.py`

Steps:

- [ ] Check Django FileField/storage docs and MAX uploads docs.
- [ ] Write tests for incoming attachment metadata, manager upload, protected download, outgoing upload success/failure.
- [ ] Run tests and confirm they fail.
- [ ] Store uploaded files under configured `MEDIA_ROOT`.
- [ ] Calculate `sha256`, `mime_type`, `size_bytes`.
- [ ] Enforce upload size limit at Django layer.
- [ ] Implement MAX upload create + file upload + message send with attachment payload.
- [ ] Implement retry handling for `attachment.not.ready` with status/error fields.
- [ ] Verify file tests and full test suite.

## Phase 9: Security And Threat Model Pass

**Outcome:** MVP security controls are documented and covered by tests where cheap.

**Files:**
- Create: `docs/security_threat_model.md`
- Add/modify tests as needed.

Steps:

- [ ] Threat model assets:
  - MAX bot token;
  - webhook secret;
  - raw payloads;
  - manager sessions;
  - uploaded files;
  - support conversations.
- [ ] Threat model trust boundaries:
  - MAX webhook internet edge;
  - Django admin/session boundary;
  - manager browser;
  - external MySQL;
  - local media storage;
  - MAX API outbound.
- [ ] Verify controls:
  - constant-time webhook secret check;
  - staff-only admin/chat/API;
  - CSRF for POST;
  - protected file downloads;
  - no raw payload stdout logging;
  - important manager actions in `ManagerActionLog`;
  - sanitized service logs for webhook/API/worker/MAX/file events;
  - token only via env.
- [ ] Record residual risks:
  - no advanced malware scan for uploads in MVP;
  - single worker process;
  - polling fallback until socket is hardened.

## Phase 10: Docker, Ops, And Verification

**Outcome:** The app can be built, checked, tested, migrated, and run locally with SQLite tests and MySQL-ready production settings.

**Files:**
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Create: `README.md` or `docs/runbook.md` only if needed for operator commands.

Steps:

- [ ] Verify local test path with SQLite: `pytest`.
- [ ] Verify Django checks: `python manage.py check`.
- [ ] Verify migrations: `python manage.py makemigrations --check --dry-run`.
- [ ] Verify Docker build.
- [ ] Verify Docker Compose maps web to host port `8066` and does not publish Redis `6379`.
- [ ] Verify app starts with env example values.
- [ ] Verify admin login flow manually or with browser smoke test.
- [ ] Verify Chatscope admin page loads and has no console errors.
- [ ] Verify CSV export response headers/content.
- [ ] Verify audit/action logs for manager operations and sanitized service logs for webhook/worker paths.
- [ ] Verify webhook/API/worker tests.
- [ ] Update session note and joy-core dashboard.
- [ ] Do not push unless explicitly requested.

## MVP Acceptance Checklist

- [ ] MAX webhook saves raw update, contact, conversation, message, attachment metadata.
- [ ] Duplicate webhook does not duplicate messages.
- [ ] Incoming MAX messages sort by MAX `Message.timestamp`, tie-break by `Message.id`.
- [ ] Manager login uses Django/Admin session auth.
- [ ] Staff managers see MAX users and can export CSV.
- [ ] Chatscope is inside Django/Unfold admin shell with sidebar visible.
- [ ] All staff managers see all chats.
- [ ] Any staff manager can answer any chat.
- [ ] `assigned_to` is responsible person only, not lock.
- [ ] Every outgoing manager message has `manager_id`.
- [ ] Outgoing message is saved as `queued` before MAX send.
- [ ] Worker sends queued messages sequentially per conversation.
- [ ] Success changes status to `sent`.
- [ ] Failure changes status to `failed`.
- [ ] Retry uses same `Message.id`.
- [ ] `DeliveryAttempt` records outbound attempts.
- [ ] Important manager actions are recorded in `ManagerActionLog`.
- [ ] Important service events are logged without secrets, tokens, cookies, session IDs, full raw payloads, or file contents.
- [ ] Superuser can inspect all main/service tables in Django Admin.
- [ ] Files are protected and not public direct links.
- [ ] Tests and verification evidence are fresh before claiming completion.
