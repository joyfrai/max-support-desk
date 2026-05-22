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

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        timeout: float = 30.0,
    ) -> dict:
        self._rate_limit()
        response = httpx.request(
            method,
            f"{MAX_BASE_URL}{path}",
            headers={"Authorization": self.token, "Content-Type": "application/json"},
            params=params,
            json=json,
            timeout=timeout,
        )
        if response.status_code >= 400:
            raise MaxApiError(response.status_code, response.text)
        return response.json() if response.content else {}

    def upload_media(self, *, kind: str, data: bytes, filename: str, content_type: str) -> dict:
        meta = self._request("POST", "/uploads", params={"type": kind})
        upload_url = meta.get("url")
        upload_token = meta.get("token")
        if not upload_url or not upload_token:
            raise ValueError("MAX upload response does not include url/token")

        self._rate_limit()
        response = httpx.post(
            upload_url,
            headers={"Authorization": upload_token},
            files={"data": (filename, data, content_type or "application/octet-stream")},
            timeout=120.0,
        )
        if response.status_code >= 400:
            raise MaxApiError(response.status_code, response.text)

        upload_payload = response.json() if response.content else {}
        if kind in {"image", "file"}:
            return {"type": kind, "payload": upload_payload}
        return {"type": kind, "payload": {"token": upload_token}}

    def send_message(self, *, chat_id: str, text: str, attachments: list[dict] | None = None) -> dict:
        payload: dict[str, Any] = {"text": text, "format": "html"}
        if attachments:
            payload["attachments"] = attachments
        return self._request(
            "POST",
            "/messages",
            params={"chat_id": chat_id},
            json=payload,
        )
