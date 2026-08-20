from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from django.urls import reverse_lazy


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CROSS_ORIGIN_OPENER_POLICY = os.getenv("DJANGO_CROSS_ORIGIN_OPENER_POLICY", "same-origin") or None
FORCE_SCRIPT_NAME = os.getenv("DJANGO_FORCE_SCRIPT_NAME") or None
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT")
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE")
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE")

MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN", "")
MAX_WEBHOOK_SECRET = os.getenv("MAX_WEBHOOK_SECRET", "")
MAX_NOTIFICATION_CHAT_ID = os.getenv("MAX_NOTIFICATION_CHAT_ID", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_NOTIFICATION_CHAT_ID = os.getenv("TELEGRAM_NOTIFICATION_CHAT_ID", "")
SUPPORT_DESK_PUBLIC_URL = os.getenv("SUPPORT_DESK_PUBLIC_URL", "")
SUPPORT_EXTERNAL_API_TOKEN = os.getenv("SUPPORT_EXTERNAL_API_TOKEN", "")
AUDIT_LOG_RETENTION_DAYS = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "7"))
DEMO_LOGIN_HINTS = env_bool("DEMO_LOGIN_HINTS")
DEMO_LOGIN_USERNAME = os.getenv("DEMO_LOGIN_USERNAME", "")
DEMO_LOGIN_PASSWORD = os.getenv("DEMO_LOGIN_PASSWORD", "")

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "support",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "max_support_desk.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "max_support_desk.context_processors.demo_login",
            ],
        },
    },
]

WSGI_APPLICATION = "max_support_desk.wsgi.application"
ASGI_APPLICATION = "max_support_desk.asgi.application"


def database_from_url(database_url: str) -> dict[str, object]:
    parsed = urlparse(database_url)
    query = dict(parse_qsl(parsed.query))
    if parsed.scheme in {"mysql", "mysql2"}:
        engine = "django.db.backends.mysql"
    elif parsed.scheme in {"sqlite", "sqlite3"}:
        engine = "django.db.backends.sqlite3"
    else:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")

    if engine == "django.db.backends.sqlite3":
        name = parsed.path.lstrip("/") or str(BASE_DIR / "db.sqlite3")
        if name == ":memory:":
            return {"ENGINE": engine, "NAME": name}
        return {"ENGINE": engine, "NAME": "/" + name if parsed.path.startswith("/") else name}

    return {
        "ENGINE": engine,
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "OPTIONS": query,
    }


def default_database() -> dict[str, object]:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_from_url(database_url)

    mysql_database = os.getenv("MYSQL_DATABASE")
    if mysql_database:
        return {
            "ENGINE": "django.db.backends.mysql",
            "NAME": mysql_database,
            "USER": os.getenv("MYSQL_USER", ""),
            "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
            "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
            "PORT": os.getenv("MYSQL_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }

    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }


DATABASES = {"default": default_database()}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = f"{FORCE_SCRIPT_NAME.rstrip('/')}/static/" if FORCE_SCRIPT_NAME else "/static/"
STATIC_ROOT = Path(os.getenv("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [BASE_DIR / "static"]
if (BASE_DIR / "frontend" / "dist").exists():
    STATICFILES_DIRS.append(BASE_DIR / "frontend" / "dist")

MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "admin:login"
LOGIN_REDIRECT_URL = f"{FORCE_SCRIPT_NAME.rstrip('/')}/admin/" if FORCE_SCRIPT_NAME else "/admin/"
LOGOUT_REDIRECT_URL = f"{FORCE_SCRIPT_NAME.rstrip('/')}/admin/login/" if FORCE_SCRIPT_NAME else "/admin/login/"

REDIS_URL = os.getenv("REDIS_URL", "")


def channel_layers_from_env(redis_url: str | None = None) -> dict[str, dict[str, object]]:
    configured_redis_url = REDIS_URL if redis_url is None else redis_url
    if configured_redis_url:
        return {
            "default": {
                "BACKEND": "channels_redis.core.RedisChannelLayer",
                "CONFIG": {
                    "hosts": [configured_redis_url],
                },
            },
        }

    return {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }


CHANNEL_LAYERS = channel_layers_from_env()

UNFOLD = {
    "SITE_TITLE": "MAX Help Desk",
    "SITE_HEADER": "MAX Help Desk",
    "SITE_ICON": f"{STATIC_URL}max-help-desk-mark.svg",
    "SITE_URL": None,
    "THEME": None,
    "COLORS": {
        "primary": {
            "50": "#edf4ff",
            "100": "#dbe8ff",
            "200": "#bfd4ff",
            "300": "#94b5ff",
            "400": "#5f8fff",
            "500": "#2f6fff",
            "600": "#0b5cff",
            "700": "#0848ca",
            "800": "#06389e",
            "900": "#052d7c",
            "950": "#031d52",
        },
    },
    "STYLES": [
        f"{STATIC_URL}admin-mobile-overrides.css",
        f"{STATIC_URL}admin-brand.css",
    ],
    "SCRIPTS": [f"{STATIC_URL}admin-theme-default.js"],
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Поддержка",
                "separator": True,
                "items": [
                    {
                        "title": "Пользователи MAX",
                        "icon": "group",
                        "link": reverse_lazy("admin:support_maxcontact_changelist"),
                    },
                    {
                        "title": "Чаты",
                        "icon": "forum",
                        "link": reverse_lazy("admin_support_chats"),
                    },
                ],
            },
        ],
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": "ts=%(asctime)s level=%(levelname)s logger=%(name)s event=%(message)s",
        },
    },
    "filters": {
        "redact_secrets": {
            "()": "support.logging_filters.SecretRedactingFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
            "filters": ["redact_secrets"],
        },
    },
    "loggers": {
        "support": {
            "handlers": ["console"],
            "level": os.getenv("SUPPORT_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "httpx": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "httpcore": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
