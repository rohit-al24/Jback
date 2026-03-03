from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid

import requests as http_requests

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .decorators import api_login_required
from .models import User

try:
    from payments.models import payments_enabled as _payments_enabled
except Exception:  # pragma: no cover
    def _payments_enabled() -> bool:  # type: ignore[no-redef]
        return True

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _cashfree_base() -> str:
    if getattr(settings, "CASHFREE_ENV", "TEST") == "PRODUCTION":
        return "https://api.cashfree.com/pg"
    return "https://sandbox.cashfree.com/pg"


def _cashfree_headers() -> dict:
    return {
        "x-client-id":     settings.CASHFREE_APP_ID,
        "x-client-secret": settings.CASHFREE_SECRET_KEY,
        "x-api-version":   "2023-08-01",
        "Content-Type":    "application/json",
    }


# The single plan available for testing
PLAN_50 = {
    "id":           1,
    "code":         "monthly_2",
    "display_name": "Monthly Plan",
    "price_paise":  200,       # ₹2 in paise
    "price_rs":     2,
    "duration_days": 30,
}


# ─── API views ────────────────────────────────────────────────────────────────

@api_login_required
def plans(request: HttpRequest) -> JsonResponse:
    """Return available plans. Currently only the ₹50 monthly plan."""
    return JsonResponse({"plans": [PLAN_50]})


@api_login_required
def cashfree_create_order(request: HttpRequest) -> JsonResponse:
    """Create a Cashfree order and return the payment_link for redirect.

    POST body: { plan_id: 1 }  (only plan_id=1 is valid for now)
    """
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)

    if not _payments_enabled():
        return JsonResponse({"detail": "Payments are disabled"}, status=503)

    if not getattr(settings, "CASHFREE_APP_ID", ""):
        return JsonResponse(
            {"detail": "CASHFREE_APP_ID not configured — add it to settings/env"},
            status=501,
        )

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    plan_id = body.get("plan_id")
    if str(plan_id) != "1":
        return JsonResponse({"detail": "Invalid plan"}, status=400)

    user: User = request.user   # type: ignore[assignment]

    order_id = f"bengo_{user.pk}_{uuid.uuid4().hex[:10]}"

    payload = {
        "order_id":       order_id,
        "order_amount":   PLAN_50["price_rs"],
        "order_currency": "INR",
        "customer_details": {
            "customer_id":    f"user_{user.pk}",
            "customer_name":  user.get_full_name() or user.username,
            "customer_email": user.email or "noemail@bengo.app",
            "customer_phone": "9999999999",   # Cashfree requires this field
        },
        "order_meta": {
            "return_url": (
                getattr(settings, "CASHFREE_RETURN_URL",
                        "http://localhost:5173/app/shop?result=1")
                + f"&order_id={order_id}&user_id={user.pk}"
            ),
            "notify_url": "",  # webhook is set via Cashfree dashboard
        },
        "order_tags": {
            "user_id":   str(user.pk),
            "plan_code": PLAN_50["code"],
        },
    }

    try:
        resp = http_requests.post(
            f"{_cashfree_base()}/orders",
            headers=_cashfree_headers(),
            json=payload,
            timeout=10,
        )
        data = resp.json()
    except Exception as exc:
        return JsonResponse({"detail": f"Cashfree API error: {exc}"}, status=502)

    if resp.status_code not in (200, 201):
        msg = data.get("message") or data.get("detail") or resp.text[:200]
        return JsonResponse({"detail": f"Cashfree: {msg}"}, status=400)

    payment_link = data.get("payment_link") or data.get("payment_link_url", "")
    cf_order_id  = data.get("cf_order_id", "")
    session_id   = data.get("payment_session_id", "")

    # Cashfree /pg/orders returns payment_session_id, not a payment_link by default.
    # Build the hosted-checkout redirect URL when payment_link is absent.
    if not payment_link and session_id:
        env = getattr(settings, "CASHFREE_ENV", "TEST")
        if env == "PRODUCTION":
            payment_link = f"https://payments.cashfree.com/forms/view?id={session_id}"
        else:
            payment_link = f"https://sandbox.cashfree.com/forms/view?id={session_id}"

    return JsonResponse({
        "payment_link":        payment_link,
        "payment_session_id":  session_id,
        "cf_order_id":         cf_order_id,
        "order_id":            order_id,
    })


