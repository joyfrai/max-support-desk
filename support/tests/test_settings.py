from max_support_desk import settings as project_settings


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
    assert "/static/admin-theme-default.js" in project_settings.UNFOLD["SCRIPTS"]
    assert project_settings.UNFOLD["SITE_URL"] is None


def test_cross_origin_opener_policy_is_configurable() -> None:
    assert hasattr(project_settings, "SECURE_CROSS_ORIGIN_OPENER_POLICY")
