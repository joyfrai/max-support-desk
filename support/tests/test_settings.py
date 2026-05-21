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
