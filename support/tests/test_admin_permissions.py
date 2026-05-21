from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
import pytest

from support.admin import MaxContactAdmin
from support.models import MaxContact


@pytest.mark.django_db
def test_max_contact_admin_is_view_only() -> None:
    request = RequestFactory().get("/admin/support/maxcontact/")
    request.user = get_user_model().objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="secret",
    )
    contact = MaxContact.objects.create(max_user_id="1001", first_name="Иван", last_name="Петров")
    model_admin = MaxContactAdmin(MaxContact, AdminSite())

    assert model_admin.has_view_permission(request, contact)
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request, contact)
    assert not model_admin.has_delete_permission(request, contact)
