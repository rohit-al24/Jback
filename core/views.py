from __future__ import annotations

import json
import random
from io import BytesIO

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Case, Count, F, IntegerField, Q, Sum, When
from django.db.utils import OperationalError, ProgrammingError
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .decorators import api_login_required
from .models import (
	DailyQuizTask,
	MasteredQuestion,
	Mondai,
	MondaiAnswerAttempt,
	MondaiQuestion,
	Question,
	ReviewQueue,
	User,
	VideoCompletion,
	WeeklyContent,
    EmailOTP,
)
from .models import College
from .services import schedule_two_reviews_for_wrong_answer
from .streaks import touch_study_streak
from .xp import award_xp
import hashlib
from datetime import timedelta


def _schema_out_of_date_response() -> JsonResponse:
	"""Return a helpful error when production DB migrations weren’t applied."""
	return JsonResponse(
		{
			"detail": "Server database schema is out of date. On the VPS, run 'python manage.py migrate' and restart the server.",
		},
		status=500,
	)


def _is_paid(user: User) -> bool:
	return getattr(user, "subscription_status", None) == User.SubscriptionStatus.PAID


def _current_weekly_content_for_user(user: User) -> WeeklyContent | None:
	return (
		WeeklyContent.objects.filter(level=user.target_level, is_approved=True)
		.order_by("-week_number")
		.first()
	)


def _question_to_payload(question: Question) -> dict:
	return {
		"id": question.id,
		"prompt": question.prompt,
		"options": {
			"A": question.option_a,
			"B": question.option_b,
			"C": question.option_c,
			"D": question.option_d,
		},
		"week_number": question.weekly_content.week_number,
	}


@api_login_required
def daily_quiz(request: HttpRequest) -> JsonResponse:
	"""Sun-Fri: returns a mixed list of due reviews + new questions."""

	user: User = request.user  # type: ignore[assignment]
	today = timezone.localdate()

	# Prioritize review items scheduled for today.
	due_review_qs = (
		ReviewQueue.objects.select_related("question", "question__weekly_content")
		.filter(user=user, scheduled_date=today)
		.order_by("?")
	)
	due_questions = [rq.question for rq in due_review_qs[:10]]

	weekly = _current_weekly_content_for_user(user)
	if weekly is None:
		return JsonResponse({"questions": [], "detail": "No approved weekly content yet."})

	# Pull new questions from the current week, excluding anything already in due reviews.
	excluded_ids = {q.id for q in due_questions}
	new_candidates = (
		Question.objects.select_related("weekly_content")
		.filter(weekly_content=weekly)
		.exclude(id__in=excluded_ids)
		.order_by("?")
	)
	new_questions = list(new_candidates[:10])

	mixed = due_questions + new_questions
	random.shuffle(mixed)

	return JsonResponse(
		{
			"date": str(today),
			"week": {
				"weekly_content_id": weekly.id,
				"level": weekly.level,
				"week_number": weekly.week_number,
			},
			"questions": [_question_to_payload(q) for q in mixed],
		}
	)


@api_login_required
def submit_answer(request: HttpRequest) -> JsonResponse:
	if request.method != "POST":
		return JsonResponse({"detail": "POST required"}, status=405)

	user: User = request.user  # type: ignore[assignment]
	today = timezone.localdate()

	try:
		payload = json.loads(request.body.decode("utf-8"))
	except json.JSONDecodeError:
		return JsonResponse({"detail": "Invalid JSON"}, status=400)

	question_id = payload.get("question_id")
	selected = (payload.get("selected") or "").strip().upper()
	if not question_id or selected not in {"A", "B", "C", "D"}:
		return JsonResponse({"detail": "question_id and selected(A-D) required"}, status=400)

	question = get_object_or_404(Question.objects.select_related("weekly_content"), pk=question_id)

	touch_study_streak(user_id=user.pk, today=today)

	is_correct = selected == question.correct_answer
	if is_correct:
		award_xp(user_id=user.pk, points=1, reason="question_correct")
		MasteredQuestion.objects.get_or_create(user=user, question=question)
		# Clear any scheduled review items for this question today.
		ReviewQueue.objects.filter(user=user, question=question, scheduled_date=today).delete()
	else:
		schedule_two_reviews_for_wrong_answer(user=user, question=question, today=today)

	return JsonResponse({"correct": is_correct})


