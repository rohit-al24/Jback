from __future__ import annotations

import random
from datetime import date, timedelta

from django.db import transaction

from .models import Question, ReviewQueue, User


def schedule_two_reviews_for_wrong_answer(*, user: User, question: Question, today: date) -> None:
    """Create two future ReviewQueue items with randomized upcoming dates."""

    tomorrow = today + timedelta(days=1)
    candidate_offsets = [0, 1, 2, 3, 4, 5, 6]
    first_offset = random.choice(candidate_offsets)
    second_offset = random.choice(candidate_offsets)
    if second_offset == first_offset:
        second_offset = (second_offset + random.choice([1, 2, 3])) % 7

    scheduled_1 = tomorrow + timedelta(days=first_offset)
    scheduled_2 = tomorrow + timedelta(days=second_offset)

    with transaction.atomic():
        ReviewQueue.objects.create(user=user, question=question, scheduled_date=scheduled_1)
        ReviewQueue.objects.create(user=user, question=question, scheduled_date=scheduled_2)
