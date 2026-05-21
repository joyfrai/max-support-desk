from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from support.models import DeliveryAttempt, ManagerActionLog


class Command(BaseCommand):
    help = "Delete support audit and delivery diagnostic logs older than retention window."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=settings.AUDIT_LOG_RETENTION_DAYS,
            help="Retention window in days. Defaults to AUDIT_LOG_RETENTION_DAYS.",
        )

    def handle(self, *args, **options) -> None:
        days = int(options["days"])
        cutoff = timezone.now() - timedelta(days=days)
        actions_deleted, _ = ManagerActionLog.objects.filter(created_at__lt=cutoff).delete()
        attempts_deleted, _ = DeliveryAttempt.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {actions_deleted} manager action logs and {attempts_deleted} delivery attempts."
            )
        )
