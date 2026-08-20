import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from support.routing import websocket_urlpatterns


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "max_support_desk.settings")

django_asgi_app = get_asgi_application()


class ScriptNameWebSocketMiddleware:
    """Strip the reverse-proxy script prefix before Channels route matching."""

    def __init__(self, inner):
        self.inner = inner
        self.prefix = (os.getenv("DJANGO_FORCE_SCRIPT_NAME") or "").rstrip("/")

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket" and self.prefix:
            path = scope.get("path", "")
            if path == self.prefix or path.startswith(f"{self.prefix}/"):
                scope = dict(scope)
                scope["path"] = path[len(self.prefix) :] or "/"
                raw_path = scope.get("raw_path")
                if raw_path:
                    scope["raw_path"] = raw_path[len(self.prefix.encode("utf-8")) :] or b"/"
        return await self.inner(scope, receive, send)


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": ScriptNameWebSocketMiddleware(AuthMiddlewareStack(URLRouter(websocket_urlpatterns))),
    }
)
