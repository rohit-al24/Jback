from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import MasterPayments, SubscriptionPlan, payments_enabled


def master_payments(request: HttpRequest) -> JsonResponse:
    """GET: returns the global payments enable flag.
    POST (staff only): toggles the flag or sets it explicitly via body {"enabled": bool}"""
    if request.method == "POST":
        if not request.user.is_authenticated or not request.user.is_staff:
            return JsonResponse({"error": "Forbidden"}, status=403)
        import json
        try:
            body = json.loads(request.body or "{}")
        except ValueError:
            body = {}
        obj, _ = MasterPayments.objects.get_or_create(id=1)
        if "enabled" in body:
            obj.enabled = bool(body["enabled"])
        else:
            obj.enabled = not obj.enabled
        obj.save()
        return JsonResponse({"enabled": obj.enabled})
    return JsonResponse({"enabled": payments_enabled()})


def subscription_plans(request: HttpRequest) -> JsonResponse:
    """Return active subscription plans for the frontend."""
    plans = SubscriptionPlan.objects.filter(is_active=True).values(
        "id", "name", "price_inr", "duration_days", "description"
    )
    return JsonResponse({"plans": list(plans)})
