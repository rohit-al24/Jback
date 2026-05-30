from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class VocabularyHint(models.Model):
    """User-created hint for a vocabulary item."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vocabulary_hints",
    )
    vocabulary_item = models.ForeignKey(
        "course.VocabularyItem",
        on_delete=models.CASCADE,
        related_name="hints",
    )
    hint_text = models.TextField(help_text="User's personal memory hint or mnemonic")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "vocabulary_item"],
                name="unique_vocab_hint_per_user",
            )
        ]
        indexes = [
            models.Index(fields=["user", "vocabulary_item"]),
        ]

    def __str__(self) -> str:
        return f"Hint(user={self.user_id}, vocab={self.vocabulary_item_id})"


class HintUsage(models.Model):
    """Daily hint usage counter — max 3 hints per user per day during quizzes."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hint_usages",
    )
    date = models.DateField(db_index=True)
    count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"],
                name="unique_hint_usage_per_day",
            )
        ]

    DAILY_LIMIT = 3

    @classmethod
    def can_use(cls, user_id: int, today) -> bool:
        obj = cls.objects.filter(user_id=user_id, date=today).first()
        return obj is None or obj.count < cls.DAILY_LIMIT

    @classmethod
    def increment(cls, user_id: int, today) -> int:
        obj, _ = cls.objects.get_or_create(user_id=user_id, date=today)
        obj.count += 1
        obj.save(update_fields=["count"])
        return obj.count

    def __str__(self) -> str:
        return f"HintUsage(user={self.user_id}, date={self.date}, count={self.count})"
