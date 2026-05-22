from __future__ import annotations

from dataclasses import dataclass

from support.max_client import MaxClient


@dataclass
class FakeResponse:
    status_code: int
    payload: dict | None = None
    text: str = ""

    @property
    def content(self) -> bytes:
        return b"{}" if self.payload is not None else b""

    def json(self) -> dict:
        return self.payload or {}


def test_upload_media_file_uses_upload_response_payload_and_bot_token(monkeypatch) -> None:
    request_calls: list[dict] = []
    post_calls: list[dict] = []

    def fake_request(method, url, *, headers, params, json, timeout):
        request_calls.append(
            {"method": method, "url": url, "headers": headers, "params": params, "json": json, "timeout": timeout}
        )
        return FakeResponse(200, {"url": "https://fu.oneme.ru/upload.do?token=from-url"})

    def fake_post(url, *, headers, files, timeout):
        post_calls.append({"url": url, "headers": headers, "files": files, "timeout": timeout})
        return FakeResponse(200, {"token": "uploaded-file-token"})

    monkeypatch.setattr("support.max_client.httpx.request", fake_request)
    monkeypatch.setattr("support.max_client.httpx.post", fake_post)

    attachment = MaxClient(token="bot-token").upload_media(
        kind="file",
        data=b"report",
        filename="report.txt",
        content_type="text/plain",
    )

    assert request_calls[0]["params"] == {"type": "file"}
    assert post_calls[0]["headers"] == {"Authorization": "bot-token"}
    assert post_calls[0]["files"]["data"] == ("report.txt", b"report", "text/plain")
    assert attachment == {"type": "file", "payload": {"token": "uploaded-file-token"}}


def test_upload_media_video_uses_token_from_upload_url_response(monkeypatch) -> None:
    def fake_request(method, url, *, headers, params, json, timeout):
        return FakeResponse(200, {"url": "https://vu.okcdn.ru/upload.do", "token": "video-upload-token"})

    def fake_post(url, *, headers, files, timeout):
        return FakeResponse(200, {"retval": 1})

    monkeypatch.setattr("support.max_client.httpx.request", fake_request)
    monkeypatch.setattr("support.max_client.httpx.post", fake_post)

    attachment = MaxClient(token="bot-token").upload_media(
        kind="video",
        data=b"movie",
        filename="movie.mp4",
        content_type="video/mp4",
    )

    assert attachment == {"type": "video", "payload": {"token": "video-upload-token"}}
