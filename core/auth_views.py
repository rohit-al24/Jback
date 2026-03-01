from __future__ import annotations

import json

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest, JsonResponse
from django.core import signing
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone

import pyotp


def _user_payload(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.get_full_name(),
        "first_name": getattr(user, 'first_name', ''),
        "last_name": getattr(user, 'last_name', ''),
        "email": getattr(user, 'email', ''),
        "target_level": getattr(user, "target_level", None),
        "total_points": getattr(user, "total_points", None),
        "subscription_status": getattr(user, "subscription_status", None),
        "streak_count": getattr(user, "streak_count", None),
        "referral_code": getattr(user, "referral_code", None),
    }


@ensure_csrf_cookie
def csrf(request: HttpRequest) -> JsonResponse:
    # Sets the CSRF cookie. Useful for SPA bootstrapping.
    return JsonResponse({"detail": "CSRF cookie set", "csrfToken": get_token(request)})


def me(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False})
    return JsonResponse({"authenticated": True, "user": _user_payload(request.user)})


def register_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    username = payload.get("username")
    password = payload.get("password")
    email = (payload.get("email") or "").strip() or None
    first_name = (payload.get("first_name") or "").strip() or None
    last_name = (payload.get("last_name") or "").strip() or None
    referral_code = (payload.get("referral_code") or "").strip().upper()
    target_level = payload.get("target_level")
    role = (payload.get("role") or "student").strip().lower()
    college_id = payload.get("college_id")

    if not username or not password:
        return JsonResponse({"detail": "username and password required"}, status=400)
    if not email:
        return JsonResponse({"detail": "email required"}, status=400)

    # Enforce email OTP verification before account creation.
    verified_email = (request.session.get("email_otp_verified_email") or "").strip().lower()
    verified_until = (request.session.get("email_otp_verified_until") or "").strip()
    if not verified_email or verified_email != (email or "").strip().lower():
        return JsonResponse({"detail": "Verify your email OTP before creating an account"}, status=400)
    if verified_until:
        try:
            until_dt = timezone.datetime.fromisoformat(verified_until)
            if timezone.is_naive(until_dt):
                until_dt = timezone.make_aware(until_dt)
            if timezone.now() > until_dt:
                return JsonResponse({"detail": "Email OTP verification expired. Please resend OTP."}, status=400)
        except Exception:
            return JsonResponse({"detail": "Email OTP verification expired. Please resend OTP."}, status=400)

    from .models import User

    if User.objects.filter(username=username).exists():
        return JsonResponse({"detail": "Username already exists"}, status=400)
    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"detail": "Email already registered"}, status=400)

    referred_by = None
    if referral_code:
        referred_by = User.objects.filter(referral_code=referral_code).first()

    user = User(username=username)
    if email:
        user.email = email
    if first_name:
        user.first_name = first_name
    if last_name:
        user.last_name = last_name
    if role in {r.value for r in User.Role}:
        user.role = role
    if college_id:
        try:
            from .models import College

            c = College.objects.filter(id=int(college_id)).first()
            if c:
                user.college = c
        except Exception:
            pass
    if target_level in {"N5", "N4"}:
        user.target_level = target_level
    user.referred_by = referred_by
    user.set_password(password)
    user.email_verified = True
    user.save()

    # Clear session flag after successful account creation.
    request.session.pop("email_otp_verified_email", None)
    request.session.pop("email_otp_verified_until", None)

    # Default new users to the "student" role.
    try:
        from django.contrib.auth.models import Group

        student_group, _ = Group.objects.get_or_create(name="student")
        user.groups.add(student_group)
    except Exception:
        # Don't block registration if the auth tables aren't ready yet.
        pass

    # Log the user in directly after account creation (TOTP setup removed)
    login(request, user)
    return JsonResponse({"authenticated": True, "user": _user_payload(user)})


def login_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    identifier = (payload.get("identifier") or payload.get("username"))
    password = payload.get("password")
    if not identifier or not password:
        return JsonResponse({"detail": "username/email and password required"}, status=400)

    username_for_auth = identifier
    # If identifier looks like an email, try resolve to username.
    if isinstance(identifier, str) and "@" in identifier:
        from .models import User

        user_obj = User.objects.filter(email__iexact=identifier).first()
        if user_obj:
            username_for_auth = user_obj.username

    user = authenticate(request, username=username_for_auth, password=password)
    if user is None:
        return JsonResponse({"detail": "Invalid credentials"}, status=400)

    # If TOTP is enabled, require an OTP code from Google Authenticator.
    if getattr(user, "totp_enabled", False):
        otp = (payload.get("otp") or "").strip().replace(" ", "")
        if not otp:
            return JsonResponse({"detail": "OTP required", "otp_required": True, "code": "otp_required"}, status=400)
        secret = getattr(user, "totp_secret", "") or ""
        if not secret:
            return JsonResponse({"detail": "OTP not configured"}, status=400)
        totp = pyotp.TOTP(secret)
        if not totp.verify(otp, valid_window=1):
            return JsonResponse({"detail": "Invalid OTP", "otp_required": True, "code": "otp_required"}, status=400)

    login(request, user)
    return JsonResponse({"authenticated": True, "user": _user_payload(user)})


def totp_confirm(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    setup_token = (payload.get("setup_token") or "").strip()
    otp = (payload.get("otp") or "").strip().replace(" ", "")
    if not setup_token or not otp:
        return JsonResponse({"detail": "setup_token and otp required"}, status=400)

    try:
        data = signing.loads(setup_token, salt="totp-setup", max_age=15 * 60)
        uid = int(data.get("uid"))
    except Exception:
        return JsonResponse({"detail": "Setup token expired or invalid"}, status=400)

    from .models import User

    user = User.objects.filter(id=uid).first()
    if not user:
        return JsonResponse({"detail": "User not found"}, status=400)
    if user.totp_enabled:
        # Already enabled; just log in.
        login(request, user)
        return JsonResponse({"authenticated": True, "user": _user_payload(user)})

    if not user.totp_secret:
        return JsonResponse({"detail": "OTP not configured"}, status=400)

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(otp, valid_window=1):
        return JsonResponse({"detail": "Invalid OTP"}, status=400)

    user.totp_enabled = True
    user.save(update_fields=["totp_enabled"])

    login(request, user)
    return JsonResponse({"authenticated": True, "user": _user_payload(user)})


def logout_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)

    logout(request)
    return JsonResponse({"authenticated": False})