def _hash_otp(email: str, otp: str) -> str:
	h = hashlib.sha256()
	h.update((otp + settings.SECRET_KEY + (email or "")).encode("utf-8"))
	return h.hexdigest()


def send_email_otp(request: HttpRequest) -> JsonResponse:
	"""Public endpoint: POST { email: ... } -> sends OTP via configured Apps Script."""
	if request.method != "POST":
		return JsonResponse({"detail": "POST required"}, status=405)

	try:
		payload = json.loads(request.body.decode("utf-8"))
	except json.JSONDecodeError:
		return JsonResponse({"detail": "Invalid JSON"}, status=400)

	email = (payload.get("email") or "").strip().lower()
	if not email:
		return JsonResponse({"detail": "email required"}, status=400)

	apps_url = getattr(settings, "APPS_SCRIPT_URL", None)
	if not apps_url:
		return JsonResponse({"detail": "Email OTP sender is not configured"}, status=500)

	# Generate 6-digit OTP
	otp = f"{random.randint(0, 999999):06d}"
	otp_hash = _hash_otp(email, otp)
	expires = timezone.now() + timedelta(minutes=10)

	# Call Apps Script to send email (strict: fail if delivery call fails)
	apps_secret = getattr(settings, "APPS_SCRIPT_SECRET", "")
	try:
		# Lazy import requests to avoid hard dependency at import time
		import requests
		res = requests.post(apps_url, data={"email": email, "otp": otp, "secret": apps_secret}, timeout=12)
		if not getattr(res, "ok", False):
			return JsonResponse({"detail": "Failed to send OTP"}, status=502)
	except Exception as e:
		return JsonResponse({"detail": f"Failed to send OTP: {str(e) or 'network error'}"}, status=502)

	EmailOTP.objects.create(email=email, otp_hash=otp_hash, expires_at=expires)

	return JsonResponse({"sent": True, "expires_at": expires.isoformat()})


def verify_email_otp(request: HttpRequest) -> JsonResponse:
	"""Public endpoint: POST { email, otp } -> verify and mark used."""
	if request.method != "POST":
		return JsonResponse({"detail": "POST required"}, status=405)

	try:
		payload = json.loads(request.body.decode("utf-8"))
	except json.JSONDecodeError:
		return JsonResponse({"detail": "Invalid JSON"}, status=400)

	email = (payload.get("email") or "").strip().lower()
	otp = (payload.get("otp") or "").strip()
	if not email or not otp:
		return JsonResponse({"detail": "email and otp required"}, status=400)

	otp_hash = _hash_otp(email, otp)
	now = timezone.now()
	match = (
		EmailOTP.objects.filter(email=email, otp_hash=otp_hash, used=False, expires_at__gte=now)
		.order_by("-created_at")
		.first()
	)
	if not match:
		return JsonResponse({"detail": "Invalid or expired OTP"}, status=400)

	match.used = True
	match.save()

	# Store a short-lived session flag so registration can enforce OTP-before-create.
	request.session["email_otp_verified_email"] = email
	request.session["email_otp_verified_until"] = (timezone.now() + timedelta(minutes=15)).isoformat()

	# Mark associated user email_verified if present
	try:
		user = User.objects.filter(email__iexact=email).first()
		if user:
			user.email_verified = True
			user.save(update_fields=["email_verified"])
	except Exception:
		pass

	return JsonResponse({"verified": True})


def _iso_week_start_end(week_start: timezone.datetime.date) -> tuple[str, str]:
	return (week_start.isoformat(), (week_start + timezone.timedelta(days=6)).isoformat())


@api_login_required
def leaderboard(request: HttpRequest) -> JsonResponse:
	"""Weekly leaderboard based on XP earned in the last 7 days."""

	from datetime import timedelta

	from django.db.models import Sum
	from django.db.models.functions import Coalesce

	seven_days_ago = timezone.now() - timedelta(days=7)

	rows = (
		User.objects.filter(is_active=True)
		.annotate(
			xp_week=Coalesce(
				Sum(
					"xp_events__points",
					filter=Q(xp_events__created_at__gte=seven_days_ago),
				),
				0,
			)
		)
		.order_by("-xp_week", "-total_points", "-streak_count", "username")
	)

	entries: list[dict] = []
	for idx, u in enumerate(rows[:50], start=1):
		full_name = (u.get_full_name() or u.username).strip()
		initials = "".join([p[:1].upper() for p in full_name.split()[:2]]) or (u.username[:2].upper())
		xp_week = int(getattr(u, "xp_week", 0) or 0)
		entries.append(
			{
				"rank": idx,
				"name": full_name,
				"avatar": initials,
				"level": getattr(u, "target_level", None),
				"streak": int(getattr(u, "streak_count", 0) or 0),
				"points_week": xp_week,
				"points_total": int(getattr(u, "total_points", 0) or 0),
			}
		)

	return JsonResponse({"entries": entries})
