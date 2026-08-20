from __future__ import annotations

import json
import logging
from hmac import compare_digest

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from support.services.ingest import ingest_max_update

logger = logging.getLogger("support.webhook")


def _demo_webhook_rate_limited(request: HttpRequest) -> bool:
    if not settings.DEMO_LOGIN_HINTS:
        return False

    client_ip = request.headers.get("X-Real-IP") or request.META.get("REMOTE_ADDR", "unknown")
    cache_key = f"demo-max-webhook:{client_ip}"
    if cache.add(cache_key, 1, timeout=settings.DEMO_WEBHOOK_RATE_WINDOW):
        return False

    count = cache.incr(cache_key)
    return count > settings.DEMO_WEBHOOK_RATE_LIMIT


@csrf_exempt
@require_POST
def max_webhook(request: HttpRequest) -> JsonResponse:
    if _demo_webhook_rate_limited(request):
        logger.warning("max_webhook_rate_limited")
        return JsonResponse(
            {"ok": False, "error": "rate_limited"},
            status=429,
            headers={"Retry-After": str(settings.DEMO_WEBHOOK_RATE_WINDOW)},
        )

    expected_secret = settings.MAX_WEBHOOK_SECRET
    received_secret = request.headers.get("X-Max-Bot-Api-Secret", "")
    if not expected_secret:
        logger.warning("max_webhook_forbidden reason=secret_not_configured")
        return JsonResponse({"ok": False}, status=403)
    if not compare_digest(received_secret, expected_secret):
        logger.warning("max_webhook_forbidden reason=secret_mismatch")
        return JsonResponse({"ok": False}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("max_webhook_bad_json")
        return JsonResponse({"ok": False, "error": "bad_json"}, status=400)

    if not isinstance(payload, dict):
        logger.warning("max_webhook_bad_payload")
        return JsonResponse({"ok": False, "error": "bad_payload"}, status=400)

    result = ingest_max_update(payload, headers=dict(request.headers))
    return JsonResponse({"ok": True, "duplicate": result.duplicate})
