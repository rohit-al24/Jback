from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid


class User(AbstractUser):
	class TargetLevel(models.TextChoices):
		N5 = "N5", "N5"
		N4 = "N4", "N4"

	class SubscriptionStatus(models.TextChoices):
		FREE = "free", "Free"
		PAID = "paid", "Paid"

	target_level = models.CharField(
		max_length=2,
		choices=TargetLevel.choices,
		default=TargetLevel.N5,
	)
	total_points = models.PositiveIntegerField(default=0)
	subscription_status = models.CharField(
		max_length=8,
		choices=SubscriptionStatus.choices,
		default=SubscriptionStatus.FREE,
	)

	referral_code = models.CharField(max_length=12, unique=True, blank=True)
	referred_by = models.ForeignKey(
		"self",
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="referrals",
	)

	streak_count = models.PositiveIntegerField(default=0)
	last_study_date = models.DateField(null=True, blank=True)

	def save(self, *args, **kwargs):
		if not self.referral_code:
			self.referral_code = str(uuid.uuid4()).replace("-", "")[:8].upper()
		super().save(*args, **kwargs)


class SubscriptionPlan(models.Model):
	"""Simple plan catalogue (price in INR paise)."""

	class Code(models.TextChoices):
		BASIC_MONTHLY = "basic_monthly", "Nihongo Basic (Monthly)"
		PRO_6MO = "pro_6mo", "Nihongo Pro (6 months)"

	code = models.CharField(max_length=32, choices=Code.choices, unique=True)
	display_name = models.CharField(max_length=64)
	price_paise = models.PositiveIntegerField()
	duration_days = models.PositiveIntegerField()
	is_active = models.BooleanField(default=True)

	# Optional for Stripe Checkout wiring
	stripe_price_id = models.CharField(max_length=64, blank=True)

	def __str__(self) -> str:
		return self.display_name


class UserSubscription(models.Model):
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
	started_at = models.DateTimeField(default=timezone.now)
	ends_at = models.DateTimeField()
	is_active = models.BooleanField(default=True)

	class Meta:
		indexes = [models.Index(fields=["user", "is_active", "ends_at"])]


class WeeklyContent(models.Model):
	class Level(models.TextChoices):
		N5 = "N5", "N5"
		N4 = "N4", "N4"

	level = models.CharField(max_length=2, choices=Level.choices)
	week_number = models.PositiveIntegerField()
	video_file = models.FileField(upload_to="weekly_videos/")
	is_approved = models.BooleanField(default=False)

	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["level", "week_number"],
				name="unique_week_per_level",
			)
		]

	def __str__(self) -> str:
		return f"{self.level} - Week {self.week_number}"


class Question(models.Model):
	weekly_content = models.ForeignKey(
		WeeklyContent,
		on_delete=models.CASCADE,
		related_name="questions",
	)
	prompt = models.TextField()
	option_a = models.CharField(max_length=255)
	option_b = models.CharField(max_length=255)
	option_c = models.CharField(max_length=255)
	option_d = models.CharField(max_length=255)

	class CorrectAnswer(models.TextChoices):
		A = "A", "A"
		B = "B", "B"
		C = "C", "C"
		D = "D", "D"

	correct_answer = models.CharField(max_length=1, choices=CorrectAnswer.choices)

	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self) -> str:
		return f"Q{self.pk} (Week {self.weekly_content.week_number})"


class ReviewQueue(models.Model):
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	question = models.ForeignKey(Question, on_delete=models.CASCADE)
	scheduled_date = models.DateField(db_index=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		indexes = [
			models.Index(fields=["user", "scheduled_date"]),
			models.Index(fields=["user", "question", "scheduled_date"]),
		]

	def __str__(self) -> str:
		return f"Review(user={self.user_id}, q={self.question_id}, date={self.scheduled_date})"


class MasteredQuestion(models.Model):
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	question = models.ForeignKey(Question, on_delete=models.CASCADE)
	mastered_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["user", "question"],
				name="unique_mastery",
			)
		]