@api_login_required
def current_week_content(request: HttpRequest) -> JsonResponse:
	"""Return current calendar-week Mondai content (approved + fixed week)."""

	user: User = request.user  # type: ignore[assignment]
	# Students only.
	if getattr(user, "role", "student") not in {"student", "employee"}:
		return JsonResponse({"detail": "Not allowed"}, status=403)

	today = timezone.localdate()
	try:
		mondais = (
			Mondai.objects.filter(
				status=Mondai.Status.APPROVED,
				week_start_date__lte=today,
				week_end_date__gte=today,
			)
			.order_by("public_id")
		)
		first = mondais.first()
		week_start = first.week_start_date if first else None
		week_end = first.week_end_date if first else None
		mondai_items = [
			{
				"public_id": m.public_id,
				"name": m.name,
				"question_count": m.questions.count(),
			}
			for m in mondais
		]
	except (OperationalError, ProgrammingError):
		return _schema_out_of_date_response()

	return JsonResponse(
		{
			"date": today.isoformat(),
			"week": {
				"start": week_start.isoformat() if week_start else None,
				"end": week_end.isoformat() if week_end else None,
			},
			"mondais": mondai_items,
		}
	)


@api_login_required
def week_study_questions(request: HttpRequest) -> JsonResponse:
	"""All questions for a fixed week, including correct answers (study mode).

	Accepts optional query param: ?date=YYYY-MM-DD (defaults to today).
	"""

	user: User = request.user  # type: ignore[assignment]
	try:
		from datetime import date

		date_str = (request.GET.get("date") or "").strip()
		today = date.fromisoformat(date_str) if date_str else timezone.localdate()
	except Exception:
		return JsonResponse({"detail": "Invalid date"}, status=400)

	try:
		mondais = Mondai.objects.filter(
			status=Mondai.Status.APPROVED,
			week_start_date__lte=today,
			week_end_date__gte=today,
		)
		first = mondais.first()
		week_start = first.week_start_date if first else None
		week_end = first.week_end_date if first else None
		qs = MondaiQuestion.objects.select_related("mondai").filter(mondai__in=mondais)
		items = []
		for q in qs:
			items.append(
				{
					"id": q.id,
					"mondai_public_id": q.mondai.public_id,
					"prompt": q.prompt,
					"options": {
						"A": q.option_a,
						"B": q.option_b,
						"C": q.option_c,
						"D": q.option_d,
					},
					"correct": q.correct_answer,
				}
			)
		random.shuffle(items)
	except (OperationalError, ProgrammingError):
		return _schema_out_of_date_response()
	return JsonResponse(
		{
			"date": today.isoformat(),
			"week": {
				"start": week_start.isoformat() if week_start else None,
				"end": week_end.isoformat() if week_end else None,
			},
			"questions": items,
		}
	)


@api_login_required
def fixed_week_list(request: HttpRequest) -> JsonResponse:
	"""Returns current and previous fixed-week ranges for students."""

	user: User = request.user  # type: ignore[assignment]
	if getattr(user, "role", "student") not in {"student", "employee"}:
		return JsonResponse({"detail": "Not allowed"}, status=403)

	today = timezone.localdate()
	try:
		current_qs = Mondai.objects.filter(
			status=Mondai.Status.APPROVED,
			week_start_date__lte=today,
			week_end_date__gte=today,
		)
		current_first = current_qs.first()
		current_start = current_first.week_start_date if current_first else None
		current_end = current_first.week_end_date if current_first else None
		current_count = MondaiQuestion.objects.filter(mondai__in=current_qs).count() if current_first else 0

		prev_mondai = (
			Mondai.objects.filter(status=Mondai.Status.APPROVED, week_end_date__lt=today)
			.exclude(week_start_date__isnull=True)
			.exclude(week_end_date__isnull=True)
			.order_by("-week_end_date")
			.first()
		)
	except (OperationalError, ProgrammingError):
		return _schema_out_of_date_response()
	prev_start = getattr(prev_mondai, "week_start_date", None)
	prev_end = getattr(prev_mondai, "week_end_date", None)
	prev_count = 0
	if prev_start and prev_end:
		prev_qs = Mondai.objects.filter(
			status=Mondai.Status.APPROVED,
			week_start_date=prev_start,
			week_end_date=prev_end,
		)
		prev_count = MondaiQuestion.objects.filter(mondai__in=prev_qs).count()

	return JsonResponse(
		{
			"today": today.isoformat(),
			"current": {
				"start": current_start.isoformat() if current_start else None,
				"end": current_end.isoformat() if current_end else None,
				"question_count": int(current_count),
			},
			"previous": {
				"start": prev_start.isoformat() if prev_start else None,
				"end": prev_end.isoformat() if prev_end else None,
				"question_count": int(prev_count),
			},
		}
	)


