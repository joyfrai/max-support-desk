from __future__ import annotations

import json
import logging
from hmac import compare_digest

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from support.services.ingest import ingest_max_update

logger = logging.getLogger("support.webhook")


@csrf_exempt
@require_POST
def max_webhook(request: HttpRequest) -> JsonResponse:
    expected_secret = settings.MAX_WEBHOOK_SECRET
    received_secret = request.headers.get("X-Max-Bot-Api-Secret", "")
    if expected_secret and not compare_digest(received_secret, expected_secret):
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