class VideoCompletion(models.Model):
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	weekly_content = models.ForeignKey(WeeklyContent, on_delete=models.CASCADE)
	completed_at = models.DateTimeField(default=timezone.now)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["user", "weekly_content"],
				name="unique_video_completion",
			)
		]

	def __str__(self) -> str:
		return f"VideoCompletion(user={self.user_id}, week={self.weekly_content_id})"


class Mondai(models.Model):
	class Status(models.TextChoices):
		DRAFT = "draft", "Draft"
		PENDING = "pending", "Pending"
		APPROVED = "approved", "Approved"
		REJECTED = "rejected", "Rejected"

	class VideoType(models.TextChoices):
		UPLOAD = "upload", "Upload"
		LINK = "link", "Link"
		EMBED = "embed", "Embed"

	public_id = models.CharField(max_length=16, unique=True, editable=False)
	name = models.CharField(max_length=120, blank=True)

	video_type = models.CharField(max_length=10, choices=VideoType.choices, default=VideoType.UPLOAD)
	video_file = models.FileField(upload_to="mondai_videos/", blank=True, null=True)
	video_url = models.URLField(blank=True)
	video_embed_url = models.URLField(blank=True)

	transcript = models.TextField(blank=True)
	status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)

	created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mondais")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	reviewed_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="reviewed_mondais",
	)
	reviewed_at = models.DateTimeField(null=True, blank=True)
	review_note = models.TextField(blank=True)

	class Meta:
		indexes = [
			models.Index(fields=["status", "created_at"]),
			models.Index(fields=["created_by", "updated_at"]),
		]

	def save(self, *args, **kwargs):
		if not self.public_id:
			# Human-friendly short id.
			self.public_id = "MON-" + str(uuid.uuid4()).replace("-", "")[:8].upper()
		if not self.name:
			self.name = "Untitled Mondai"
		super().save(*args, **kwargs)

	def __str__(self) -> str:
		return f"{self.public_id} - {self.name}"

	@property
	def display_video(self) -> dict:
		"""Template-friendly representation of video source."""
		if self.video_type == self.VideoType.UPLOAD and self.video_file:
			return {"type": "upload", "url": self.video_file.url}
		if self.video_type == self.VideoType.LINK and self.video_url:
			return {"type": "link", "url": self.video_url}
		if self.video_type == self.VideoType.EMBED and self.video_embed_url:
			return {"type": "embed", "url": self.video_embed_url}
		return {"type": "none"}


class MondaiVocabulary(models.Model):
	mondai = models.ForeignKey(Mondai, on_delete=models.CASCADE, related_name="vocab")
	term = models.CharField(max_length=120)
	reading = models.CharField(max_length=120, blank=True)
	meaning = models.CharField(max_length=255, blank=True)
	order = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ["order", "id"]

	def __str__(self) -> str:
		return self.term


class MondaiQuestion(models.Model):
	class CorrectAnswer(models.TextChoices):
		A = "A", "A"
		B = "B", "B"
		C = "C", "C"
		D = "D", "D"

	mondai = models.ForeignKey(Mondai, on_delete=models.CASCADE, related_name="questions")
	prompt = models.TextField()
	option_a = models.CharField(max_length=255)
	option_b = models.CharField(max_length=255)
	option_c = models.CharField(max_length=255)
	option_d = models.CharField(max_length=255, blank=True)
	correct_answer = models.CharField(max_length=1, choices=CorrectAnswer.choices)
	order = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ["order", "id"]

	def clean(self):
		# Allow 3 or 4 options: D may be blank, but can't be correct in that case.
		from django.core.exceptions import ValidationError

		if not self.option_a or not self.option_b or not self.option_c:
			raise ValidationError("Options A, B and C are required")
		if not self.option_d and self.correct_answer == self.CorrectAnswer.D:
			raise ValidationError("Option D is blank, so it cannot be the correct answer")

	def __str__(self) -> str:
		return f"MondaiQ{self.pk} ({self.mondai.public_id})"