@api_login_required
def daily_task(request: HttpRequest) -> JsonResponse:
	user: User = request.user  # type: ignore[assignment]
	today = timezone.localdate()
	task, _ = DailyQuizTask.objects.get_or_create(user=user, date=today)
	remaining = max(0, int(task.target_questions) - int(task.answered_questions))
	return JsonResponse(
		{
			"date": today.isoformat(),
			"target": task.target_questions,
			"answered": task.answered_questions,
			"remaining": remaining,
			"rewarded": task.rewarded,
		}
	)


@api_login_required
def daily_week_quiz(request: HttpRequest) -> JsonResponse:
	"""Returns today's quiz questions from the current fixed week (no answers exposed)."""

	user: User = request.user  # type: ignore[assignment]
	today = timezone.localdate()
	try:
		mondais = Mondai.objects.filter(
			status=Mondai.Status.APPROVED,
			week_start_date__lte=today,
			week_end_date__gte=today,
		)
		qs = MondaiQuestion.objects.select_related("mondai").filter(mondai__in=mondais).order_by("?")
	except (OperationalError, ProgrammingError):
		return _schema_out_of_date_response()

	# Use remaining count as the quiz size, but at least 1.
	task, _ = DailyQuizTask.objects.get_or_create(user=user, date=today)
	remaining = max(0, int(task.target_questions) - int(task.answered_questions))
	count = min(remaining if remaining > 0 else 10, 20)
	items = []
	for q in qs[:count]:
		items.append(
			{
				"id": q.id,
				"prompt": q.prompt,
				"options": {
					"A": q.option_a,
					"B": q.option_b,
					"C": q.option_c,
					"D": q.option_d,
				},
			}
		)

	return JsonResponse({"date": today.isoformat(), "questions": items})


@api_login_required
def daily_week_quiz_retake(request: HttpRequest) -> JsonResponse:
	"""Paid-only retake: returns a fresh set of questions for today (no answers exposed).

	This does not alter the daily target; it's meant as extra practice after finishing.
	"""

	user: User = request.user  # type: ignore[assignment]
	if not _is_paid(user):
		return JsonResponse({"detail": "Paid subscription required"}, status=402)

	today = timezone.localdate()
	try:
		mondais = Mondai.objects.filter(
			status=Mondai.Status.APPROVED,
			week_start_date__lte=today,
			week_end_date__gte=today,
		)
		qs = MondaiQuestion.objects.select_related("mondai").filter(mondai__in=mondais)
	except (OperationalError, ProgrammingError):
		return _schema_out_of_date_response()

	# Prefer unseen questions for today.
	seen_ids = set(
		MondaiAnswerAttempt.objects.filter(user=user, date=today).values_list("mondai_question_id", flat=True)
	)
	if seen_ids:
		qs = qs.exclude(id__in=seen_ids)
	qs = qs.order_by("?")

	count = 10
	items = []
	for q in qs[:count]:
		items.append(
			{
				"id": q.id,
				"prompt": q.prompt,
				"options": {
					"A": q.option_a,
					"B": q.option_b,
					"C": q.option_c,
					"D": q.option_d,
				},
			}
		)

	return JsonResponse({"date": today.isoformat(), "questions": items, "mode": "retake"})


