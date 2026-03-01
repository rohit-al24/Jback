from __future__ import annotations

from django.db import transaction
from django.db.models import F

from .models import XPEvent, User


@transaction.atomic
def award_xp(*, user_id: int, points: int, reason: str) -> None:
    """Awards XP to a user and records an XPEvent.

    This keeps `User.total_points` as the fast counter, while allowing
    leaderboard queries over recent XP using the event log.
    """

    if points == 0:
        return

    # Concurrency-safe increment.
    User.objects.filter(pk=user_id).update(total_points=F("total_points") + points)
    XPEvent.objects.create(user_id=user_id, points=points, reason=reason)
