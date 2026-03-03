from __future__ import annotations

from django.http import HttpRequest, JsonResponse

from .models import payments_enabled


def master_payments(request: HttpRequest) -> JsonResponse:
    """Public endpoint for frontend: returns the global payments enable flag."""
    return JsonResponse({"enabled": payments_enabled()})
