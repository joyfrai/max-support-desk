from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.fixture
def user_factory(db):
    def create_user(username: str, *, is_staff: bool):
        return get_user_model().objects.create_user(
            username=username,
            password="secret",
            is_staff=is_staff,
        )

    return create_user


def test_support_short_url_redirects_to_admin_chats(client) -> None:
    response = client.get("/support/")

    assert response.status_code == 302
    assert response["Location"] == reverse("admin_support_chats")


def test_favicon_redirects_to_static_asset(client) -> None:
    response = client.get("/favicon.ico")

    assert response.status_code == 301
    assert response["Location"] == "/static/favicon.ico"


def test_chats_admin_page_requires_login(client) -> None:
    response = client.get(reverse("admin_support_chats"))

    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_chats_admin_page_rejects_non_staff(client, user_factory) -> None:
    user = user_factory("regular", is_staff=False)
    client.force_login(user)

    response = client.get(reverse("admin_support_chats"))

    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_chats_admin_page_allows_staff(client, user_factory) -> None:
    user = user_factory("staff", is_staff=True)
    client.force_login(user)

    response = client.get(reverse("admin_support_chats"))

    assert response.status_code == 200
    assert b"support-desk-root" in response.content
