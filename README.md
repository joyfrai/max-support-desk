# MAX Support Desk

MVP support desk для сообщений из MAX: Django admin, staff-only Chatscope UI, webhook для входящих сообщений и worker для исходящей очереди.

## Что нужно до установки

- Домен для support desk, например `support.example.com`.
- HTTPS-сертификат для домена. Практичный вариант: Let's Encrypt через `certbot`.
- Сервер с Docker и Docker Compose plugin.
- MySQL 8 или совместимая БД. Для локальной проверки можно использовать SQLite, но production лучше запускать на MySQL.
- Токен MAX bot.
- Секрет webhook для MAX. Он должен совпадать с `MAX_WEBHOOK_SECRET` в `.env`.

## Быстрый порядок запуска на сервере

1. Клонировать репозиторий:

```bash
git clone https://github.com/joyfrai/max-support-desk.git /opt/max-support-desk
cd /opt/max-support-desk
```

2. Создать `.env`:

```bash
cp .env.example .env
nano .env
```

Минимально заполнить:

```bash
DJANGO_SECRET_KEY=replace-with-long-random-secret
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=support.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://support.example.com

MYSQL_HOST=your-mysql-host
MYSQL_PORT=3306
MYSQL_DATABASE=max_support_desk
MYSQL_USER=max_support_desk
MYSQL_PASSWORD=replace-with-db-password

MAX_BOT_TOKEN=replace-with-max-bot-token
MAX_WEBHOOK_SECRET=replace-with-webhook-secret
SUPPORT_DESK_PUBLIC_URL=https://support.example.com

# Optional: notifications about new incoming MAX messages.
# If token/chat IDs are empty, notifications are skipped.
TELEGRAM_BOT_TOKEN=
TELEGRAM_NOTIFICATION_CHAT_ID=
MAX_NOTIFICATION_CHAT_ID=

AUDIT_LOG_RETENTION_DAYS=7
SUPPORT_LOG_LEVEL=INFO
```

Можно вместо `MYSQL_*` использовать одну строку:

```bash
DATABASE_URL=mysql://max_support_desk:password@mysql-host:3306/max_support_desk?charset=utf8mb4
```

3. Собрать и запустить контейнеры:

```bash
docker compose build
docker compose up -d redis web worker
```

Redis поднимается только во внутренней Docker-сети и наружу не публикуется. Он нужен Django Channels для WebSocket-событий между web и worker.

4. Применить миграции:

```bash
docker compose exec web python manage.py migrate
```

5. Создать суперпользователя Django:

```bash
docker compose exec web python manage.py createsuperuser
```

6. Открыть admin:

```text
https://support.example.com/admin/
```

Менеджеры должны быть Django users с `is_staff=True`. Раздел чатов доступен внутри admin sidebar: `Поддержка -> Чаты`.

## Уведомления о новых сообщениях

При входящем `message_created` приложение может отправить уведомление в Telegram channel и/или MAX chat/channel. Если настройки пустые, отправка просто пропускается.

Настройки:

```bash
TELEGRAM_BOT_TOKEN=123456:telegram-bot-token
TELEGRAM_NOTIFICATION_CHAT_ID=-1001234567890
MAX_NOTIFICATION_CHAT_ID=123456789
SUPPORT_DESK_PUBLIC_URL=https://support.example.com
```

В уведомлении будут фамилия/имя пользователя MAX, MAX ID, никнейм, текст сообщения и ссылка на `/admin/support/chats/`.

## Webhook MAX

В приложении уже есть отдельный route для webhook:

```text
POST /webhooks/max/
```

Публичный URL для настройки в MAX:

```text
https://support.example.com/webhooks/max/
```

Секрет webhook передается в HTTP header:

```text
X-Max-Bot-Api-Secret: <MAX_WEBHOOK_SECRET>
```

Значение должно совпадать с `MAX_WEBHOOK_SECRET` в `.env`. Если секрет не совпадает, приложение вернет `403`.

## External read-only API

Для внешней интеграции доступен отдельный read-only API поверх тех же диалогов и сообщений.

Что включить в `.env`:

```bash
SUPPORT_EXTERNAL_API_TOKEN=replace-with-long-random-token
```

Routes:

```text
GET /api/external/conversations/
GET /api/external/conversations/<conversation_id>/messages/
GET /api/external/openapi.json
```

Auth header:

```text
Authorization: Bearer <SUPPORT_EXTERNAL_API_TOKEN>
```

Примеры:

```bash
curl https://support.example.com/api/external/conversations/ \
  -H "Authorization: Bearer $SUPPORT_EXTERNAL_API_TOKEN"

curl "https://support.example.com/api/external/conversations/?from=0&limit=100&sort=desc" \
  -H "Authorization: Bearer $SUPPORT_EXTERNAL_API_TOKEN"

curl "https://support.example.com/api/external/conversations/42/messages/?from=0&limit=100&sort=desc" \
  -H "Authorization: Bearer $SUPPORT_EXTERNAL_API_TOKEN"
```

Pagination and sorting:

- `limit` по умолчанию `100`
- `from` по умолчанию `0`
- `sort=desc` по умолчанию для диалогов и сообщений, то есть сначала самые новые
- при необходимости можно запросить `sort=asc`
- `offset` пока тоже принимается как backward-compatible alias для `from`

`/api/external/openapi.json` отдает OpenAPI schema для этих endpoint'ов. Ее можно импортировать в Postman, Swagger UI или любой другой клиент, который понимает OpenAPI.

## Nginx

Готовый пример лежит в [deploy/nginx/max-support-desk.conf](deploy/nginx/max-support-desk.conf).

Установить конфиг:

```bash
sudo cp deploy/nginx/max-support-desk.conf /etc/nginx/sites-available/max-support-desk.conf
sudo ln -s /etc/nginx/sites-available/max-support-desk.conf /etc/nginx/sites-enabled/max-support-desk.conf
sudo nginx -t
sudo systemctl reload nginx
```

Перед применением заменить `support.example.com` на реальный домен и проверить пути к сертификату:

```text
/etc/letsencrypt/live/<domain>/fullchain.pem
/etc/letsencrypt/live/<domain>/privkey.pem
```

Nginx проксирует admin, static, Chatscope UI, webhook MAX и WebSocket route `/ws/` на Docker web port `127.0.0.1:8066`.

## Локальная preview-сборка на SQLite

Для быстрой проверки без внешней БД:

```bash
docker compose -f docker-compose.yml -f docker-compose.sqlite-preview.yml up -d redis web
```

Preview запускает SQLite volume и demo data. Web будет доступен на:

```text
http://127.0.0.1:8066/admin/
```

## Проверка после обновлений

Обновить уже развернутый production:

```bash
cd /var/www/fastuser/data/www/max-support-desk

git status --short
git pull --ff-only

docker compose build web worker
docker compose up -d web worker
```

Если менялись зависимости, frontend или Django settings, rebuild обязателен. Для обычных backend/frontend правок достаточно пересобрать и пересоздать `web` и `worker`; Redis volume трогать не нужно.

Применить миграции и проверить Django:

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
```

Проверить контейнеры и логи:

```bash
docker compose ps
docker compose logs --tail=100 web worker
docker compose logs --tail=50 redis
```

Проверить локальные порты внутри сервера:

```bash
ss -ltnp | grep -E ':8066|:6379|:3306|:80|:443'
docker compose port redis 6379
```

Ожидаемо:

- `web` слушает `127.0.0.1:8066`;
- `redis` доступен только на `127.0.0.1:6379`;
- `mysql` доступен на `127.0.0.1:3306` или на указанном внешнем MySQL host;
- наружу открыты только nginx `80/443` для домена.

Проверить HTTP/HTTPS endpoints:

```bash
curl -I http://127.0.0.1:8066/admin/login/
curl -I http://127.0.0.1:8066/support/
curl -I http://127.0.0.1:8066/webhooks/max/

curl -I https://maxdesk.dept.trading/admin/login/
curl -I https://maxdesk.dept.trading/admin/support/chats/
```

Ожидаемо:

- `/admin/login/` возвращает `200`;
- `/support/` может вернуть `302` на `/admin/support/chats/`;
- GET `/webhooks/max/` возвращает `405`, потому что webhook принимает только `POST`.

Для ручной проверки:

- `/admin/` открывает Django admin.
- `/admin/support/maxcontact/` показывает пользователей MAX только для просмотра.
- `/admin/support/chats/` открывает Chatscope UI внутри Django admin.
- `POST /webhooks/max/` принимает webhook только с правильным `X-Max-Bot-Api-Secret`.
- Новое входящее сообщение MAX появляется в открытом `/admin/support/chats/` без перезагрузки страницы.
- Входящий файл MAX отображается как вложение; если MAX payload содержит download URL, менеджер может скачать файл по ссылке из чата.
- Исходящий файл из чата получает статус отправки и доходит в MAX; при ошибке остается доступна кнопка `Повторить`.
