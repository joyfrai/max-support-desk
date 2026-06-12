from __future__ import annotations

import logging
import time

from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import DatabaseError, OperationalError

from support.services.outbound import process_next_queued_message

logger = logging.getLogger("support.worker")


class Command(BaseCommand):
    help = "Send queued outgoing support messages to MAX."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--once", action="store_true", help="Process one available message and exit.")
        parser.add_argument("--sleep", type=float, default=1.0, help="Sleep interval when queue is empty.")
        parser.add_argument(
            "--db-retry-sleep",
            type=float,
            default=5.0,
            help="Sleep interval after a temporary database error.",
        )

    def handle(self, *args, **options) -> None:
        once = options["once"]
        sleep_seconds = options["sleep"]
        db_retry_sleep = options["db_retry_sleep"]
        while True:
            try:
                processed = process_next_queued_message()
            except OperationalError as exc:
                if once:
                    raise
                connections.close_all()
                logger.warning("worker_db_unavailable error=%s retry_in_seconds=%s", exc, db_retry_sleep)
                time.sleep(db_retry_sleep)
                continue
            except DatabaseError as exc:
                if once:
                    raise
                connections.close_all()
                logger.warning("worker_db_error error=%s retry_in_seconds=%s", exc, db_retry_sleep)
                time.sleep(db_retry_sleep)
                continue
            if once:
                return
            if processed is None:
                time.sleep(sleep_seconds)
