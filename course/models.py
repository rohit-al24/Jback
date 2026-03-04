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
    exam = models.ForeignKey(
        'administration.Exam',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='levels',
    )

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


class GrammarPakkaItem(models.Model):
    """Structured grammar practice content for the 4-step Pakka flow."""

    class StepType(models.IntegerChoices):
        BLUEPRINT = 1, "Blueprint"
        BUILDER = 2, "Builder"
        HEAVY_LOOP = 3, "Heavy Loop"
        BEAST_MODE = 4, "Beast Mode"

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="grammar_pakka")
    exam = models.ForeignKey(
        'administration.Exam',
        on_delete=models.CASCADE,
        related_name="grammar_pakka_items",
        null=True,
        blank=True,
    )

    step_type = models.PositiveSmallIntegerField(choices=StepType.choices)
    # Optional metadata for exam grouping/filtering (e.g. N5_G01)
    exam_level = models.PositiveSmallIntegerField(default=1)
    exam_code = models.CharField(max_length=32, blank=True)
    logic_formula = models.CharField(max_length=255, blank=True)
    english_prompt = models.CharField(max_length=255)
    correct_sentence = models.TextField()

    # CSV stores comma-separated fragments; API returns an array.
    word_blocks = models.TextField(blank=True)
    particle_target = models.CharField(max_length=32, blank=True)
    # CSV stores comma-separated distractors (wrong particles/verb options).
    distractors = models.TextField(blank=True)
    explanation_hint = models.TextField(blank=True)

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        db_table = "core_grammarpakkaitem"
        indexes = [
            models.Index(fields=["unit", "step_type", "order"], name="gpi_unit_step_order_idx"),
            models.Index(fields=["exam_level", "exam_code"], name="gpi_exam_meta_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["unit", "step_type", "english_prompt"],
                name="unique_grammarpakka_unit_step_prompt",
            )
        ]

    def __str__(self) -> str:
        return f"GrammarPakka(unit={self.unit.pk}, step={self.step_type})"


class GrammarLearnItem(models.Model):
    """Grammar Learn table for the study/blueprint screen.

    User-facing schema:
    - exam_level: integer
    - unit_id: integer
    - topic_order: integer
    - title: varchar
    - logic_formula: varchar
    - explanation: text
    - example_jp: text
    - example_en: text
    - visual_type: varchar, optional
    - pakka_tip: text, optional

    Internal note:
    - `exam_code` is retained for app-side grouping/filtering and can be
      auto-derived from exam_level + unit_id as N{level}_G{unit_number:02d}.
    """

    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="grammar_learn_items",
    )

    exam_level = models.PositiveSmallIntegerField(default=5)
    exam_code = models.CharField(max_length=32, blank=True)
    topic_order = models.PositiveIntegerField(default=0)

    title = models.CharField(max_length=200)
    # The key grammar element being taught (e.g. 'じゃありません', 'は', 'です').
    # Displayed as the large hero character at the top of each learn card.
    main_character = models.CharField(max_length=100, blank=True)
    logic_formula = models.CharField(max_length=255)
    explanation = models.TextField()

    # One row = one example pair.  Multiple rows sharing topic_order form one card.
    example_jp = models.TextField(blank=True)
    example_en = models.TextField(blank=True)

    visual_type = models.CharField(max_length=64, blank=True)
    pakka_tip = models.TextField(blank=True)

    class Meta:
        ordering = ["topic_order", "id"]
        db_table = "core_grammarlearnitem"
        indexes = [
            models.Index(fields=["unit", "topic_order"], name="gli_unit_topic_order_idx"),
            models.Index(fields=["exam_level", "exam_code"], name="gli_exam_meta_idx"),
            models.Index(fields=["unit", "exam_code"], name="gli_unit_exam_idx"),
        ]

    def __str__(self) -> str:
        return f"GrammarLearnItem(unit={self.unit_id}, title={self.title})"

    def save(self, *args, **kwargs):
        if not self.exam_code and self.exam_level and self.unit_id:
            self.exam_code = f"N{self.exam_level}_G{self.unit.unit_number:02d}"
        super().save(*args, **kwargs)


class GrammarLearnContent(models.Model):
    """Structured 'Learn' page sections for grammar units."""

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="grammar_learn")

    # Optional metadata for exam grouping/filtering (e.g. N5_G01)
    exam_level = models.PositiveSmallIntegerField(default=1)
    exam_code = models.CharField(max_length=32, blank=True)

    section_title = models.CharField(max_length=200)
    visual_type = models.CharField(max_length=64)
    content_body = models.TextField()
    sensei_tip = models.TextField(blank=True)

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        db_table = "core_grammarlearncontent"
        indexes = [
            models.Index(fields=["unit", "order"], name="glc_unit_order_idx"),
            models.Index(fields=["exam_level", "exam_code"], name="glc_exam_meta_idx"),
            models.Index(fields=["unit", "exam_code"], name="glc_unit_exam_idx"),
        ]

    def __str__(self) -> str:
        return f"GrammarLearn(unit={self.unit.pk}, type={self.visual_type})"

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
            models.Index(fields=["user", "mastered"], name="course_user_user_id_9a6e8b_idx"),
            models.Index(fields=["user", "due_at"], name="course_user_user_id_b845f9_idx"),
            models.Index(fields=["user", "is_weak"], name="course_user_user_id_5a05e3_idx"),
        ]

    def __str__(self) -> str:
        return f"VocabState({self.user_id}, vocab={self.vocab_item_id}, mode={self.mode}, streak={self.streak_correct})"