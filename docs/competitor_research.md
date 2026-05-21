# MAX Support Desk: исследование конкурентов

Дата: 2026-05-21

## Короткий вывод

Для Telegram подобных решений много. Рынок уже понятный:

- легкие Telegram-native inbox-сервисы;
- омниканальные helpdesk/CRM с Telegram как каналом;
- open-source/self-hosted платформы вроде Chatwoot;
- enterprise-сервисы с маршрутизацией, SLA, аналитикой, AI и интеграциями.

Для MAX решения уже есть, но рынок менее зрелый:

- несколько омниканальных платформ заявляют поддержку MAX;
- есть helpdesk-интеграции MAX через бота;
- есть интеграторы, которые делают MAX + Telegram + CRM под заказ;
- мало публичных узких продуктов формата "self-hosted MAX support desk с простой Django-админкой".

Вывод для нашего проекта: ниша не пустая, но у нас может быть сильная позиция как простое self-hosted/on-premise решение под MAX, без тяжелой омниканальности и без зависимости от SaaS.

## Telegram: какие решения уже есть

### Telegram-native shared inbox

Такие сервисы превращают Telegram-группу с topics в рабочий helpdesk.

Примеры:

- GramDesk
- SupportHub
- Omnigram

Что предлагают:

- клиент пишет в Telegram-бота;
- сервис создает отдельную тему/диалог для клиента;
- команда отвечает из приватной Telegram-группы;
- ответ уходит клиенту обратно в бот;
- часто нет отдельной web-админки;
- низкая цена и быстрый запуск.

Сильные стороны:

- очень быстрый onboarding;
- менеджерам не нужен новый интерфейс;
- дешево для маленьких команд;
- хорошо подходит для фрилансеров, магазинов, маленьких сервисов.

Слабые стороны:

- интерфейс ограничен Telegram topics;
- сложнее сделать нормальные роли, аудит, CSV, расширенную аналитику;
- сложнее контролировать файлы, retention, права доступа;
- данные часто остаются в Telegram-потоке, а не в полноценной БД клиента.

Что взять нам:

- простую логику "клиент пишет боту -> команда отвечает из общего места";
- быструю настройку бота;
- отдельный conversation/thread на клиента;
- низкий порог входа.

Что не копировать:

- зависимость рабочего процесса от Telegram topics;
- отсутствие нормальной web-админки;
- слабый контроль над данными.

### Омниканальные helpdesk/CRM с Telegram

Примеры:

- Chatwoot
- Jivo
- Crisp
- Usedesk
- Umnico
- CraftTalk

Что предлагают:

- Telegram как один из каналов рядом с email, WhatsApp, web chat, VK и другими;
- unified inbox;
- назначение операторов;
- internal notes;
- canned responses/templates;
- labels/tags;
- automations;
- reports/analytics;
- media/file support.

Сильные стороны:

- зрелая модель helpdesk;
- много каналов;
- готовая аналитика;
- роли, команды, маршрутизация;
- часть решений уже умеет rich media.

Слабые стороны:

- тяжелые для простой задачи "поддержка в одном MAX-боте";
- часто SaaS и per-seat/per-channel pricing;
- сложная кастомизация;
- self-hosted доступен не у всех;
- MAX поддерживается не везде или только как новый канал.

Что взять нам:

- единая лента сообщений;
- assignment;
- private notes;
- быстрые ответы;
- теги;
- статусы обращения;
- отчеты по времени ответа;
- хранение вложений рядом с conversation.

Что отложить:

- полноценную омниканальность;
- AI-автоответы;
- сложные SLA;
- интеграции с десятками CRM.

### Open-source/self-hosted

Главный ориентир: Chatwoot.

Почему важен:

- open-source;
- поддерживает Telegram Bot API;
- хранит media with conversation;
- дает team inbox, assignment, labels, automations, reports;
- можно self-host.

Ограничение для нас:

- Chatwoot уже решает часть Telegram-задачи, но не является MAX-first продуктом;
- интеграцию с MAX придется писать отдельно;
- если нужен простой Django/MySQL проект, Chatwoot как Ruby/Rails платформа может быть избыточен.

Практический вывод:

- можно брать Chatwoot как UX/model reference;
- не стоит копировать весь масштаб платформы в MVP.

## MAX: какие решения уже есть

### HelpDeskEddy

Заявляет интеграцию с MAX через бота.

Возможности по публичному описанию:

- принимать обращения из MAX;
- автоматически создавать заявки;
- вести переписку с клиентом внутри HelpDeskEddy;
- использовать автоответы и автораспределение;
- объединять MAX с другими каналами.

Вывод:

- прямой конкурент для support/helpdesk;
- сильнее нас как готовая helpdesk-платформа;
- слабее для сценария "легкий self-hosted MAX-only проект с полной кастомизацией".

### Dialog Gate

