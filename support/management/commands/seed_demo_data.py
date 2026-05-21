from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
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
                "is_superuser": True,
            },
        )
        if created or not user.has_usable_password():
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["password", "is_staff", "is_superuser"])

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
                    ("incoming", "Здравствуйте, хочу уточнить статус заказа.", -20),
                    ("outgoing", "Здравствуйте. Сейчас проверю и вернусь с ответом.", -16),
                    ("incoming", "Спасибо, буду ждать.", -12),
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
                    ("incoming", "Не получается открыть вложение в сообщении.", -35),
                    ("outgoing", "Поняла. Пришлите, пожалуйста, скрин ошибки.", -30),
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
                    ("incoming", "Можно повторить последнее сообщение?", -50),
                    ("failed", "Повторяю: ваш запрос уже в работе.", -45),
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
            for index, (kind, text, minutes_offset) in enumerate(row["messages"], start=1):
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
                        sent_at=created_at if send_status == Message.SendStatus.SENT else None,
                        last_error_code="preview_failed" if send_status == Message.SendStatus.FAILED else "",
                        last_error_text="Demo failed delivery for retry button preview."
                        if send_status == Message.SendStatus.FAILED
                        else "",
                    )
                last_message = message

            if last_message is not None:
                conversation.last_message = last_message
                conversation.last_message_at = last_message.provider_created_at or last_message.created_at
                conversation.save(update_fields=["last_message", "last_message_at", "updated_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready. Login: {username} / {password}. "
                "Open http://127.0.0.1:8066/admin/support/chats/"
            )
        )
