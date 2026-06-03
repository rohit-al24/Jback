from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt


TResponse = TypeVar("TResponse")


def api_login_required(view_func: Callable[..., TResponse]):
    """Like Django's login_required, but returns JSON 401 instead of redirect."""

    @wraps(view_func)
    @csrf_exempt
    def _wrapped(request: HttpRequest, *args: Any, **kwargs: Any):
        if not request.user.is_authenticated:
            return JsonResponse({"detail": "Authentication required"}, status=401)
        return view_func(request, *args, **kwargs)

    return _wrapped


def require_role(*role_names: str):
    """Decorator: user must have at least one of the listed roles (via UserRole).

    Usage::

        @require_role("master_admin", "college_admin")
        def my_view(request): ...
    """

    def decorator(view_func: Callable[..., TResponse]):
        @wraps(view_func)
        @csrf_exempt
        def _wrapped(request: HttpRequest, *args: Any, **kwargs: Any):
            if not request.user.is_authenticated:
                return JsonResponse({"detail": "Authentication required"}, status=401)
            # Superusers bypass role checks
            if getattr(request.user, "is_superuser", False):
                return view_func(request, *args, **kwargs)
            # Import here to avoid circular imports
            from administration.models import UserRole
            has_role = UserRole.objects.filter(
                user=request.user,
                role__name__in=role_names,
                role__is_active=True,
            ).exists()
            if not has_role:
                return JsonResponse(
                    {"detail": f"Access denied. Required role: {', '.join(role_names)}"},
                    status=403,
                )
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator

