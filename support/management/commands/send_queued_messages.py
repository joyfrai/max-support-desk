from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from support.services.outbound import process_next_queued_message


class Command(BaseCommand):
    help = "Send queued outgoing support messages to MAX."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--once", action="store_true", help="Process one available message and exit.")
        parser.add_argument("--sleep", type=float, default=1.0, help="Sleep interval when queue is empty.")

    def handle(self, *args, **options) -> None:
        once = options["once"]
        sleep_seconds = options["sleep"]
        while True:
            processed = process_next_queued_message()
            if once:
                return
            if processed is None:
                time.sleep(sleep_seconds)
