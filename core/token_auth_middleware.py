from __future__ import annotations

from django.http import HttpRequest
from django.utils.functional import SimpleLazyObject


def _get_user_from_token(request: HttpRequest):
    """Resolve user from Authorization: Token <key> header."""
    from django.contrib.auth.models import AnonymousUser

    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Token "):
        return None

    key = auth_header[6:].strip()
    if not key:
        return None

    from .models import PersistentToken

    try:
        token = PersistentToken.objects.select_related("user").get(key=key)
    except PersistentToken.DoesNotExist:
        return None

    if token.user.is_active:
        return token.user
    return None


class PersistentTokenAuthMiddleware:
    """Authenticate via Authorization: Token <key> when no session exists."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        # Only inject token user when the session did not already authenticate.
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            token_user = _get_user_from_token(request)
            if token_user is not None:
                request.user = token_user
                # Mark request as token-authenticated so CSRF can be skipped
                request._dont_enforce_csrf_checks = True
        return self.get_response(request)
