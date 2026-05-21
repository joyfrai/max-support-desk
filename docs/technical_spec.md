# MAX Support Desk: техническое задание

Дата актуализации: 2026-05-21

## 1. Цель проекта

Сделать web-сайт поддержки для пользователей мессенджера MAX.

Основной сценарий:

1. Пользователь пишет в MAX-бота.
2. Backend принимает webhook от MAX.
3. Система сохраняет пользователя, чат, сообщение, файлы и raw payload в БД.
4. Менеджер входит на сайт по логину и паролю.
5. В web-чате менеджер видит всех обратившихся пользователей.
6. Менеджер открывает чат, читает историю и отвечает.
7. Ответ менеджера сохраняется в БД.
8. Worker отправляет ответ пользователю в MAX.

Главный принцип: **сначала пишем в БД, потом показываем через socket или отправляем в MAX**.

БД является единственным источником правды. Socket и MAX API — внешние эффекты после успешной записи.

## 2. Scope MVP

Входит в MVP:

- Django backend.
- Django Admin для моделей, менеджеров и служебных операций.
- Стандартная Django `User` model для менеджеров.
- Web-chat на Chatscope.
- MAX webhook endpoint.
- Сохранение всех доступных данных пользователя MAX.
- Сохранение входящих и исходящих сообщений.
- Сохранение raw webhook/update/message/user payloads.
- Прием и отправка файлов.
- CSV export всех пользователей MAX из web-админки.
- Многопользовательская админка.
- Все менеджеры видят все чаты.
- Любой менеджер может ответить в любой чат.
- Закрепление менеджера за чатом опционально и не блокирует остальных.
- Автор каждого исходящего сообщения сохраняется.
- Footer сообщения в Chatscope показывает автора.
- Логирование всех важных действий и service events.
- Docker deployment.
- External MySQL.

Не входит в первый MVP:

- тяжелая омниканальность;
- Telegram adapter;
- CRM-интеграции;
- AI-автоответы;
- сложные SLA;
- departments/queues;
- публичный API для внешних клиентов.

## 3. Технологический стек

Backend:

- Python.
- Django.
- Django ORM.
- Django Admin.
- Django session auth.
- Django Unfold для современной темы admin/UI shell.

Frontend:

- Chatscope UI.
- Рекомендуемый способ: React + `@chatscope/chat-ui-kit-react`.
- Сборка через Vite.
- Bundle подключается в Django template.

Realtime:

- Предпочтительно Django Channels + WebSocket.
- Production channel layer: Redis через официально поддерживаемый `channels_redis`.
- Redis запускается как внутренний Docker service без published `ports`; Django подключается по `REDIS_URL=redis://redis:6379/0`.
- Если `REDIS_URL` не задан, local/tests используют `InMemoryChannelLayer`.
- Для надежности оставить polling fallback.

Background jobs:

- На MVP можно простой worker process.
- Для production лучше Celery/RQ + Redis.

Database:

- External MySQL.
- Tests run on SQLite.
- Production uses Django MySQL backend `django.db.backends.mysql` with the standard `mysqlclient` Python driver.

Deployment:

- Docker.
- Static files are served from `STATIC_ROOT` by WhiteNoise middleware in the Django/Daphne container.
- Web service publishes host port `8066` to container port `8000`.
- Redis service is internal-only in Docker Compose and must not publish `6379` to host/internet.
- MySQL не поднимаем обязательным сервисом в compose, потому что БД внешняя.

## 3.1. Native-by-docs implementation rule

Важное правило реализации:

- все решения реализуются нативно по официальной документации используемых библиотек;
- перед внедрением framework/library behavior сверяется с документацией, а не придумывается "своя версия";
- если есть стандартный механизм Django/Admin/Unfold/Channels/Chatscope, использовать его;
- кастомный код писать только там, где стандартного механизма нет или он не закрывает конкретное требование;
- решения по MAX payload/API сверять с MAX docs и локальным reference project;
- при сомнении фиксировать ссылку на документацию в комментарии плана/issue, а не угадывать.

