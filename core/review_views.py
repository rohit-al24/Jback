from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.utils import timezone

from .decorators import api_login_required
from .models import ReviewQueue, User


@api_login_required
def due_reviews(request: HttpRequest) -> JsonResponse:
    user: User = request.user  # type: ignore[assignment]
    today = timezone.localdate()
    items = (
        ReviewQueue.objects.select_related("question")
        .filter(user=user, scheduled_date=today)
        .order_by("?")[:50]
    )

    return JsonResponse(
        {
            "date": str(today),
            "count": len(items),
            "items": [
                {
                    "id": rq.id,
                    "question_id": rq.question_id,
                    "prompt": rq.question.prompt,
                }
                for rq in items
            ],
        }
    )