@api_login_required
def quiz_history(request: HttpRequest) -> JsonResponse:
	"""Returns recent quiz/task days + correctness stats for history."""

	user: User = request.user  # type: ignore[assignment]
	today = timezone.localdate()

	# Last 60 task days.
	tasks = list(DailyQuizTask.objects.filter(user=user).order_by("-date")[:60])
	if not tasks:
		return JsonResponse({"items": []})

	dates = [t.date for t in tasks]

	correct_sum = Sum(Case(When(correct=True, then=1), default=0, output_field=IntegerField()))
	agg = (
		MondaiAnswerAttempt.objects.filter(user=user, date__in=dates)
		.values("date")
		.annotate(total=Count("id"), correct=correct_sum)
	)
	by_date = {row["date"]: row for row in agg}

	items: list[dict] = []
	for t in tasks:
		row = by_date.get(t.date) or {}
		total = int(row.get("total") or 0)
		correct = int(row.get("correct") or 0)
		items.append(
			{
				"date": t.date.isoformat(),
				"target": int(t.target_questions),
				"answered": int(t.answered_questions),
				"rewarded": bool(t.rewarded),
				"total_attempts": total,
				"correct": correct,
				"ended": t.date < today or bool(t.rewarded) or int(t.answered_questions) >= int(t.target_questions),
			}
		)

	return JsonResponse({"items": items})


@api_login_required
def quiz_history_detail(request: HttpRequest, date_str: str) -> JsonResponse:
	"""Detailed report for a quiz day (answered report + analysis)."""

	user: User = request.user  # type: ignore[assignment]
	try:
		from datetime import date

		day = date.fromisoformat(date_str)
	except Exception:
		return JsonResponse({"detail": "Invalid date"}, status=400)

	attempts = (
		MondaiAnswerAttempt.objects.select_related("mondai_question")
		.filter(user=user, date=day)
		.order_by("created_at")
	)

	correct_count = 0
	items: list[dict] = []
	for a in attempts:
		q = a.mondai_question
		options = {
			"A": q.option_a,
			"B": q.option_b,
			"C": q.option_c,
			"D": q.option_d,
		}
		selected = (a.selected or "").upper()
		correct_letter = (q.correct_answer or "").upper()
		selected_text = options.get(selected)
		correct_text = options.get(correct_letter)
		if a.correct:
			correct_count += 1
		items.append(
			{
				"question_id": q.id,
				"prompt": q.prompt,
				"options": options,
				"selected": selected,
				"selected_text": selected_text,
				"correct": bool(a.correct),
				"correct_answer": correct_letter,
				"correct_text": correct_text,
			}
		)

	total = attempts.count()
	accuracy = (correct_count / total) if total else 0.0
	task = DailyQuizTask.objects.filter(user=user, date=day).first()

	return JsonResponse(
		{
			"date": day.isoformat(),
			"summary": {
				"total": int(total),
				"correct": int(correct_count),
				"accuracy": accuracy,
				"target": int(getattr(task, "target_questions", 0) or 0),
				"answered": int(getattr(task, "answered_questions", 0) or 0),
				"rewarded": bool(getattr(task, "rewarded", False)),
			},
			"items": items,
		}
	)