Context7 MCP docs anchors для реализации:

- Django: `/websites/djangoproject_en_5_2`
- Django source/package docs: `/django/django`
- Django Unfold: `/unfoldadmin/django-unfold`
- Django Channels: `/django/channels`
- Vite: `/vitejs/vite`
- Chatscope React UI Kit: `/chatscope/chat-ui-kit-react`

Дополнительные official web docs:

- Django docs: https://docs.djangoproject.com/en/5.2/
- Django admin actions: https://docs.djangoproject.com/en/5.2/ref/contrib/admin/actions/
- Django databases: https://docs.djangoproject.com/en/5.2/ref/databases/
- Unfold docs: https://unfoldadmin.com/docs/
- Channels docs: https://channels.readthedocs.io/
- Vite docs: https://vite.dev/
- Chatscope docs: https://chatscope.io/docs/

## 3.2. Локальные референсы реализации

Для работы с MAX использовать как reference project:

- `/root/projects/repost_bot-main`

Что смотреть:

- `requirements.txt` и `pyproject.toml` для зависимости `maxapi`;
- `max_bot/main.py` для примера runtime на `maxapi`;
- `services/max_client.py` для примера thin HTTP client под MAX API;
- `worker/repost_worker.py` для примера фоновой отправки;
- `poster/` и `cabinet/` для Django/Django Admin подходов.

Для работы с Chatscope использовать как reference project:

- `/root/projects/telegram-mtproto-web-gateway`

Что смотреть:

- `frontend/package.json` для зависимостей `@chatscope/chat-ui-kit-react`, `@chatscope/chat-ui-kit-styles`, `@chatscope/use-chat`;
- `frontend/src/components/ChatShell.tsx` для layout на Chatscope;
- `frontend/src/chat/useGatewayChatState.ts` и `GatewayChatProvider.tsx` для chat state binding;
- `frontend/src/chatscope-native-theme.scss` для подключения нативной темы;
- `docs/CHATSCOPE_UI_CONTRACT_RU.md` для UI contract;
- `docs/CHATSCOPE_DEEP_INTEGRATION_PLAN_RU.md` для deeper integration plan.

## 4. Конфигурация через env

В переменных окружения храним:

- данные подключения к БД;
- MAX bot token;
- MAX webhook secret key — произвольная секретная строка для проверки webhook.

Рекомендуемые env vars:

- `DATABASE_URL`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MAX_BOT_TOKEN`
- `MAX_WEBHOOK_SECRET`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_DEBUG`
- `MEDIA_ROOT`
- `MEDIA_URL`

Важно:

- `MAX_BOT_TOKEN` не хранить в коде.
- `MAX_WEBHOOK_SECRET` проверять через constant-time comparison.
- Raw payloads не логировать целиком в stdout.

## 5. MAX integration

Официальная документация:

- MAX API: https://dev.max.ru/docs-api
- User object: https://dev.max.ru/docs-api/objects/User
- Message object: https://dev.max.ru/docs-api/objects/Message
- Update object: https://dev.max.ru/docs-api/objects/Update
- Webhook subscriptions: https://dev.max.ru/docs-api/methods/POST/subscriptions
- Send message: https://dev.max.ru/docs-api/methods/POST/messages
- Uploads: https://dev.max.ru/docs-api/methods/POST/uploads

Библиотека из проекта `repost_bot-main`:

- `maxapi`

Подтверждение:

- `/root/projects/repost_bot-main/requirements.txt`: `maxapi>=0.9`
- `/root/projects/repost_bot-main/pyproject.toml`: `maxapi>=0.9`
- `/root/projects/repost_bot-main/max_bot/main.py`: `from maxapi import Bot, Dispatcher`

Также в `repost_bot-main` есть полезный reference client:

- `/root/projects/repost_bot-main/services/max_client.py`

Он уже реализует:

- `GET /me`
- `GET /chats`
- `POST /messages`
- `POST /uploads`
- upload image/file/video/audio
- rate limit 30 rps

