from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from django.http import HttpRequest, JsonResponse


TResponse = TypeVar("TResponse")


def api_login_required(view_func: Callable[..., TResponse]):
    """Like Django's login_required, but returns JSON 401 instead of redirect."""

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args: Any, **kwargs: Any):
        if not request.user.is_authenticated:
            return JsonResponse({"detail": "Authentication required"}, status=401)
        return view_func(request, *args, **kwargs)

    return _wrapped
