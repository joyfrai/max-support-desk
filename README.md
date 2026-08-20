# MAX Help Desk

Self-hosted help desk для обращений из мессенджера MAX. Команда получает отдельную web-панель, история диалогов хранится на вашем сервере, а ответы уходят клиенту обратно в MAX.

[![Демо-доступ](https://img.shields.io/badge/Демо--доступ-yagix.ru%2Fmaxhelpdeskdemo-0b5cff)](https://yagix.ru/maxhelpdeskdemo/)
[![Лицензия MIT](https://img.shields.io/badge/license-MIT-0b5cff.svg)](LICENSE)
[![Язык: Python](https://img.shields.io/badge/Python-3.11%2B-111418.svg)](pyproject.toml)

## Зачем этот проект

MAX Help Desk подходит командам, которым нужна собственная панель поддержки без SaaS-зависимости и платы за каждого менеджера:

- данные и код остаются под вашим контролем;
- менеджеры отвечают из привычной web-панели;
- входящие сообщения приходят через MAX webhook;
- исходящие ответы отправляет отдельный worker;
- realtime-обновления работают через Django Channels и Redis;
- проект можно развернуть на своём VPS и дорабатывать под свои процессы.

Открытый demo доступен по адресу [yagix.ru/maxhelpdeskdemo](https://yagix.ru/maxhelpdeskdemo/). В демо используются тестовые данные и отдельная SQLite-база; production MAX/Telegram credentials туда не подключены.

## Возможности

- Django Admin и современная staff-only панель чатов на Chatscope.
- Список контактов MAX, статусы обращений, непрочитанные сообщения и назначение менеджера.
- Отправка текста и файлов из рабочей панели.
- Входящий MAX webhook с проверкой секрета и дедупликацией событий.
- Очередь исходящих сообщений и журнал попыток доставки.
- WebSocket-обновления без перезагрузки страницы.
- Audit log действий менеджеров.
- Защищённая выдача вложений и CSV-экспорт контактов.
- Read-only external API с OpenAPI-схемой и пагинацией.

## Архитектура

```text
MAX → webhook → Django + MySQL → Chatscope admin
                         ├──────→ WebSocket / Redis
                         └──────→ outbound worker → MAX API
```

Основные компоненты:

- `max_support_desk/` — Django settings, URL routes, ASGI/WSGI.
- `support/` — модели, webhook, staff API, realtime и worker.
- `frontend/` — React/Vite bundle для чатов внутри Django Admin.
- `deploy/nginx/` — пример reverse proxy с HTTPS и WebSocket.
- `docs/` — техническая документация, threat model и исследование решений.

## Быстрый запуск с Docker

Требования: Docker, Docker Compose plugin, MySQL 8 или совместимая база и домен с HTTPS.

```bash
git clone https://github.com/joyfrai/max-support-desk.git
cd max-support-desk
cp .env.example .env
```

Заполните `.env` как минимум:

```dotenv
DJANGO_SECRET_KEY=длинный-случайный-секрет
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=support.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://support.example.com

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=max_support_desk
MYSQL_USER=max_support_desk
MYSQL_PASSWORD=пароль-базы

MAX_BOT_TOKEN=токен-бота
MAX_WEBHOOK_SECRET=секрет-webhook
SUPPORT_DESK_PUBLIC_URL=https://support.example.com
```

Запустите сервисы и примените миграции:

```bash
docker compose build
docker compose up -d redis web worker
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Готовый пример Nginx находится в [`deploy/nginx/max-support-desk.conf`](deploy/nginx/max-support-desk.conf). После настройки домена панель будет доступна по `/admin/`, а webhook — по `/webhooks/max/`.

## Локальный preview на SQLite

Preview запускается с тестовыми данными и не требует MySQL. Пароль задаётся явно через переменную окружения, чтобы в проекте не было известного default-пароля:

```bash
export DEMO_ADMIN_PASSWORD='локальный-пароль-для-preview'
docker compose -f docker-compose.yml -f docker-compose.sqlite-preview.yml up -d redis web
```

Панель будет доступна на `http://127.0.0.1:8066/admin/`.

## Внешний read-only API

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

## Nginx

Готовый пример находится в [`deploy/nginx/max-support-desk.conf`](deploy/nginx/max-support-desk.conf). После настройки домена панель будет доступна по `/admin/`, webhook — по `/webhooks/max/`, а WebSocket — по `/ws/`.

Для интеграций доступны:

```text
GET /api/external/conversations/
GET /api/external/conversations/<conversation_id>/messages/
GET /api/external/openapi.json
```

API включается только при заданном `SUPPORT_EXTERNAL_API_TOKEN` и принимает:

```http
Authorization: Bearer <SUPPORT_EXTERNAL_API_TOKEN>
```

`limit` по умолчанию равен `100`, сортировка по умолчанию — от новых записей к старым, для навигации используется `from`. Полный контракт доступен в OpenAPI endpoint.

## Конфигурация и безопасность

Секреты хранятся только в `.env` или в deployment secret store. Файл `.env` и runtime-данные исключены из Git. Проверка текущего tracked-содержимого и Git history не выявила production credentials. В старой локальной preview-конфигурации встречается тестовый placeholder; его нельзя использовать в production.

Для production:

- держите `DJANGO_DEBUG=false`;
- задайте уникальные `DJANGO_SECRET_KEY`, `MAX_WEBHOOK_SECRET` и `SUPPORT_EXTERNAL_API_TOKEN`;
- ограничьте `DJANGO_ALLOWED_HOSTS` и `DJANGO_CSRF_TRUSTED_ORIGINS` своим доменом;
- используйте HTTPS;
- запускайте Redis и приложение только на loopback/private network;
- не публикуйте `.env`, SQLite/MySQL dump и каталог `media/`.

Threat model проекта лежит в [`docs/security_threat_model.md`](docs/security_threat_model.md).

## Разработка

Backend:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
python manage.py migrate
pytest -q
python manage.py check
```

Frontend:

```bash
cd frontend
npm ci
npm run build
```

Перед pull request проверьте `git diff --check`, backend tests и frontend build.

## Участие в проекте

Исправления и предложения принимаются через GitHub Issues и Pull Requests. Перед большим изменением сначала опишите задачу, затронутые части системы и способ проверки. Детали — в [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Лицензия и связь

Проект распространяется по открытой лицензии [MIT](LICENSE).

По вопросам установки и доработок: [написать в Telegram](https://t.me/egorprh).
