from __future__ import annotations

import json

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie


def _user_payload(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.get_full_name(),
        "target_level": getattr(user, "target_level", None),
        "total_points": getattr(user, "total_points", None),
        "subscription_status": getattr(user, "subscription_status", None),
        "streak_count": getattr(user, "streak_count", None),
        "referral_code": getattr(user, "referral_code", None),
    }


@ensure_csrf_cookie
def csrf(request: HttpRequest) -> JsonResponse:
    # Sets the CSRF cookie. Useful for SPA bootstrapping.
    return JsonResponse({"detail": "CSRF cookie set"})


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
    referral_code = (payload.get("referral_code") or "").strip().upper()
    target_level = payload.get("target_level")

    if not username or not password:
        return JsonResponse({"detail": "username and password required"}, status=400)

    from .models import User

    if User.objects.filter(username=username).exists():
        return JsonResponse({"detail": "Username already exists"}, status=400)

    referred_by = None
    if referral_code:
        referred_by = User.objects.filter(referral_code=referral_code).first()

    user = User(username=username)
    if target_level in {"N5", "N4"}:
        user.target_level = target_level
    user.referred_by = referred_by
    user.set_password(password)
    user.save()

    # Default new users to the "student" role.
    try:
        from django.contrib.auth.models import Group

        student_group, _ = Group.objects.get_or_create(name="student")
        user.groups.add(student_group)
    except Exception:
        # Don't block registration if the auth tables aren't ready yet.
        pass

    login(request, user)
    return JsonResponse({"authenticated": True, "user": _user_payload(user)})


def login_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        return JsonResponse({"detail": "username and password required"}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"detail": "Invalid credentials"}, status=400)

    login(request, user)
    return JsonResponse({"authenticated": True, "user": _user_payload(user)})


def logout_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)

    logout(request)
    return JsonResponse({"authenticated": False})
