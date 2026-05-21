from django.urls import path

from support.consumers import SupportEventsConsumer


websocket_urlpatterns = [
    path("ws/support/", SupportEventsConsumer.as_asgi()),
]