Омниканальная CRM для мессенджеров.

Заявляет:

- Telegram bots/personal accounts;
- WhatsApp;
- VK;
- MAX;
- Email;
- SMS;
- VK Notify;
- web chat;
- routing, templates, tags, analytics, канбан.

Вывод:

- конкурент в сегменте "единое окно для сообщений";
- сильный омниканальный угол;
- вероятно тяжелее и шире нашего MVP.

### Umnico

Омниканальная платформа для продаж и поддержки.

Заявляет:

- Telegram, WhatsApp, VK, MAX, Одноклассники, онлайн-чат и другие каналы;
- единый интерфейс;
- автоматическое распределение;
- шаблоны;
- горячие клавиши;
- чат-боты.

Вывод:

- конкурент как SaaS unified inbox;
- подтверждает, что MAX уже становится заявленным каналом в российских омниканальных платформах.

### CraftTalk

Омниканальная чат-платформа.

Заявляет:

- MAX, Telegram, Viber, web chat, Email и другие каналы;
- одно рабочее место оператора;
- распределение нагрузки;
- шаблоны ответов;
- KPI;
- база знаний.

Вывод:

- enterprise/omnichannel конкурент;
- важные features для будущего: база знаний, шаблоны, KPI, routing.

### Bot4Max

Интегратор под MAX.

Заявляет:

- MAX + Telegram;
- on-premise;
- CRM/1C integrations;
- кабинет операторов;
- аудит;
- SLA;
- custom/on-premise решения.

Вывод:

- прямой конкурент как кастомная разработка;
- сильный сигнал, что бизнесу нужны on-premise MAX решения;
- у нас может быть преимущество, если сделать готовый продукт, а не только проектную разработку.

### LEADTEX

Конструктор ботов и mini apps.

Заявляет:

- Telegram, MAX, WhatsApp, VK;
- visual bot builder;
- admin panel;
- messenger in personal cabinet;
- built-in CRM;
- рассылки и автоворонки.

Вывод:

- конкурент в сегменте no-code/low-code ботов;
- сильнее по bot builder;
- слабее, если клиенту нужен простой прозрачный support desk на своей инфраструктуре.

### SIPOUT Multichat

Заявляет:

- Telegram, VK, MAX, Avito;
- единый интерфейс;
- AI-manager;
- amoCRM integration;
- SLA, tags, export dialogs, KPI managers.

Вывод:

- конкурент в сегменте "AI + sales/support multichat";
- хорошо показывает ожидаемые функции зрелого продукта: SLA, tags, exports, KPI.

## Что это значит для нашего продукта

### Рынок Telegram

Telegram-support решения уже доказали спрос.

Паттерн повторяется у многих:

1. Клиент пишет боту.
2. Система создает диалог/тикет.
3. Менеджеры отвечают из общего интерфейса.
4. Сообщение уходит клиенту обратно.
5. Внутри есть assignment, notes, templates, tags, files, analytics.

Это ровно подтверждает выбранную архитектуру `Contact -> Conversation -> Message -> Attachment`.

### Рынок MAX

MAX уже появился в предложениях HelpDesk/CRM/интеграторов.

Но публично найденные решения в основном:

- омниканальные;
- SaaS;
- enterprise;
- кастомные;
- с фокусом на "всё в одном".

Меньше видно простых решений:

- MAX-only;
- self-hosted;
- Django/MySQL;
- с прозрачной БД;
- с легкой web-админкой;
- без тяжелой CRM.

Это хорошая точка входа.

## Возможное позиционирование нашего проекта

### Вариант 1: MAX-first self-hosted support desk

Основной оффер:

- "Поддержка клиентов из MAX-бота в web-админке на своей инфраструктуре".

Кому:

- компании, которым нельзя отдавать переписки в сторонний SaaS;
- бизнесы, которые уже идут в MAX;
- интеграторы, которым нужен базовый white-label модуль;
- небольшие команды, которым HelpDeskEddy/Umnico/CraftTalk тяжелы.

Сильные стороны:

- данные в своей БД;
- простой Docker deploy;
- внешняя MySQL;
- контроль файлов;
- понятная Django Admin;
- легкая кастомизация.

### Вариант 2: MAX + Telegram adapter

Оффер:

- "Единый support desk для MAX и Telegram, но без тяжелой омниканальности".

Архитектурно:

- добавить `Channel` / `ProviderAccount`;
- `MaxContact` переименовать позже в `ExternalContact`;
- `Message.provider = max/telegram`;
- файловую и message-модель оставить общей.

Риск:

- MVP станет шире и дольше.

Рекомендация:

- начинать с MAX-first, но не закрывать дверь для Telegram adapter.

## Feature map для MVP и после MVP

### Must-have MVP

