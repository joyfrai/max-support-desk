from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from support.models import Conversation, MaxContact, Message


class Command(BaseCommand):
    help = "Create local demo users, contacts, conversations, and messages."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--username", default="admin", help="Demo superuser username.")
        parser.add_argument("--password", default="admin12345", help="Demo superuser password.")
        parser.add_argument("--reset", action="store_true", help="Reset demo conversations before seeding.")

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        username = options["username"]
        password = options["password"]
        reset = options["reset"]

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": "admin@example.local",
                "is_staff": True,
                "is_superuser": False,
            },
        )
        update_fields = ["is_staff", "is_superuser"]
        if created or not user.has_usable_password():
            user.set_password(password)
            update_fields.append("password")
        user.is_staff = True
        user.is_superuser = False
        user.save(update_fields=update_fields)
        user.user_permissions.set(
            Permission.objects.filter(content_type__app_label="support", codename__startswith="view_")
        )

        if reset:
            Conversation.objects.filter(contact__max_user_id__startswith="demo-").delete()
            MaxContact.objects.filter(max_user_id__startswith="demo-").delete()

        now = timezone.now()
        seed_rows = [
            {
                "user_id": "demo-1001",
                "username": "ivan_support",
                "first_name": "Иван",
                "last_name": "Петров",
                "chat_id": "demo-chat-1001",
                "status": Conversation.Status.OPEN,
                "unread": 1,
                "messages": [
                    ("incoming", "Здравствуйте, хочу уточнить статус заказа."),
                    ("outgoing", "Здравствуйте! Проверяю заказ по номеру из вашего профиля."),
                    ("incoming", "Номер заканчивается на 4821, заказ оформлял вчера вечером."),
                    ("outgoing", "Нашла: заказ собран и передан в доставку. Ожидаем курьера сегодня до 21:00."),
                    ("incoming", "Отлично, спасибо. А уведомление о доставке тоже придёт сюда?"),
                    ("outgoing", "Да, бот пришлёт сообщение с интервалом доставки и ссылкой на отслеживание."),
                    ("incoming", "Понял, буду ждать уведомление."),
                ],
            },
            {
                "user_id": "demo-1002",
                "username": "maria_max",
                "first_name": "Мария",
                "last_name": "Смирнова",
                "chat_id": "demo-chat-1002",
                "status": Conversation.Status.PENDING,
                "unread": 0,
                "messages": [
                    ("incoming", "Не получается открыть вложение в сообщении."),
                    ("outgoing", "Давайте проверим. Какая ошибка появляется после нажатия на файл?"),
                    ("incoming", "Пишет, что файл недоступен, хотя сообщение пришло только что."),
                    ("outgoing", "Поняла. Похоже, ссылка ещё обрабатывается. Попробуйте открыть чат заново."),
                    ("incoming", "Перезашёл, теперь файл скачивается, но имя отображается странно."),
                    ("outgoing", "Это исправим на нашей стороне. Сам файл уже открылся корректно?"),
                    ("incoming", "Да, содержимое в порядке. Спасибо за помощь."),
                    ("outgoing", "Хорошо, передала замечание команде, чтобы поправили отображение имени."),
                    ("incoming", "Буду иметь в виду, если повторится — напишу сюда."),
                ],
            },
            {
                "user_id": "demo-1003",
                "username": "retry_case",
                "first_name": "Алексей",
                "last_name": "Орлов",
                "chat_id": "demo-chat-1003",
                "status": Conversation.Status.OPEN,
                "unread": 0,
                "messages": [
                    ("incoming", "Можно повторить последнее сообщение?"),
                    ("failed", "Повторяю: ваш запрос уже в работе."),
                    ("incoming", "У меня оно так и не появилось, попробуйте ещё раз."),
                    ("outgoing", "Конечно. Повторяю сообщение и проверяю статус доставки."),
                    ("incoming", "Теперь вижу, спасибо."),
                    ("outgoing", "Отлично. Если сообщения снова пропадут, зафиксируем время и ID чата."),
                ],
            },
            {
                "user_id": "demo-1004",
                "username": "refund_question",
                "first_name": "Елена",
                "last_name": "Кузнецова",
                "chat_id": "demo-chat-1004",
                "status": Conversation.Status.PENDING,
                "unread": 2,
                "messages": [
                    ("incoming", "Здравствуйте. Хочу уточнить, когда вернутся деньги за отменённый заказ."),
                    ("outgoing", "Здравствуйте! Проверю операцию. Напомните, пожалуйста, дату отмены."),
                    ("incoming", "Отмена была в понедельник, оплата картой, сумма 3 490 рублей."),
                    ("outgoing", "Нашла платеж. Возврат создан сегодня в 09:40 и уже передан банку."),
                    ("incoming", "Сколько обычно занимает зачисление?"),
                    ("outgoing", "Банк обычно зачисляет возврат за 1–3 рабочих дня. Если срок пройдёт, проверим повторно."),
                    ("incoming", "Хорошо, тогда подожду до конца недели."),
                    ("outgoing", "Я оставила обращение открытым и вернусь с обновлением, если банк пришлёт статус."),
                    ("incoming", "Спасибо, теперь понятно."),
                    ("outgoing", "Пожалуйста! Если деньги поступят раньше, чат можно будет закрыть самостоятельно."),
                    ("incoming", "Договорились."),
                ],
            },
            {
                "user_id": "demo-1005",
                "username": "account_access",
                "first_name": "Дмитрий",
                "last_name": "Соколов",
                "chat_id": "demo-chat-1005",
                "status": Conversation.Status.OPEN,
                "unread": 0,
                "messages": [
                    ("incoming", "Не могу войти в аккаунт после смены телефона."),
                    ("outgoing", "Помогу восстановить доступ. Старый номер уже недоступен?"),
                    ("incoming", "Да, сим-карту заблокировали вчера."),
                    ("outgoing", "Тогда не будем отправлять код на старый номер. Подтвердите почту, указанную в профиле."),
                    ("incoming", "Почта d.sokolov@example.test, последние цифры заказа 1178."),
                    ("outgoing", "Данных достаточно. Отправила письмо со ссылкой на восстановление, проверьте папку «Спам»."),
                    ("incoming", "Письмо пришло, ссылка открывается."),
                    ("outgoing", "Отлично. Задайте новый пароль и включите дополнительную проверку в настройках безопасности."),
                    ("incoming", "Пароль обновил, но приложение всё ещё показывает старую сессию."),
                    ("outgoing", "Выйдите из приложения на старом устройстве через раздел «Активные сессии». После этого войдите заново."),
                    ("incoming", "Нашёл этот раздел, старая сессия закрыта."),
                    ("outgoing", "Теперь доступ должен работать штатно. Проверьте, пожалуйста, открывается ли история заказов."),
                    ("incoming", "Да, всё открылось. Спасибо, можно закрывать обращение."),
                ],
            },
            {
                "user_id": "demo-1006",
                "username": "delivery_delay",
                "first_name": "Ольга",
                "last_name": "Морозова",
                "chat_id": "demo-chat-1006",
                "status": Conversation.Status.OPEN,
                "unread": 1,
                "messages": [
                    ("incoming", "Курьер не приехал в выбранный интервал доставки."),
                    ("outgoing", "Проверяю маршрут. Напишите адрес или последние четыре цифры заказа."),
                    ("incoming", "Заказ 9036, доставка на Большую Никитскую."),
                    ("outgoing", "Вижу задержку на маршруте из-за перекрытия улицы. Новый интервал — с 19:30 до 20:30."),
                    ("incoming", "Мне нужно уйти в 20:00. Можно перенести на завтра?"),
                    ("outgoing", "Да, предложу ближайшие окна на завтра. Удобнее утром или после 18:00?"),
                    ("incoming", "После 18:00, пожалуйста."),
                    ("outgoing", "Есть окно с 18:00 до 20:00. Переношу доставку без дополнительной платы."),
                    ("incoming", "Подтверждаю перенос."),
                    ("outgoing", "Готово, новая дата и интервал уже отображаются в заказе."),
                    ("incoming", "Уведомление пока не пришло, это нормально?"),
                    ("outgoing", "Да, уведомление появится после подтверждения маршрута складом, обычно в течение часа."),
                    ("incoming", "Поняла, проверю позже."),
                    ("outgoing", "Я оставлю чат открытым до появления подтверждения."),
                    ("incoming", "Спасибо за помощь."),
                ],
            },
            {
                "user_id": "demo-1007",
                "username": "subscription_pause",
                "first_name": "Артём",
                "last_name": "Лебедев",
                "chat_id": "demo-chat-1007",
                "status": Conversation.Status.CLOSED,
                "unread": 0,
                "messages": [
                    ("incoming", "Хочу приостановить подписку на месяц, но не потерять настройки."),
                    ("outgoing", "Настройки и история сохранятся. Приостановка остановит списания до выбранной даты."),
                    ("incoming", "А доступ к уже созданным проектам останется?"),
                    ("outgoing", "Да, проекты останутся доступны для просмотра, но новые запуски будут недоступны."),
                    ("incoming", "Можно поставить паузу с первого числа следующего месяца?"),
                    ("outgoing", "Можно. Сейчас у вас оплаченный период до 31 числа, пауза начнётся 1-го."),
                    ("incoming", "Хорошо, поставьте паузу на один месяц."),
                    ("outgoing", "Готово. Следующее списание запланировано после окончания паузы."),
                    ("incoming", "Если передумаю, можно будет возобновить раньше?"),
                    ("outgoing", "Да, в разделе подписки есть кнопка «Возобновить сейчас»."),
                    ("incoming", "Нашёл, спасибо за подробное объяснение."),
                    ("outgoing", "Рада помочь. Закрываю обращение, но вы сможете написать в этот чат снова."),
                    ("incoming", "Отлично."),
                    ("outgoing", "Обращение закрыто. Хорошего дня!"),
                    ("incoming", "И вам хорошего дня."),
                    ("outgoing", "Спасибо!"),
                ],
            },
            {
                "user_id": "demo-1008",
                "username": "api_integration",
                "first_name": "Никита",
                "last_name": "Волков",
                "chat_id": "demo-chat-1008",
                "status": Conversation.Status.PENDING,
                "unread": 0,
                "messages": [
                    ("incoming", "Подключаем API к CRM, но события о новых сообщениях не приходят."),
                    ("outgoing", "Проверим по шагам. Webhook уже зарегистрирован и отвечает кодом 200?"),
                    ("incoming", "Да, проверка URL проходит, но в журнале CRM пусто."),
                    ("outgoing", "Тогда посмотрим секрет и формат события. В запросе передаётся заголовок X-MAX-Bot-Api-Secret?"),
                    ("incoming", "Передаётся, но мы читаем его из переменной окружения с пробелом в конце."),
                    ("outgoing", "Пробел может ломать сравнение. Уберите его и перезапустите обработчик webhook."),
                    ("incoming", "Исправил переменную, теперь получили первый тестовый event."),
                    ("outgoing", "Отлично. Проверьте ещё повторную доставку: одинаковый dedupe_key не должен создавать две записи."),
                    ("incoming", "Отправил один и тот же event дважды, в CRM появилась одна запись."),
                    ("outgoing", "Значит, дедупликация работает. Теперь проверьте вложение и пустой текст сообщения."),
                    ("incoming", "Вложение пришло, а пустое сообщение сохранилось как событие без текста."),
                    ("outgoing", "Это ожидаемое поведение. Для интерфейса можно показывать тип контента вместо пустой строки."),
                    ("incoming", "Понял. Есть ли ограничение на размер ответа от нашего обработчика?"),
                    ("outgoing", "Для webhook достаточно быстро вернуть 2xx, тяжёлую обработку лучше оставлять воркеру."),
                    ("incoming", "Хорошо, вынесем обработку в очередь."),
                    ("outgoing", "После этого можно включить мониторинг задержки между received_at и processed_at."),
                    ("incoming", "Добавил метрику, на тестах задержка меньше секунды."),
                    ("outgoing", "Отличный результат. Оставляю обращение ожидающим финального deploy в CRM."),
                    ("incoming", "Deploy запланирован на вечер, вернусь с результатом."),
                ],
            },
            {
                "user_id": "demo-1009",
                "username": "export_request",
                "first_name": "Светлана",
                "last_name": "Романова",
                "chat_id": "demo-chat-1009",
                "status": Conversation.Status.OPEN,
                "unread": 0,
                "messages": [
                    ("incoming", "Нужно выгрузить список клиентов за прошлый месяц."),
                    ("outgoing", "Сделаем. Нужны все клиенты или только те, кто писал в поддержку?"),
                    ("incoming", "Только активные обращения и последний статус каждого чата."),
                    ("outgoing", "Поняла. В выгрузке будут MAX ID, имя, последний контакт, статус и ответственный менеджер."),
                    ("incoming", "Добавьте ещё количество сообщений по каждому клиенту."),
                    ("outgoing", "Добавлю отдельную колонку с количеством сообщений."),
                    ("incoming", "Формат лучше CSV, чтобы открыть в таблицах."),
                    ("outgoing", "Да, подготовлю CSV в UTF-8 с BOM, чтобы русские заголовки корректно открылись."),
                    ("incoming", "Нужны ли права администратора для скачивания?"),
                    ("outgoing", "Да, ссылка доступна только сотрудникам support desk и пишется в журнал действий."),
                    ("incoming", "Хорошо. Можно ли отфильтровать закрытые чаты?"),
                    ("outgoing", "Можно выбрать только открытые и ожидающие обращения перед экспортом."),
                    ("incoming", "Тогда оставьте открытые и ожидающие."),
                    ("outgoing", "Фильтр применён. Проверяю, чтобы в CSV не попали вложения и токены."),
                    ("incoming", "Это важно, файл пойдёт руководителю."),
                    ("outgoing", "Проверила: экспорт содержит только служебные поля и текстовых сообщений в нём нет."),
                    ("incoming", "Отлично, скачайте тестовый файл в чат."),
                    ("outgoing", "Тестовый CSV готов. Проверьте кодировку и названия колонок."),
                    ("incoming", "Открылся корректно, колонки подходят."),
                    ("outgoing", "Тогда оставляю настройки фильтра для следующей выгрузки."),
                    ("incoming", "Спасибо, это сильно упростит еженедельный отчёт."),
                ],
            },
            {
                "user_id": "demo-1010",
                "username": "onboarding_help",
                "first_name": "Ирина",
                "last_name": "Белова",
                "chat_id": "demo-chat-1010",
                "status": Conversation.Status.NEW,
                "unread": 3,
                "messages": [
                    ("incoming", "Здравствуйте! Помогите настроить рабочее пространство для команды."),
                    ("outgoing", "Здравствуйте! Начнём с участников и ролей. Сколько человек будет работать в проекте?"),
                    ("incoming", "Пять человек: руководитель, два менеджера и два аналитика."),
                    ("outgoing", "Предлагаю выдать руководителю роль владельца, менеджерам — support, аналитикам — просмотр."),
                    ("incoming", "Аналитики смогут видеть переписку, но не отправлять сообщения?"),
                    ("outgoing", "Да, для них оставим только просмотр и экспорт отчётов."),
                    ("incoming", "Нужно ли создавать отдельные очереди для продаж и поддержки?"),
                    ("outgoing", "Лучше разделить очереди, если у них разные SLA и ответственные менеджеры."),
                    ("incoming", "У нас поддержка отвечает за два часа, продажи — в течение рабочего дня."),
                    ("outgoing", "Тогда настроим два SLA и разные статусы эскалации."),
                    ("incoming", "Можно ли автоматически назначать чат по ключевым словам?"),
                    ("outgoing", "Да, например, слова «оплата» и «возврат» отправлять в биллинг, а «доставка» — в логистику."),
                    ("incoming", "А если клиент пишет сразу про оплату и доставку?"),
                    ("outgoing", "Сработает приоритет правила биллинга, а менеджер сможет переназначить чат вручную."),
                    ("incoming", "Нужно показывать новые чаты отдельным списком."),
                    ("outgoing", "В demo это уже видно по статусу «Новый» и счётчику непрочитанных сообщений."),
                    ("incoming", "Как проверить, что уведомления не теряются?"),
                    ("outgoing", "Создайте тестовое обращение, затем проверьте событие в журнале и изменение статуса доставки."),
                    ("incoming", "Можно ли закрыть чат и потом снова открыть его?"),
                    ("outgoing", "Да, закрытие не удаляет историю, новый ответ вернёт обращение в активную работу."),
                    ("incoming", "Есть ли отчёт по времени первого ответа?"),
                    ("outgoing", "В текущем demo показываем историю и статусы, а метрику SLA добавим отдельным экраном."),
                    ("incoming", "Поняла. Какие данные нужны для запуска в production?"),
                    ("outgoing", "Понадобятся bot token, webhook secret, домен и отдельная база. Demo эти данные намеренно не использует."),
                    ("incoming", "Хорошо, сначала покажу команде этот интерфейс."),
                    ("outgoing", "Отлично. В demo можно спокойно просмотреть сценарии без подключения реальных клиентов."),
                    ("incoming", "Тогда вернусь с комментариями по ролям."),
                ],
            },
        ]

        for row in seed_rows:
            contact, _ = MaxContact.objects.update_or_create(
                max_user_id=row["user_id"],
                defaults={
                    "username": row["username"],
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "last_activity_time": now,
                    "last_seen_at": now,
                    "raw_user": {
                        "user_id": row["user_id"],
                        "username": row["username"],
                    },
                },
            )
            conversation, _ = Conversation.objects.update_or_create(
                contact=contact,
                max_chat_id=row["chat_id"],
                defaults={
                    "recipient_type": Conversation.RecipientType.USER,
                    "status": row["status"],
                    "assigned_to": user if row["user_id"] == "demo-1001" else None,
                    "unread_count": row["unread"],
                },
            )
            conversation.messages.all().delete()

            last_message = None
            message_count = len(row["messages"])
            for index, (kind, text) in enumerate(row["messages"], start=1):
                minutes_offset = (index - message_count - 1) * 3
                created_at = now + timedelta(minutes=minutes_offset)
                if kind == "incoming":
                    message = Message.objects.create(
                        conversation=conversation,
                        contact=contact,
                        direction=Message.Direction.INCOMING,
                        sender_kind=Message.SenderKind.MAX_USER,
                        max_sender_user_id=contact.max_user_id,
                        max_message_id=f"{row['user_id']}-{index}",
                        external_event_key=f"demo:{row['user_id']}:{index}",
                        text=text,
                        provider_created_at=created_at,
                        received_at=created_at,
                    )
                else:
                    send_status = Message.SendStatus.FAILED if kind == "failed" else Message.SendStatus.SENT
                    message = Message.objects.create(
                        conversation=conversation,
                        contact=contact,
                        direction=Message.Direction.OUTGOING,
                        sender_kind=Message.SenderKind.MANAGER,
                        manager=user,
                        text=text,
                        send_status=send_status,
                        provider_created_at=created_at,
                        sent_at=created_at if send_status == Message.SendStatus.SENT else None,
                        last_error_code="preview_failed" if send_status == Message.SendStatus.FAILED else "",
                        last_error_text="Demo failed delivery for retry button preview."
                        if send_status == Message.SendStatus.FAILED
                        else "",
                    )
                message.created_at = created_at
                message.save(update_fields=["created_at"])
                last_message = message

            if last_message is not None:
                conversation.last_message = last_message
                conversation.last_message_at = last_message.provider_created_at or last_message.created_at
                conversation.save(update_fields=["last_message", "last_message_at", "updated_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready for {username}. Password is configured separately. "
                "Open the configured demo URL to review the chats."
            )
        )
