from __future__ import annotations

from datetime import date, timedelta

from django.db.models import F

from .models import User, UserStreak


def touch_study_streak(*, user_id: int, today: date) -> None:
    """Update streak for a user in a concurrency-safe way.

    Updates both User.streak_count (legacy fast counter) and the dedicated
    UserStreak table.

    Rules:
    - If last_activity_date == today: no change
    - If last_activity_date == yesterday: streak +1
    - Else: streak = 1
    """

    user = User.objects.only("id", "last_study_date").filter(pk=user_id).first()
    if user is None:
        return

    if user.last_study_date == today:
        return

    yesterday = today - timedelta(days=1)
    if user.last_study_date == yesterday:
        new_streak = (user.streak_count or 0) + 1
        User.objects.filter(pk=user_id).update(streak_count=F("streak_count") + 1, last_study_date=today)
    else:
        new_streak = 1
        User.objects.filter(pk=user_id).update(streak_count=1, last_study_date=today)

    # Sync to dedicated UserStreak table
    streak_obj, _ = UserStreak.objects.get_or_create(user_id=user_id)
    streak_obj.current_streak = new_streak
    streak_obj.last_activity_date = today
    if new_streak > streak_obj.longest_streak:
        streak_obj.longest_streak = new_streak
    streak_obj.save(update_fields=["current_streak", "longest_streak", "last_activity_date", "updated_at"])