Решение:

- `maxapi` можно использовать для event types, если webhook flow удобный.
- Для отправки сообщений/uploads лучше держать собственный thin client на `httpx`, чтобы контролировать retries, статусы, логирование и rate limit.

## 6. MAX webhook

Endpoint:

- `POST /webhooks/max/`

Требования MAX:

- production лучше через webhook, не polling;
- endpoint должен быть HTTPS;
- endpoint должен быть доступен на 443;
- endpoint должен быстро вернуть `200 OK`;
- если задан secret, MAX передает его в `X-Max-Bot-Api-Secret`;
- webhook payload содержит `Update`.

Алгоритм входящего webhook:

1. Получить `POST /webhooks/max/`.
2. Проверить `X-Max-Bot-Api-Secret` против `MAX_WEBHOOK_SECRET`.
3. Распарсить JSON.
4. Вычислить `dedupe_key`.
5. Создать `RawUpdate`.
6. Если такой `dedupe_key` уже есть, вернуть `200 OK` без дубля.
7. Определить `update_type`.
8. Для `message_created`:
   - извлечь `sender`;
   - upsert-ить `MaxContact`;
   - найти или создать active `Conversation`;
   - создать `Message(direction=incoming)`;
   - создать `MessageAttachment`, если есть вложения;
   - обновить `Conversation.last_message_at`, `last_message_id`, `unread_count`.
9. После commit отправить socket event.
10. Вернуть `200 OK`.

Важно: socket event отправлять только после успешного DB commit.

## 7. Модель данных

### 7.1. Менеджеры

Используем стандартную модель:

- `django.contrib.auth.models.User`

Роли можно сделать через Django groups:

- `support_admin`
- `support_manager`
- `support_readonly`

Для MVP достаточно:

- `is_staff=True`
- permission checks на staff-only views/API.

### 7.2. `MaxContact`

Пользователь MAX, который написал боту.

Поля:

- `id`
- `max_user_id` unique
- `first_name`
- `last_name`
- `username`
- `is_bot`
- `last_activity_time`
- `legacy_name`
- `raw_user` JSON
- `first_seen_at`
- `last_seen_at`
- `created_at`
- `updated_at`

MAX `User` содержит:

- `user_id`
- `first_name`
- `last_name`
- `username`
- `is_bot`
- `last_activity_time`
- `name`, но `name` устаревшее

Решение:

- нормализованные поля храним отдельно;
- весь объект MAX `User` храним в `raw_user`;
- `name` кладем в `legacy_name`, но не строим на нем бизнес-логику.

Индексы:

- unique `max_user_id`
- index `username`
- index `last_seen_at`

### 7.3. `Conversation`

Рабочий чат/обращение в нашей системе.

Поля:

- `id`
- `contact_id` FK -> `MaxContact`
- `max_chat_id` nullable
- `recipient_type`: `user`, `chat`, `channel`, `unknown`
- `status`: `new`, `open`, `pending`, `closed`
- `assigned_to_id` FK -> Django `User`, nullable
- `last_message_id` FK -> `Message`, nullable
- `last_message_at`
- `unread_count`
- `closed_at`
- `created_at`
- `updated_at`

Правила:

- `assigned_to` — ответственный менеджер, не lock.
- Все менеджеры видят все chats.
- Любой менеджер может ответить в любой chat.
- Автор каждого outgoing message сохраняется в `Message.manager_id`.

Индексы:

- `(status, last_message_at)`
- `(assigned_to_id, status, last_message_at)`
- `(contact_id, status)`
- `max_chat_id`

### 7.4. `RawUpdate`

Сырой webhook event от MAX.

Поля:

- `id`
- `update_type`
- `max_timestamp`
- `max_chat_id`
- `dedupe_key` unique
- `payload` JSON
- `headers` JSON
- `received_at`
- `processed_at`
- `status`: `received`, `processed`, `ignored`, `failed`
- `error_text`

Нужен для:

- отладки;
- replay;
- защиты от дублей webhook retry;
- сохранения новых MAX fields без миграции.

### 7.5. `Message`

Единая таблица входящих и исходящих сообщений.

Поля:

- `id`
- `conversation_id` FK
- `contact_id` FK
- `raw_update_id` FK, nullable
- `direction`: `incoming`, `outgoing`
- `sender_kind`: `max_user`, `manager`, `system`
- `max_sender_user_id`, nullable
- `manager_id` FK -> Django `User`, nullable
- `max_message_id`, nullable
- `external_event_key`, nullable
- `reply_to_message_id`, nullable
- `text`
- `text_format`: `plain`, `html`, `markdown`, `unknown`
- `content_type`: `text`, `file`, `mixed`, `service`, `unsupported`
- `raw_message` JSON
- `send_status`: `not_applicable`, `queued`, `sending`, `sent`, `failed`
- `send_attempts`
- `last_error_code`
- `last_error_text`
- `provider_created_at`
- `received_at`
- `sent_at`
- `created_at`
- `updated_at`

Решение по хранению:

- Не делить на `IncomingMessage` и `OutgoingMessage`.
- Хранить одну ленту `Message`.
- Различать направление через `direction`.
- Различать автора через `sender_kind`.
- Для outgoing от менеджера `manager_id` обязателен.
- Для incoming от MAX `send_status=not_applicable`.
- Для outgoing сначала `send_status=queued`.

### 7.6. Порядок сообщений

Для входящих MAX-сообщений главный порядок:

1. `provider_created_at` из `Message.timestamp` объекта MAX.
2. Если timestamp совпал или отсутствует — `Message.id`.

В БД обязательно записывать timestamp из объекта MAX `Message`.

Для исходящих сообщений:

- порядок фиксации у нас — `Message.id`;
- worker отправляет outgoing messages в один `Conversation` последовательно по `Message.id`.

Для отображения общей ленты:

- primary sort: `provider_created_at` для incoming, если есть;
- tie-breaker: `Message.id`;
- для outgoing `provider_created_at` можно ставить равным времени создания/отправки у нас или хранить отдельно `created_at`;
- serializer должен отдавать готовый `sort_key`, чтобы frontend не гадал.

Практически для MVP:

- в API сортировать так, чтобы incoming MAX messages шли по MAX timestamp;
- при одинаковом timestamp сортировать по `id`;
- outgoing messages не переставлять задним числом после ответа MAX.

### 7.7. `MessageAttachment`

Файл или вложение сообщения.

Поля:

- `id`
- `message_id` FK
- `conversation_id` FK
- `contact_id` FK
- `direction`
- `sender_kind`
- `manager_id` FK -> Django `User`, nullable
- `attachment_type`: `image`, `video`, `audio`, `file`, `inline_keyboard`, `unknown`
- `original_file_name`
- `stored_file` FileField, nullable
- `mime_type`
- `size_bytes`
- `sha256`
- `max_payload` JSON
- `raw_attachment` JSON
- `upload_status`: `not_needed`, `pending`, `uploaded`, `ready`, `failed`
- `max_upload_token`
- `max_upload_url`
- `last_error_text`
- `created_at`
- `uploaded_at`

Django `FileField` подходит:

- файл хранится через storage;
- в БД хранится путь;
- можно начать с local volume и позже перейти на S3-compatible storage.

Файлы должны отдаваться через protected endpoint, не напрямую из публичной папки.

### 7.8. `ManagerActionLog`

Audit log для действий менеджеров.

Поля:

- `id`
- `manager_id`
- `conversation_id`
- `message_id`, nullable
- `action`
- `metadata` JSON
- `created_at`

Логировать:

- назначение менеджера;
- снятие назначения;
- закрытие/переоткрытие чата;
- retry failed message;
- удаление/скрытие/служебные операции, если появятся.

### 7.9. `DeliveryAttempt`

Опционально, но желательно для диагностики отправки.

Поля:

- `id`
- `message_id`
- `attempt_no`
- `status`: `started`, `success`, `failed`, `retry_scheduled`
- `request_payload` JSON
- `response_payload` JSON
- `http_status`
- `error_code`
- `error_text`
- `created_at`

В MVP можно хранить только `send_attempts`, `last_error_code`, `last_error_text` на `Message`, но отдельная таблица удобнее для разбора проблем.

## 8. DB-first flow

### 8.1. Incoming MAX -> DB -> socket

1. Пользователь пишет в MAX.
2. MAX присылает webhook.
3. Django сохраняет `RawUpdate`.
4. Django сохраняет/обновляет `MaxContact`.
5. Django создает/находит `Conversation`.
6. Django сохраняет `Message`.
7. Django сохраняет `MessageAttachment`.
8. Transaction commit.
9. После commit socket event `message.created`.
10. Chatscope получает событие и показывает сообщение.

### 8.2. Chatscope -> DB -> MAX

1. Менеджер пишет в Chatscope.
2. Frontend отправляет `POST /api/conversations/{id}/messages/`.
3. Django создает `Message(direction=outgoing, send_status=queued, manager_id=<user>)`.
4. Django сохраняет attachments.
5. Transaction commit.
6. После commit socket event `message.created`.
7. Менеджеры видят сообщение как `queued/sending`.
8. Worker берет queued message.
9. Worker отправляет сообщение/файлы в MAX.
10. Worker ставит `send_status=sent` или `failed`.
11. После commit socket event `message.status_changed`.

## 9. Отправка и retry

Требование:

- если отправка в MAX упала, сообщение остается в БД;
- в UI показывается `failed`;
- менеджер может нажать retry;
- retry не создает новое сообщение, а повторяет отправку того же `Message.id`.

Решение:

- `send_status=queued` — ожидает отправки;
- `send_status=sending` — worker отправляет;
- `send_status=sent` — MAX принял;
- `send_status=failed` — финальная ошибка или временная ошибка после лимита попыток.

По failed message:

- согласован вариант с кнопкой retry;
- final failed не должен навсегда блокировать весь чат;
- UI показывает failed bubble;
- новые сообщения можно отправлять дальше;
- retry failed message отправляет тот же `Message.id`.

## 10. Последовательность outgoing в MAX

Требование:

- сообщения в один conversation должны уходить в MAX последовательно.

Правило:

- не отправлять параллельно два outgoing queued message в один `Conversation`;
- worker берет самое раннее queued message по `Message.id`;
- перед отправкой переводит его в `sending`;
- следующие сообщения этого conversation отправляются после `sent` или final `failed` предыдущего.

MVP:

- один worker process;
- query по queued messages order by `id`;
- позже можно добавить DB row locks и несколько workers.

## 11. Socket/realtime

Socket не является источником данных. Socket только сообщает, что БД изменилась.

События:

- `conversation.created`
- `conversation.updated`
- `message.created`
- `message.status_changed`
- `attachment.updated`

Payload:

- `conversation_id`
- `message_id`
- `last_message_id`
- минимальные display fields.

Надежность:

- при reconnect UI делает sync через API;
- если есть пропуск message id, UI делает `GET /api/conversations/{id}/messages/?after_id=<last_seen_id>`.

## 12. Manager UI in Django Admin + Unfold

Решение:

- Основной интерфейс менеджера работает внутри Django Admin shell на теме Unfold.
- Менеджер логинится через стандартный Django/Admin login.
- Менеджер — это Django `User` с `is_staff=True`.
- После входа менеджер видит список пользователей MAX (`MaxContact`) в Django Admin.
- В admin/sidebar есть пункт "Чаты".
- При переходе в "Чаты" в content area открывается React/Chatscope UI.
- Sidebar Django/Unfold остается на экране.
- Не встраиваем Chatscope в стандартные model changeform/changelist; делаем custom admin page.

Маршруты:

- `/admin/` — Django Admin + Unfold shell.
- `/admin/support/maxcontact/` — список пользователей MAX.
- `/admin/support/chats/` — custom admin page с Chatscope app.
- `/support/` — optional redirect на `/admin/support/chats/` для короткого URL.
- `/support/conversations/<id>/` — optional redirect/deep-link на Chatscope с выбранным conversation.

Внедрение:

1. React/Chatscope build через Vite.
2. Build кладется в Django static files.
3. Django/Unfold custom admin template подключает JS/CSS bundle.
4. Auth через обычную Django session.
5. API под той же session auth.
6. CSRF для POST.
7. WebSocket auth через session cookie при Channels.

Пользовательский опыт:

- менеджер логинится один раз;
- стартовая рабочая зона — список пользователей MAX;
- из admin/sidebar переходит в "Чаты";
- отдельной авторизации для chat UI нет;
- визуально это часть одного Django/Unfold приложения.

CSV export:

- Django не дает готовую кнопку "export CSV" из коробки.
- Django дает нативный механизм admin actions.
- Для `MaxContact` делаем admin action/custom admin URL, который возвращает CSV response.
- Для больших объемов использовать streaming response.

Superuser/service UX:

- Все основные таблицы регистрируются в Django Admin.
- Superuser видит служебные таблицы: `RawUpdate`, `Message`, `MessageAttachment`, `DeliveryAttempt`, `ManagerActionLog`.
- Staff managers видят только разрешенные рабочие разделы по permissions/groups.

## 13. Chatscope footer автора

В footer каждого сообщения показывать автора.

Incoming:

- `MAX: @username`
- или `MAX: first_name last_name`
- fallback: `MAX user <max_user_id>`

Outgoing:

- `Manager: <User.get_full_name()>`
- fallback: `Manager: <username>`

System:

- `System`

API serializer должен отдавать:

- `author_display`
- `author_kind`
- `manager_id`
- `contact_id`
- `direction`
- `send_status`

Frontend не должен угадывать автора из разных полей.

## 14. API MVP

Webhook:

- `POST /webhooks/max/`

Pages:

- `GET /support/`
- `GET /support/conversations/<id>/`

JSON API:

- `GET /api/conversations/`
- `GET /api/conversations/{id}/messages/?after_id=...`
- `POST /api/conversations/{id}/messages/`
- `POST /api/conversations/{id}/assign/`
- `POST /api/conversations/{id}/close/`
- `POST /api/messages/{id}/retry/`
- `GET /api/attachments/{id}/download/`
- `GET /admin/export/max-users.csv`

## 15. CSV export

Экспортировать пользователей MAX, то есть `MaxContact`.

Колонки:

- `max_user_id`
- `username`
- `first_name`
- `last_name`
- `is_bot`
- `last_activity_time`
- `first_seen_at`
- `last_seen_at`
- `conversation_count`
- `message_count`
- `last_message_at`
- `active_conversation_status`
- `assigned_to`

Для больших объемов делать streaming response.

## 16. Файлы

Входящие файлы:

1. Получить attachment payload из MAX.
2. Сохранить metadata в `MessageAttachment`.
3. Сохранить raw attachment JSON.
4. При необходимости скачать/кешировать файл в storage.

Исходящие файлы:

1. Менеджер прикрепляет файл в Chatscope.
2. Django сохраняет файл через `FileField`.
3. Создается `MessageAttachment(upload_status=pending)`.
4. Worker вызывает `POST /uploads?type=...`.
5. Worker загружает файл на выданный URL.
6. Worker отправляет `POST /messages` с attachment payload.
7. При `attachment.not.ready` retry с backoff.

Ограничения:

- MAX upload принимает один файл за раз;
- MAX docs указывают лимит файла до 4 GB;
- нужно ограничить размер файлов на nginx/Django уровне;
- protected download обязателен.

## 17. Безопасность

Обязательно:

- `MAX_BOT_TOKEN` только в env/secret storage.
- `MAX_WEBHOOK_SECRET` только в env/secret storage.
- Webhook secret проверять constant-time comparison.
- Staff views закрыть `login_required` + `is_staff`/permissions.
- Файлы отдавать через protected endpoint.
- Ограничить upload size.
- Проверять MIME/extension.
- Не удалять сообщения физически: использовать soft-delete/status.
- Для webhook retries использовать `dedupe_key`.
- Для outbound использовать `Message.id` как idempotency anchor.
- Соблюдать MAX rate limit 30 rps.

## 17.1. Logging and audit

Обязательное требование:

- логировать все важные действия менеджеров и системы;
- бизнес-аудит хранить в БД через `ManagerActionLog`;
- технические service events писать в structured application logs;
- не писать в stdout полные raw payloads, токены, secrets, cookies, session IDs и содержимое приватных файлов.

Manager audit в БД:

- login/logout при необходимости через Django signals или admin history, если это не усложняет MVP;
- назначение/снятие `assigned_to`;
- закрытие/переоткрытие conversation;
- отправка outgoing message;
- retry failed message;
- upload/download attachment;
- CSV export;
- service/admin actions над raw updates/messages/attachments.

Service logs:

- webhook received/processed/duplicate/failed;
- MAX contact upsert;
- conversation created/updated;
- message created/status changed;
- worker picked/sent/failed/retried message;
- MAX API request result without token and without full private payload;
- file upload/download metadata without file content;
- permission denied/security-relevant events.

Log format:

- timestamp;
- event name;
- severity;
- request id/correlation id if available;
- actor user id for manager actions;
- conversation id/message id/contact id where available;
- external MAX ids where safe;
- error code and short sanitized error text.

MVP defaults:

- DB audit через `ManagerActionLog`;
- outbound delivery diagnostics через `DeliveryAttempt`;
- app logs через standard Python `logging` to stdout for Docker/systemd;
- raw webhook payload хранится в `RawUpdate.payload`, но не печатается целиком в logs.
- retention для audit/service logs: 7 дней.

## 18. Acceptance criteria

1. Если пользователь написал в MAX, сообщение сохраняется в БД.
2. Если socket недоступен, сообщение не теряется и видно после refresh.
3. Входящие MAX messages сортируются по `Message.timestamp` из MAX, при равенстве — по `Message.id`.
4. Если менеджер отправил сообщение, оно сначала сохраняется в БД как `queued`.
5. После сохранения исходящее сообщение сразу видно всем менеджерам.
6. Worker отправляет исходящее сообщение в MAX.
7. При успехе статус становится `sent`.
8. При ошибке статус становится `failed`.
9. Для failed message есть retry.
10. Retry не создает новый message, а повторяет отправку того же `Message.id`.
11. Все менеджеры видят все chats.
12. Любой менеджер может ответить в любой chat.
13. `assigned_to` не блокирует ответы других менеджеров.
14. У каждого outgoing manager message есть `manager_id`.
15. В Chatscope footer видно автора сообщения.
16. Chat UI работает внутри Django по `/support/`.
17. CSV export пользователей доступен из web-админки.
18. Файлы можно принять от пользователя и отправить пользователю.
19. Важные manager actions пишутся в `ManagerActionLog`.
20. Важные service events пишутся в structured logs без secrets/raw payload dumps.

## 19. План реализации 80/20

Этап 1: Django каркас

- Django project.
- App `support`.
- MySQL settings via env.
- Dockerfile.
- Compose без обязательного MySQL.
- Django Admin.
- Models + migrations.

Этап 2: MAX webhook ingest

- `POST /webhooks/max/`.
- Secret check.
- Raw update save.
- Dedupe.
- Parse `message_created` / `bot_started`.
- Upsert contact.
- Create conversation/message/attachments.

Этап 3: manager chat UI

- `/support/` staff-only view.
- Chatscope layout.
- Conversation list.
- Message history.
- Send text.
- Footer author.
- Socket or polling fallback.

Этап 4: outbound MAX

- Thin `MaxClient`.
- Send text via `POST /messages`.
- Store statuses.
- Retry failed.
- Sequential sending per conversation.

