from __future__ import annotations

import json

from django.conf import settings
from django.http import HttpRequest, JsonResponse

from .decorators import api_login_required
from .models import SubscriptionPlan, User


@api_login_required
def plans(request: HttpRequest) -> JsonResponse:
    items = list(
        SubscriptionPlan.objects.filter(is_active=True)
        .order_by("price_paise")
        .values("id", "code", "display_name", "price_paise", "duration_days")
    )
    return JsonResponse({"plans": items})


@api_login_required
def create_checkout_session(request: HttpRequest) -> JsonResponse:
    """Stripe Checkout stub.

    Returns 501 unless Stripe is configured (and stripe package is installed).
    """

    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)

    if not getattr(settings, "STRIPE_SECRET_KEY", ""):
        return JsonResponse({"detail": "Stripe not configured"}, status=501)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    plan_id = payload.get("plan_id")
    referral_code = (payload.get("referral_code") or "").strip().upper()
    plan = SubscriptionPlan.objects.filter(pk=plan_id, is_active=True).first()
    if plan is None:
        return JsonResponse({"detail": "Invalid plan"}, status=400)

    # Import lazily so dev can run without installing stripe.
    try:
        import stripe  # type: ignore
    except Exception:
        return JsonResponse({"detail": "stripe package not installed"}, status=501)

    user: User = request.user  # type: ignore[assignment]

    stripe.api_key = settings.STRIPE_SECRET_KEY

    if not plan.stripe_price_id:
        return JsonResponse({"detail": "Plan missing stripe_price_id"}, status=501)

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
        success_url=getattr(settings, "STRIPE_SUCCESS_URL"),
        cancel_url=getattr(settings, "STRIPE_CANCEL_URL"),
        client_reference_id=str(user.pk),
        metadata={
            "referral_code": referral_code,
            "user_id": str(user.pk),
            "plan_code": plan.code,
        },
    )

    return JsonResponse({"url": session.url})