- MAX webhook.
- Сохранение raw updates.
- Contact/conversation/message/attachment model.
- Web chat для менеджеров.
- Текстовые ответы.
- Прием/отправка файлов.
- Django users для менеджеров.
- CSV export users.
- Базовые статусы: `new`, `open`, `closed`.
- Search по username/name/message text.
- Protected download файлов.

### Should-have next

- Assignment.
- Tags.
- Internal notes.
- Quick replies/templates.
- Retry failed messages.
- Conversation close/reopen.
- Basic stats: first response time, messages per manager.
- Audit log manager actions.

### Later

- SLA.
- Departments/queues.
- AI suggestions.
- Auto-replies.
- Knowledge base.
- Telegram adapter.
- CRM integrations.
- Web widget.
- Public API.

## Риски

### Конкурентный риск

Если клиенту нужна большая омниканальность прямо сейчас, он выберет HelpDeskEddy, Umnico, CraftTalk или Dialog Gate.

Ответ:

- не соревноваться с ними в ширине;
- соревноваться в простоте, self-hosted, MAX-first, кастомизации и контроле данных.

### Product risk

Если сделать просто "еще один helpdesk", будет скучно и поздно.

Ответ:

- сделать упор на MAX;
- дать быстрый deploy;
- дать прозрачную БД;
- дать удобный Django admin;
- сделать интегратор-friendly архитектуру.

### Technical risk

MAX API и экосистема могут быстро меняться.

Ответ:

- хранить raw payloads;
- держать тонкий adapter layer;
- не размазывать MAX-specific поля по всему проекту;
- писать integration tests на реальные webhook samples.

## Практический алгоритм продукта

1. Сделать MAX-only MVP.
2. Не делать тяжелую омниканальность в первом релизе.
3. Сразу заложить provider adapter, но реализовать только MAX.
4. Сделать хороший web-chat, а не пытаться заменить Telegram topics.
5. Сделать надежные files + retries — это у конкурентов часто болит.
6. Сделать CSV/users export и audit как простое преимущество для бизнеса.
7. После MVP добавить assignment/tags/templates.
8. Потом решить, нужен ли Telegram adapter.

## Список конкурентов

### Telegram-focused

- GramDesk — легкий общий Telegram inbox, около $3 за бота в месяц, без оплаты за сотрудников.
- SupportHub — Telegram-first support desk в private topic group, web chat, email, routing, analytics.
- Omnigram — омниканальный CRM внутри Telegram-групп, WhatsApp/Instagram/LinkedIn/Gmail/Webhooks.
- Hotline.tg — Telegram CRM/support/sales positioning.
- Entergram — Telegram CRM для sales/support/community teams.

### Global helpdesk with Telegram

- Chatwoot — open-source/self-hosted, Telegram bot integration, media sync, team inbox, assignment, automations, reports.
- Jivo — Telegram через BotFather token, сообщения попадают в Jivo app.
- Crisp — Telegram bot integration into shared Inbox.
- Usedesk — Telegram personal account/channel support.
- CallHippo — Telegram shared inbox positioning.

### MAX-capable / Russian omnichannel

- HelpDeskEddy — MAX integration via bot, tickets and full correspondence inside helpdesk.
- Dialog Gate — Telegram, WhatsApp, VK, MAX, Email, SMS, web chat, routing, templates, analytics.
- Umnico — Telegram, WhatsApp, VK, MAX, Одноклассники, online chat and other channels in one interface.
- CraftTalk — MAX, Telegram, Viber, web chat, Email and other channels, operator workspace, KPI, KB.
- Bot4Max — custom/on-premise MAX + Telegram solutions, cabinet of operators, CRM/1C integrations.
- LEADTEX — bot/mini-app constructor for Telegram, MAX, WhatsApp, VK; admin panel, built-in CRM.
- SIPOUT Multichat — Telegram, VK, MAX, Avito, AI manager, amoCRM, SLA/tags/export/KPI.

## Sources

- GramDesk: https://gramdeskbot.com/ru/
- SupportHub: https://supporthub.tg/en
- Omnigram: https://omnigram.app/
- Chatwoot Telegram integration: https://www.chatwoot.com/features/telegram-integration/
- Jivo Telegram integration: https://www.jivochat.com/help/integrations/connecting-telegram.html
- Crisp Telegram integration: https://help.crisp.chat/en/article/how-to-connect-telegram-with-crisp-x2nkse/
- Usedesk Telegram integration: https://en.usedocs.com/article/35119
- HelpDeskEddy MAX integration: https://helpdeskeddy.ru/vozmoznosti/razlichnie-vozmoznosti-priema-zajavok/max-messenger
- Dialog Gate: https://dialoggate.ru/
- Umnico: https://umnico.com/ru/
- CraftTalk chat platform: https://crafttalk.ru/chat
- Bot4Max: https://bot4max.ru/
- LEADTEX: https://leadteh.ru/
- SIPOUT Multichat: https://chat.sipout.ai/