Этап 5: files

- Upload from manager.
- `FileField` storage.
- MAX `/uploads`.
- Send attachment.
- Retry `attachment.not.ready`.
- Protected downloads.

Этап 6: admin operations

- CSV export.
- Admin filters.
- Assignment/status actions.
- Audit log.

## 20. Команда навыков и агентов для реализации

Project-local skills установлены в:

- `.agents/skills/`

Provenance установлен в:

- `.agents/library-lock.json`

### Superpowers

Использовать как execution discipline:

- `using-superpowers` — обязательный entrypoint для применения Superpowers.
- `writing-plans` — план реализации перед крупными этапами.
- `executing-plans` — выполнение плана без расползания scope.
- `test-driven-development` — тесты до/вместе с реализацией критичных flow.
- `systematic-debugging` — отладка по root cause, а не перебор.
- `verification-before-completion` — закрывать этап только после evidence.
- `dispatching-parallel-agents` — параллелить независимые workstreams при необходимости.
- `finishing-a-development-branch` — финальная подготовка branch перед сдачей.

### Project skills

Использовать по назначению:

- `domain-modeling` — финализация модели `MaxContact`, `Conversation`, `Message`, `Attachment`.
- `queue-processing-patterns` — worker/outbox/retry/FIFO per conversation.
- `db-migration-reviewer` — Django/MySQL migrations, indexes, rollback safety.
- `integration-test-planner` — MAX webhook/API/files integration tests.
- `accessibility-basic-check` — доступность Chatscope/Django UI.
- `threat-modeling` — webhook, token, files, staff access, data leakage.
- `observability-setup` — logs/metrics/statuses for webhook/worker/MAX sends.
- `ui-test` — browser/UI validation for Chatscope flows.
- `improve-codebase-architecture` — architecture review before implementation grows.
- `grill-with-docs` — проверять decisions against docs and local references.

### Project agents

Agent profiles установлены в:

- `.codex/agents/`

Рекомендуемая команда:

- `engineering-backend-architect` — Django architecture, DB-first flow, API boundaries.
- `engineering-database-optimizer` — MySQL schema, indexes, ordering, CSV export queries.
- `engineering-frontend-developer` — Chatscope UI, Vite integration, staff-only app.
- `engineering-devops-automator` — Docker, env, deployment, worker process.
- `engineering-security-engineer` — webhook secret, tokens, file access, auth.
- `engineering-code-reviewer` — review before merge/push.
- `design-ux-architect` — support desk UX, chat footer, status display.
- `project-management-project-shepherd` — keep MVP scope and acceptance criteria aligned.

### Suggested implementation order

1. `using-superpowers` + `writing-plans`.
2. `domain-modeling` + backend/database agents.
3. Django models/migrations/admin.
4. MAX webhook ingest using `repost_bot-main` as reference.
5. DB-first message API.
6. Chatscope UI using `telegram-mtproto-web-gateway` as reference.
7. Worker/outbox/retry/FIFO.
8. Files flow.
9. CSV export.
10. Security/threat model pass.
11. UI/integration tests.
12. Verification before completion.

## 21. Не подмешивать сюда

Анализ конкурентов живет отдельно:

- `docs/competitor_research.md`

В это ТЗ конкурентный анализ не добавлять, чтобы не мешать продуктовые решения и рыночные заметки.

## 22. Источники

MAX:

- https://dev.max.ru/docs-api
- https://dev.max.ru/docs-api/objects/User
- https://dev.max.ru/docs-api/objects/Message
- https://dev.max.ru/docs-api/objects/Update
- https://dev.max.ru/docs-api/methods/POST/subscriptions
- https://dev.max.ru/docs-api/methods/POST/messages
- https://dev.max.ru/docs-api/methods/POST/uploads

Chatscope:

- https://chatscope.io/docs/
- https://github.com/chatscope/chat-ui-kit-react

Local references:

- `/root/projects/repost_bot-main`
- `/root/projects/telegram-mtproto-web-gateway`
