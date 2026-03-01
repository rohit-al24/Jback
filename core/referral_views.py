from __future__ import annotations

from django.http import HttpRequest, JsonResponse

from .decorators import api_login_required
from .models import User


@api_login_required
def referral_dashboard(request: HttpRequest) -> JsonResponse:
    user: User = request.user  # type: ignore[assignment]
    count = User.objects.filter(referred_by=user).count()
    return JsonResponse({"referral_code": user.referral_code, "referred_count": count})
