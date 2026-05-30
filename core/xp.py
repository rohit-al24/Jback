from __future__ import annotations

from django.db import transaction
from django.db.models import F

from .models import XPEvent, User, UserXP

# XP rates per activity type
XP_RATES: dict[str, int] = {
    "vocab_quiz_correct": 3,
    "grammar_quiz_correct": 4,
    "pakka_adaptive_normal": 2,
    "pakka_adaptive_flip": 5,
    "pakka_adaptive_speed": 10,
    "daily_revise_correct": 3,
    "streak_bonus": 10,
    "referral": 50,
    "other": 1,
}


@transaction.atomic
def award_xp(*, user_id: int, points: int, reason: str) -> None:
    """Awards XP to a user.

    Updates User.total_points (fast counter), UserXP.total_xp (dedicated table),
    and appends an XPEvent for leaderboard queries.
    """

    if points == 0:
        return

    # Concurrency-safe increment on User model
    User.objects.filter(pk=user_id).update(total_points=F("total_points") + points)

    # Update dedicated UserXP table (create if first time)
    UserXP.objects.update_or_create(
        user_id=user_id,
        defaults={},
    )
    UserXP.objects.filter(user_id=user_id).update(total_xp=F("total_xp") + points)

    # Append event log for leaderboard / analytics
    XPEvent.objects.create(user_id=user_id, points=points, reason=reason)
