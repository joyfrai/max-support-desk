from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger("support.max_client")

MAX_BASE_URL = "https://platform-api.max.ru"
MAX_RPS = 30


class MaxApiError(Exception):
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"MAX API error {status_code}")


class MaxClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token if token is not None else settings.MAX_BOT_TOKEN
        self._last_request_at = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        min_interval = 1.0 / MAX_RPS
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def send_message(self, *, chat_id: str, text: str) -> dict:
        self._rate_limit()
        response = httpx.post(
            f"{MAX_BASE_URL}/messages",
            headers={"Authorization": self.token, "Content-Type": "application/json"},
            params={"chat_id": chat_id},
            json={"text": text, "format": "html"},
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise MaxApiError(response.status_code, response.text)
        return response.json() if response.content else {}

