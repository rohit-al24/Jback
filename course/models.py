from __future__ import annotations

from django.conf import settings
from django.db import models


class Level(models.Model):
    """Represents a course level (e.g., Level 1, Level 2)."""
    level_number = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "level_number"]
        db_table = "core_level"
        managed = False

    def __str__(self) -> str:
        return self.name or f"Level {self.level_number}"


class Unit(models.Model):
    """Represents a unit within a level."""
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="units")
    unit_number = models.PositiveIntegerField()
    name = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "unit_number"]
        db_table = "core_unit"
        managed = False
        constraints = [
            models.UniqueConstraint(
                fields=["level", "unit_number"],
                name="unique_unit_per_level",
            )
        ]

    def __str__(self) -> str:
        return f"{self.level} - Unit {self.unit_number}"


class VocabularyItem(models.Model):
    """Vocabulary item for a unit with target (Hiragana) and correct (English) plus distractors."""
    class CorrectAnswer(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"
        D = "D", "D"

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="vocabulary")
    exam = models.ForeignKey('administration.Exam', on_delete=models.CASCADE, related_name="vocabulary_items", null=True, blank=True)
    target = models.CharField(max_length=255, help_text="Target word (Hiragana)")
    correct = models.CharField(max_length=255, help_text="Correct English translation")
    wrong1 = models.CharField(max_length=255, help_text="Wrong option 1")
    wrong2 = models.CharField(max_length=255, help_text="Wrong option 2")
    wrong3 = models.CharField(max_length=255, help_text="Wrong option 3")
    correct_answer = models.CharField(
        max_length=1,
        choices=CorrectAnswer.choices,
        blank=True,
        help_text="Auto-calculated: which slot (A-D) contains the correct answer after shuffle"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        db_table = "core_vocabularyitem"
        managed = False

    def __str__(self) -> str:
        return f"{self.unit} - {self.target}"


class GrammarContent(models.Model):
    """Grammar explanations and patterns for a unit."""
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="grammar")
    exam = models.ForeignKey('administration.Exam', on_delete=models.CASCADE, related_name="grammar_items", null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField(help_text="Grammar explanation, sentence patterns, particle usage")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        db_table = "core_grammarcontent"
        managed = False

    def __str__(self) -> str:
        return f"{self.unit} - {self.title or 'Grammar'}"

class UserVocabState(models.Model):
    """Tracks each user's mastery state for every VocabularyItem they have attempted."""

    class Mode(models.TextChoices):
        NORMAL = "normal", "Normal (Hiragana → English)"
        FLIP = "flip", "Flip (English → Hiragana)"
        SPEED = "speed", "Speed Drill"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vocab_states",
    )
    vocab_item = models.ForeignKey(
        VocabularyItem,
        on_delete=models.CASCADE,
        related_name="user_states",
    )

    # ── Progress ──────────────────────────────────────────────────
    streak_correct = models.PositiveIntegerField(default=0)   # consecutive correct in current mode
    streak_normal  = models.PositiveIntegerField(default=0)   # total consecutive correct in normal (unlocks flip)
    lapses         = models.PositiveIntegerField(default=0)   # lifetime wrong answers
    is_weak        = models.BooleanField(default=False)       # currently in heavy loop

    # ── Mode / mastery ────────────────────────────────────────────
    mode    = models.CharField(max_length=10, choices=Mode.choices, default=Mode.NORMAL)
    mastered = models.BooleanField(default=False)             # graduated from speed drill

    # ── Spaced repetition ─────────────────────────────────────────
    last_answered_at = models.DateTimeField(null=True, blank=True, db_index=True)
    due_at           = models.DateTimeField(null=True, blank=True, db_index=True)
    half_life_days   = models.FloatField(default=1.0)         # grows as mastery deepens

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "vocab_item"], name="unique_user_vocab_state"),
        ]
        indexes = [
            models.Index(fields=["user", "mastered"]),
            models.Index(fields=["user", "due_at"]),
            models.Index(fields=["user", "is_weak"]),
        ]

    def __str__(self) -> str:
        return f"VocabState({self.user_id}, vocab={self.vocab_item_id}, mode={self.mode}, streak={self.streak_correct})"