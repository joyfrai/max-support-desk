from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, DateTimeField, F, QuerySet, Value, When
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class MaxContact(TimestampedModel):
    max_user_id = models.CharField(max_length=128, unique=True)
    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    username = models.CharField(max_length=255, blank=True, db_index=True)
    is_bot = models.BooleanField(default=False)
    last_activity_time = models.DateTimeField(null=True, blank=True)
    legacy_name = models.CharField(max_length=255, blank=True)
    raw_user = models.JSONField(default=dict, blank=True)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_seen_at", "id"]
        verbose_name = "пользователь MAX"
        verbose_name_plural = "Пользователи MAX"

    def __str__(self) -> str:
        if self.username:
            return f"@{self.username}"
        display_name = " ".join(part for part in [self.first_name, self.last_name] if part)
        return display_name or f"MAX user {self.max_user_id}"


class Conversation(TimestampedModel):
    class RecipientType(models.TextChoices):
        USER = "user", "Пользователь"
        CHAT = "chat", "Чат"
        CHANNEL = "channel", "Канал"
        UNKNOWN = "unknown", "Неизвестно"

    class Status(models.TextChoices):
        NEW = "new", "Новый"
        OPEN = "open", "Открыт"
        PENDING = "pending", "Ожидает"
        CLOSED = "closed", "Закрыт"

    contact = models.ForeignKey(MaxContact, on_delete=models.PROTECT, related_name="conversations")
    max_chat_id = models.CharField(max_length=128, blank=True, db_index=True)
    recipient_type = models.CharField(
        max_length=16,
        choices=RecipientType.choices,
        default=RecipientType.USER,
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_conversations",
    )
    last_message = models.ForeignKey(
        "Message",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    last_message_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.PositiveIntegerField(default=0)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "last_message_at"]),
            models.Index(fields=["assigned_to", "status", "last_message_at"]),
            models.Index(fields=["contact", "status"]),
            models.Index(fields=["max_chat_id"]),
        ]
        ordering = ["-last_message_at", "-updated_at", "id"]
        verbose_name = "чат"
        verbose_name_plural = "Чаты"

    def __str__(self) -> str:
        return f"Conversation #{self.pk} with {self.contact}"


class RawUpdate(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Получено"
        PROCESSED = "processed", "Обработано"
        IGNORED = "ignored", "Проигнорировано"
        FAILED = "failed", "Ошибка"

    update_type = models.CharField(max_length=128, blank=True)
    max_timestamp = models.DateTimeField(null=True, blank=True)
    max_chat_id = models.CharField(max_length=128, blank=True)
    dedupe_key = models.CharField(max_length=255, unique=True)
    payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED)
    error_text = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at", "id"]
        verbose_name = "сырое событие MAX"
        verbose_name_plural = "Сырые события MAX"

    def __str__(self) -> str:
        return f"{self.update_type or 'update'}:{self.dedupe_key}"


class MessageQuerySet(QuerySet):
    def for_display(self) -> "MessageQuerySet":
        return self.annotate(
            display_created_at=Case(
                When(
                    direction=Message.Direction.INCOMING,
                    provider_created_at__isnull=False,
                    then=F("provider_created_at"),
                ),
                default=F("created_at"),
                output_field=DateTimeField(),
            ),
            display_missing_provider_at=Case(
                When(
                    direction=Message.Direction.INCOMING,
                    provider_created_at__isnull=True,
                    then=Value(1),
                ),
                default=Value(0),
                output_field=models.IntegerField(),
            ),
        ).order_by("display_created_at", "display_missing_provider_at", "id")


