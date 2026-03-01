from __future__ import annotations

from datetime import date, timedelta

from django.db.models import F

from .models import User


def touch_study_streak(*, user_id: int, today: date) -> None:
    """Update streak_count/last_study_date for a user in a concurrency-safe way.

    Rules:
    - If last_study_date == today: no change
    - If last_study_date == yesterday: streak +1
    - Else: streak = 1
    """

    user = User.objects.only("id", "last_study_date").filter(pk=user_id).first()
    if user is None:
        return

    if user.last_study_date == today:
        return

    yesterday = today - timedelta(days=1)
    if user.last_study_date == yesterday:
        User.objects.filter(pk=user_id).update(streak_count=F("streak_count") + 1, last_study_date=today)
    else:
        User.objects.filter(pk=user_id).update(streak_count=1, last_study_date=today)