@csrf_exempt
def cashfree_webhook(request: HttpRequest) -> JsonResponse:
    """Cashfree sends a signed POST here on PAYMENT_SUCCESS.

    Verify signature → activate subscription.
    """
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)

    raw_body = request.body.decode("utf-8")

    # ── Signature verification ────────────────────────────────────────────────
    cf_signature  = request.headers.get("x-webhook-signature", "")
    cf_timestamp  = request.headers.get("x-webhook-timestamp", "")
    webhook_secret = getattr(settings, "CASHFREE_WEBHOOK_SECRET", "")

    if webhook_secret and cf_signature and cf_timestamp:
        sign_str   = cf_timestamp + raw_body
        expected   = hmac.new(
            webhook_secret.encode(),
            sign_str.encode(),
            hashlib.sha256,
        ).digest()
        expected_b64 = base64.b64encode(expected).decode()
        if not hmac.compare_digest(cf_signature, expected_b64):
            return JsonResponse({"detail": "Invalid signature"}, status=403)

    try:
        payload = json.loads(raw_body)
    except Exception:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    event_type = payload.get("type", "")
    data       = payload.get("data", {})
    order      = data.get("order", {})
    payment    = data.get("payment", {})

    # We only care about successful payments
    if event_type not in ("PAYMENT_SUCCESS", "PAYMENT_SUCCESS_WEBHOOK") and \
       payment.get("payment_status") != "SUCCESS":
        return JsonResponse({"status": "ignored"})

    tags = order.get("order_tags") or {}
    user_id = tags.get("user_id") or (order.get("order_id", "").split("_")[1] if "_" in order.get("order_id", "") else None)

    if not user_id:
        return JsonResponse({"detail": "user_id missing"}, status=400)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({"detail": "user not found"}, status=404)

    # Activate subscription for 30 days
    user.subscription_status = User.SubscriptionStatus.PAID  # type: ignore[attr-defined]
    user.save(update_fields=["subscription_status"])

    return JsonResponse({"status": "ok"})


@api_login_required
def cashfree_verify(request: HttpRequest) -> JsonResponse:
    """Called by frontend after redirect from Cashfree to verify payment status.

    GET ?order_id=bengo_xxx
    """
    order_id = (request.GET.get("order_id") or "").strip()
    if not order_id:
        return JsonResponse({"detail": "order_id required"}, status=400)

    if not getattr(settings, "CASHFREE_APP_ID", ""):
        return JsonResponse({"paid": False, "detail": "Cashfree not configured"})

    if not _payments_enabled():
        return JsonResponse({"paid": False, "detail": "Payments are disabled"})

    try:
        resp = http_requests.get(
            f"{_cashfree_base()}/orders/{order_id}",
            headers=_cashfree_headers(),
            timeout=8,
        )
        data = resp.json()
    except Exception as exc:
        return JsonResponse({"detail": str(exc)}, status=502)

    order_status = data.get("order_status", "")
    paid = order_status == "PAID"

    if paid:
        user: User = request.user  # type: ignore[assignment]
        if user.subscription_status != User.SubscriptionStatus.PAID:  # type: ignore[attr-defined]
            user.subscription_status = User.SubscriptionStatus.PAID   # type: ignore[attr-defined]
            user.save(update_fields=["subscription_status"])

    return JsonResponse({
        "order_status": order_status,
        "paid": paid,
    })


# keep old stub so existing URL still resolves
@api_login_required
def create_checkout_session(request: HttpRequest) -> JsonResponse:
    return JsonResponse({
        "detail": "This app now uses Cashfree. Call /api/billing/cashfree-order/ instead."
    }, status=501)
