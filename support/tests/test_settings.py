from max_support_desk import settings as project_settings
from max_support_desk.context_processors import demo_login
from django.test import RequestFactory, override_settings


def test_channel_layer_uses_memory_without_redis_url() -> None:
    assert (
        project_settings.channel_layers_from_env(redis_url="")["default"]["BACKEND"]
        == "channels.layers.InMemoryChannelLayer"
    )


def test_channel_layer_uses_redis_when_redis_url_is_set() -> None:
    layer = project_settings.channel_layers_from_env(redis_url="redis://redis:6379/0")["default"]
    assert layer["BACKEND"] == "channels_redis.core.RedisChannelLayer"
    assert layer["CONFIG"] == {"hosts": ["redis://redis:6379/0"]}


def test_unfold_uses_theme_switch_with_light_default_script_and_hides_site_link() -> None:
    assert project_settings.UNFOLD["THEME"] is None
    assert "/static/admin-mobile-overrides.css" in project_settings.UNFOLD["STYLES"]
    assert "/static/admin-brand.css" in project_settings.UNFOLD["STYLES"]
    assert "/static/admin-theme-default.js" in project_settings.UNFOLD["SCRIPTS"]
    assert project_settings.UNFOLD["SITE_ICON"].endswith("/static/max-help-desk-mark.svg")
    assert project_settings.UNFOLD["COLORS"]["primary"]["600"] == "#0b5cff"
    assert project_settings.UNFOLD["SITE_URL"] is None


def test_cross_origin_opener_policy_is_configurable() -> None:
    assert hasattr(project_settings, "SECURE_CROSS_ORIGIN_OPENER_POLICY")


def test_secure_cookie_settings_are_configurable() -> None:
    assert hasattr(project_settings, "SECURE_SSL_REDIRECT")
    assert hasattr(project_settings, "SESSION_COOKIE_SECURE")
    assert hasattr(project_settings, "CSRF_COOKIE_SECURE")


def test_notification_settings_are_defined() -> None:
    assert hasattr(project_settings, "TELEGRAM_BOT_TOKEN")
    assert hasattr(project_settings, "TELEGRAM_NOTIFICATION_CHAT_ID")
    assert hasattr(project_settings, "MAX_NOTIFICATION_CHAT_ID")
    assert hasattr(project_settings, "SUPPORT_DESK_PUBLIC_URL")
    assert hasattr(project_settings, "SUPPORT_EXTERNAL_API_TOKEN")


def test_demo_login_context_is_disabled_by_default() -> None:
    request = RequestFactory().get("/admin/login/")

    with override_settings(
        DEMO_LOGIN_HINTS=False,
        DEMO_LOGIN_USERNAME="demo-admin",
        DEMO_LOGIN_PASSWORD="demo-pass-123",
    ):
        assert demo_login(request) == {"demo_login": None}


def test_demo_login_context_exposes_configured_demo_credentials() -> None:
    request = RequestFactory().get("/admin/login/")

    with override_settings(
        DEMO_LOGIN_HINTS=True,
        DEMO_LOGIN_USERNAME="demo-admin",
        DEMO_LOGIN_PASSWORD="demo-pass-123",
    ):
        assert demo_login(request) == {
            "demo_login": {
                "username": "demo-admin",
                "password": "demo-pass-123",
            }
        }