@api_login_required
def submit_mondai_answer(request: HttpRequest) -> JsonResponse:
	if request.method != "POST":
		return JsonResponse({"detail": "POST required"}, status=405)

	user: User = request.user  # type: ignore[assignment]
	today = timezone.localdate()
	try:
		payload = json.loads(request.body.decode("utf-8"))
	except json.JSONDecodeError:
		return JsonResponse({"detail": "Invalid JSON"}, status=400)

	question_id = payload.get("question_id")
	selected = (payload.get("selected") or "").strip().upper()
	if not question_id or selected not in {"A", "B", "C", "D"}:
		return JsonResponse({"detail": "question_id and selected(A-D) required"}, status=400)

	try:
		q = get_object_or_404(MondaiQuestion.objects.select_related("mondai"), pk=question_id)
	except (OperationalError, ProgrammingError):
		return _schema_out_of_date_response()
	if q.mondai.status != Mondai.Status.APPROVED:
		return JsonResponse({"detail": "Question not available"}, status=403)

	# Ensure question is within the current week window.
	if not (q.mondai.week_start_date and q.mondai.week_end_date and q.mondai.week_start_date <= today <= q.mondai.week_end_date):
		return JsonResponse({"detail": "Not in current week"}, status=400)

	is_correct = selected == q.correct_answer
	options = {
		"A": q.option_a,
		"B": q.option_b,
		"C": q.option_c,
		"D": q.option_d,
	}
	correct_letter = (q.correct_answer or "").strip().upper()
	correct_text = options.get(correct_letter)

	# Record attempt (idempotent per question/day)
	attempt, created = MondaiAnswerAttempt.objects.get_or_create(
		user=user,
		mondai_question=q,
		date=today,
		defaults={"selected": selected, "correct": is_correct},
	)
	if not created:
		return JsonResponse(
			{
				"correct": attempt.correct,
				"already_answered": True,
				"correct_answer": correct_letter,
				"correct_text": correct_text,
			}
		)

	# Update streak and XP
	if is_correct:
		award_xp(user_id=user.pk, points=1, reason="mondai_correct")

	# Update daily task
	task, _ = DailyQuizTask.objects.get_or_create(user=user, date=today)
	DailyQuizTask.objects.filter(pk=task.pk).update(answered_questions=F("answered_questions") + 1)
	task.refresh_from_db()

	reward_awarded = False
	if not task.rewarded and task.answered_questions >= task.target_questions:
		DailyQuizTask.objects.filter(pk=task.pk, rewarded=False).update(rewarded=True)
		# Reward XP for completion.
		award_xp(user_id=user.pk, points=25, reason="daily_task_completed")
		reward_awarded = True

	remaining = max(0, int(task.target_questions) - int(task.answered_questions))

	# Streak: award only when accuracy >= 75% (can be achieved via retake practice too).
	correct_count = MondaiAnswerAttempt.objects.filter(user=user, date=today, correct=True).count()
	total_count = MondaiAnswerAttempt.objects.filter(user=user, date=today).count()
	accuracy = (float(correct_count) / float(total_count)) if total_count else 0.0
	accuracy_percent = int(round(accuracy * 100))
	streak_required_percent = 75
	streak_eligible = bool(total_count >= int(task.target_questions) and accuracy >= 0.75)
	streak_awarded = False
	if streak_eligible:
		last = User.objects.only("id", "last_study_date").filter(pk=user.pk).first()
		already_today = bool(last and last.last_study_date == today)
		touch_study_streak(user_id=user.pk, today=today)
		streak_awarded = not already_today

	return JsonResponse(
		{
			"correct": is_correct,
			"already_answered": False,
			"correct_answer": correct_letter,
			"correct_text": correct_text,
			"task": {
				"target": task.target_questions,
				"answered": task.answered_questions,
				"remaining": remaining,
				"rewarded": bool(task.rewarded),
				"reward_awarded": reward_awarded,
			},
			"streak": {
				"accuracy_percent": accuracy_percent,
				"required_percent": streak_required_percent,
				"eligible": streak_eligible,
				"awarded": streak_awarded,
			},
		}
	)


@api_login_required
def protected_video(request: HttpRequest, weekly_content_id: int) -> HttpResponse:
	"""Saturday-only gated video access (paid users only)."""

	user: User = request.user  # type: ignore[assignment]
	if user.subscription_status != User.SubscriptionStatus.PAID:
		raise PermissionDenied("Paid subscription required")

	today = timezone.localdate()
	if today.weekday() != 5:  # Monday=0 ... Saturday=5
		raise PermissionDenied("Video only available on Saturday")

	weekly = get_object_or_404(WeeklyContent, pk=weekly_content_id, is_approved=True)
	if weekly.level != user.target_level:
		raise PermissionDenied("Not your level")

	if request.method != "GET":
		return JsonResponse({"detail": "GET required"}, status=405)

	return FileResponse(weekly.video_file.open("rb"), as_attachment=False)


@api_login_required
def mark_video_completed(request: HttpRequest, weekly_content_id: int) -> JsonResponse:
	"""Called by frontend on `onEnded` after Saturday video finishes."""

	if request.method != "POST":
		return JsonResponse({"detail": "POST required"}, status=405)

	user: User = request.user  # type: ignore[assignment]
	touch_study_streak(user_id=user.pk, today=timezone.localdate())
	weekly = get_object_or_404(WeeklyContent, pk=weekly_content_id, is_approved=True)
	if weekly.level != user.target_level:
		raise PermissionDenied("Not your level")

	_, created = VideoCompletion.objects.get_or_create(user=user, weekly_content=weekly)
	return JsonResponse({"completed": True, "created": created})