class Message(TimestampedModel):
    class Direction(models.TextChoices):
        INCOMING = "incoming", "Входящее"
        OUTGOING = "outgoing", "Исходящее"

    class SenderKind(models.TextChoices):
        MAX_USER = "max_user", "Пользователь MAX"
        MANAGER = "manager", "Менеджер"
        SYSTEM = "system", "Система"

    class TextFormat(models.TextChoices):
        PLAIN = "plain", "Обычный текст"
        HTML = "html", "HTML"
        MARKDOWN = "markdown", "Markdown"
        UNKNOWN = "unknown", "Неизвестно"

    class ContentType(models.TextChoices):
        TEXT = "text", "Текст"
        FILE = "file", "Файл"
        MIXED = "mixed", "Текст и файл"
        SERVICE = "service", "Сервисное"
        UNSUPPORTED = "unsupported", "Не поддерживается"

    class SendStatus(models.TextChoices):
        NOT_APPLICABLE = "not_applicable", "Не применяется"
        QUEUED = "queued", "В очереди"
        SENDING = "sending", "Отправляется"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    contact = models.ForeignKey(MaxContact, on_delete=models.PROTECT, related_name="messages")
    raw_update = models.ForeignKey(
        RawUpdate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="messages",
    )
    direction = models.CharField(max_length=16, choices=Direction.choices)
    sender_kind = models.CharField(max_length=16, choices=SenderKind.choices)
    max_sender_user_id = models.CharField(max_length=128, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_messages",
    )
    max_message_id = models.CharField(max_length=128, blank=True, db_index=True)
    external_event_key = models.CharField(max_length=255, blank=True, db_index=True)
    reply_to_message = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
    )
    text = models.TextField(blank=True)
    text_format = models.CharField(
        max_length=16,
        choices=TextFormat.choices,
        default=TextFormat.PLAIN,
    )
    content_type = models.CharField(
        max_length=16,
        choices=ContentType.choices,
        default=ContentType.TEXT,
    )
    raw_message = models.JSONField(default=dict, blank=True)
    send_status = models.CharField(
        max_length=24,
        choices=SendStatus.choices,
        default=SendStatus.NOT_APPLICABLE,
    )
    send_attempts = models.PositiveIntegerField(default=0)
    last_error_code = models.CharField(max_length=128, blank=True)
    last_error_text = models.TextField(blank=True)
    provider_created_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)

    objects = MessageQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["conversation", "id"]),
            models.Index(fields=["conversation", "provider_created_at", "id"]),
            models.Index(fields=["direction", "send_status", "id"]),
            models.Index(fields=["manager", "created_at"]),
            models.Index(fields=["contact", "created_at"]),
        ]
        ordering = ["id"]
        verbose_name = "сообщение"
        verbose_name_plural = "Сообщения"

    def clean(self) -> None:
        errors = {}
        if self.direction == self.Direction.OUTGOING:
            if self.sender_kind == self.SenderKind.MANAGER and self.manager_id is None:
                errors["manager"] = "Outgoing manager messages require manager_id."
            if self.send_status == self.SendStatus.NOT_APPLICABLE:
                errors["send_status"] = "Outgoing messages cannot use not_applicable send status."
        if self.direction == self.Direction.INCOMING and self.send_status != self.SendStatus.NOT_APPLICABLE:
            errors["send_status"] = "Incoming messages must use not_applicable send status."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        if self.direction == self.Direction.INCOMING:
            self.send_status = self.SendStatus.NOT_APPLICABLE
        super().save(*args, **kwargs)

    def mark_for_retry(self) -> None:
        if self.direction != self.Direction.OUTGOING:
            raise ValidationError("Only outgoing messages can be retried.")
        if self.send_status != self.SendStatus.FAILED:
            raise ValidationError("Only failed messages can be retried.")
        self.send_status = self.SendStatus.QUEUED
        self.last_error_code = ""
        self.last_error_text = ""
        self.save(update_fields=["send_status", "last_error_code", "last_error_text", "updated_at"])

    def __str__(self) -> str:
        return f"{self.direction} message #{self.pk}"


class MessageAttachment(models.Model):
    class AttachmentType(models.TextChoices):
        IMAGE = "image", "Изображение"
        VIDEO = "video", "Видео"
        AUDIO = "audio", "Аудио"
        FILE = "file", "Файл"
        INLINE_KEYBOARD = "inline_keyboard", "Кнопки"
        UNKNOWN = "unknown", "Неизвестно"

    class UploadStatus(models.TextChoices):
        NOT_NEEDED = "not_needed", "Не требуется"
        PENDING = "pending", "Ожидает"
        UPLOADED = "uploaded", "Загружено"
        READY = "ready", "Готово"
        FAILED = "failed", "Ошибка"

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="attachments")
    contact = models.ForeignKey(MaxContact, on_delete=models.PROTECT, related_name="attachments")
    direction = models.CharField(max_length=16, choices=Message.Direction.choices)
    sender_kind = models.CharField(max_length=16, choices=Message.SenderKind.choices)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_attachments",
    )
    attachment_type = models.CharField(
        max_length=32,
        choices=AttachmentType.choices,
        default=AttachmentType.UNKNOWN,
    )
    original_file_name = models.CharField(max_length=512, blank=True)
    stored_file = models.FileField(upload_to="support_attachments/%Y/%m/%d/", blank=True)
    mime_type = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    max_payload = models.JSONField(default=dict, blank=True)
    raw_attachment = models.JSONField(default=dict, blank=True)
    upload_status = models.CharField(
        max_length=24,
        choices=UploadStatus.choices,
        default=UploadStatus.NOT_NEEDED,
    )
    max_upload_token = models.CharField(max_length=512, blank=True)
    max_upload_url = models.URLField(blank=True)
    last_error_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["message"]),
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["upload_status", "created_at"]),
        ]
        ordering = ["id"]
        verbose_name = "вложение"
        verbose_name_plural = "Вложения"

    def __str__(self) -> str:
        return self.original_file_name or f"{self.attachment_type} attachment #{self.pk}"


class ManagerActionLog(models.Model):
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_action_logs",
    )
    conversation = models.ForeignKey(
        Conversation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="action_logs",
    )
    message = models.ForeignKey(
        Message,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="action_logs",
    )
    action = models.CharField(max_length=128)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "id"]
        verbose_name = "лог действия менеджера"
        verbose_name_plural = "Логи действий менеджеров"

    def __str__(self) -> str:
        return f"{self.action} by {self.manager_id or 'system'}"


class DeliveryAttempt(models.Model):
    class Status(models.TextChoices):
        STARTED = "started", "Начата"
        SUCCESS = "success", "Успешно"
        FAILED = "failed", "Ошибка"
        RETRY_SCHEDULED = "retry_scheduled", "Повтор запланирован"

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="delivery_attempts")
    attempt_no = models.PositiveIntegerField()
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.STARTED)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    http_status = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=128, blank=True)
    error_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = [("message", "attempt_no")]
        ordering = ["-created_at", "id"]
        verbose_name = "попытка доставки"
        verbose_name_plural = "Попытки доставки"

    def __str__(self) -> str:
        return f"attempt {self.attempt_no} for message {self.message_id}"
