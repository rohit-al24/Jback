from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.utils import timezone

from .decorators import api_login_required
from .models import User, VideoCompletion, WeeklyContent


@api_login_required
def learning_path(request: HttpRequest) -> JsonResponse:
    user: User = request.user  # type: ignore[assignment]

    weeks = list(
        WeeklyContent.objects.filter(level=user.target_level, is_approved=True)
        .order_by("week_number")
        .values("id", "week_number")
    )
    completed_ids = set(
        VideoCompletion.objects.filter(user=user, weekly_content__level=user.target_level).values_list(
            "weekly_content_id",
            flat=True,
        )
    )

    nodes = []
    locked = False
    active_week_id = None

    for w in weeks:
        week_id = w["id"]
        is_complete = week_id in completed_ids
        if not is_complete and not locked and active_week_id is None:
            active_week_id = week_id

        if locked:
            status = "locked"
        elif is_complete:
            status = "completed"
        else:
            status = "active" if week_id == active_week_id else "locked"

        if status == "locked":
            locked = True

        nodes.append(
            {
                "weekly_content_id": week_id,
                "week_number": w["week_number"],
                "status": status,
            }
        )

    total = len(weeks)
    completed = len(completed_ids.intersection({w["id"] for w in weeks}))
    percent = int((completed / total) * 100) if total else 0

    return JsonResponse(
        {
            "level": user.target_level,
            "completed_weeks": completed,
            "total_weeks": total,
            "progress_percent": percent,
            "streak": user.streak_count,
            "points": user.total_points,
            "today": str(timezone.localdate()),
            "nodes": nodes,
        }
    )