@api_login_required
def generate_certificate(request: HttpRequest) -> HttpResponse:
	"""Generate a PDF certificate when all weeks in user's level are complete."""

	user: User = request.user  # type: ignore[assignment]

	all_weeks = WeeklyContent.objects.filter(level=user.target_level, is_approved=True)
	total = all_weeks.count()
	if total == 0:
		return JsonResponse({"detail": "No approved content for your level"}, status=400)

	completed = VideoCompletion.objects.filter(user=user, weekly_content__level=user.target_level).count()
	if completed < total:
		return JsonResponse(
			{"detail": "Not complete yet", "completed": completed, "required": total},
			status=400,
		)

	buffer = BytesIO()
	pdf = canvas.Canvas(buffer, pagesize=A4)
	width, height = A4

	pdf.setTitle("Japanese LMS Certificate")
	pdf.setFont("Helvetica-Bold", 22)
	pdf.drawCentredString(width / 2, height - 120, "Certificate of Completion")
	pdf.setFont("Helvetica", 14)
	pdf.drawCentredString(width / 2, height - 170, f"This certifies that {user.get_full_name() or user.username}")
	pdf.drawCentredString(width / 2, height - 195, f"has completed level {user.target_level}.")

	pdf.setFont("Helvetica", 11)
	pdf.drawCentredString(width / 2, height - 240, f"Issued: {timezone.localdate().isoformat()}")

	signature_path = getattr(settings, "SENSEI_SIGNATURE_PATH", None)
	try:
		if signature_path and signature_path.exists():
			pdf.drawImage(
				ImageReader(str(signature_path)),
				width / 2 - 80,
				110,
				width=160,
				height=60,
				mask='auto',
			)
			pdf.setFont("Helvetica", 10)
			pdf.drawCentredString(width / 2, 95, "Sensei")
	except Exception:
		pass

	pdf.showPage()
	pdf.save()

	buffer.seek(0)
	return FileResponse(buffer, as_attachment=True, filename="certificate.pdf")


@api_login_required
def colleges_list(request: HttpRequest) -> JsonResponse:
	qs = College.objects.all().order_by('name')
	data = [{'id': c.id, 'name': c.name, 'city': c.city} for c in qs]
	return JsonResponse({'colleges': data})


def colleges_public(request: HttpRequest) -> JsonResponse:
	"""Public colleges endpoint for registration dropdown.

	Supports optional query param: ?q=... (search by code/name/city).
	"""
	q = (request.GET.get("q") or "").strip()
	qs = College.objects.all()
	if q:
		qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q) | Q(city__icontains=q))
	qs = qs.order_by("name")[:200]
	data = [{"id": c.id, "code": c.code, "name": c.name, "city": c.city} for c in qs]
	return JsonResponse({"colleges": data})


def mondai_detail(request: HttpRequest, public_id: str) -> JsonResponse:
	"""Return JSON representation of a Mondai for frontend viewers.

	Public mondais with status APPROVED are returned; Sensei/Shitsumon users can fetch their own drafts.
	"""
	user = request.user  # may be AnonymousUser

	mondai = get_object_or_404(Mondai, public_id=public_id)

	# If not approved, only the creator or staff can view it.
	if mondai.status != Mondai.Status.APPROVED:
		if not request.user.is_authenticated:
			return JsonResponse({'detail': 'Authentication required'}, status=401)
		if mondai.created_by_id != user.pk and not user.is_staff:
			return JsonResponse({'detail': 'Not allowed'}, status=403)

	def _q_to_payload(q):
		return {
			'id': q.id,
			'prompt': q.prompt,
			'option_a': q.option_a,
			'option_b': q.option_b,
			'option_c': q.option_c,
			'option_d': q.option_d,
			'correct_answer': q.correct_answer,
		}

	data = {
		'public_id': mondai.public_id,
		'name': mondai.name,
		'status': mondai.status,
		'transcript': mondai.transcript,
		'video': mondai.display_video,
		'original_video_url': mondai.video_url or mondai.video_embed_url or None,
		'vocab': [{'term': v.term, 'reading': v.reading, 'meaning': v.meaning} for v in mondai.vocab.all()],
		'questions': [_q_to_payload(q) for q in mondai.questions.all()],
	}

	return JsonResponse({'mondai': data})

# Create your views here.
