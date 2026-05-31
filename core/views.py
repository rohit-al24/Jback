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
	QuizScore,
	ReviewQueue,
	User,
	VideoCompletion,
	WeeklyContent,
	EmailOTP,
)
from course.models import Level, Unit, VocabularyItem, GrammarContent
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
	"""Weekly leaderboard — scoped to the user's college if they have one."""

	user: User = request.user  # type: ignore[assignment]

	from datetime import timedelta

	from django.db.models import Sum
	from django.db.models.functions import Coalesce

	seven_days_ago = timezone.now() - timedelta(days=7)

	# Filter to same college when user has one
	user_college = getattr(request.user, "college_id", None)
	qs = User.objects.filter(is_active=True)
	if user_college:
		qs = qs.filter(college_id=user_college)

	rows = (
		qs.annotate(
			xp_week=Coalesce(
				Sum(
					"xp_events__points",
					filter=Q(xp_events__created_at__gte=seven_days_ago),
				),
				0,
			)
		)
		.select_related("college", "profile")
		.order_by("-xp_week", "-total_points", "-streak_count", "username")
	)

	entries: list[dict] = []
	for idx, u in enumerate(rows[:50], start=1):
		full_name = (u.get_full_name() or u.username).strip()
		initials = "".join([p[:1].upper() for p in full_name.split()[:2]]) or (u.username[:2].upper())
		xp_week = int(getattr(u, "xp_week", 0) or 0)
		profile = getattr(u, "profile", None)
		pic_url = None
		if profile and getattr(profile, "profile_picture", None):
			try:
				pic_url = request.build_absolute_uri(profile.profile_picture.url)
			except Exception:
				pass
		entries.append(
			{
				"rank": idx,
				"id": u.id,
				"name": full_name,
				"display_username": getattr(profile, "display_username", None) or u.username,
				"avatar": initials,
				"level": getattr(u, "target_level", None),
				"streak": int(getattr(u, "streak_count", 0) or 0),
				"points_week": xp_week,
				"points_total": int(getattr(u, "total_points", 0) or 0),
				"college": u.college.name if u.college else None,
				"profile_picture": pic_url,
			}
		)

	college = getattr(user, "college", None)
	return JsonResponse(
		{
			"entries": entries,
			"college_scoped": bool(user_college),
			"college_name": college.name if user_college and college else None,
		}
	)
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


# ─────────────────────────────────────────────────────────────────────────────
# Course System APIs
# ─────────────────────────────────────────────────────────────────────────────

# Map user.target_level ('N5'/'N4') to the exam code stored in the DB ('5'/'4')
_TARGET_LEVEL_TO_EXAM_CODE = {
	'N5': '5',
	'N4': '4',
}


def _filter_vocab_by_user_exam(vocab_qs, user):
	"""Filter a VocabularyItem queryset to items matching the user's exam
	(or untagged items with exam_id=None, which are shown to everyone)."""
	from administration.models import Exam
	target = getattr(user, 'target_level', None)
	exam_code = _TARGET_LEVEL_TO_EXAM_CODE.get(target) if target else None
	if exam_code:
		try:
			exam_obj = Exam.objects.get(code=exam_code)
			return vocab_qs.filter(Q(exam=exam_obj) | Q(exam__isnull=True))
		except Exam.DoesNotExist:
			pass
	return vocab_qs


@api_login_required
def exams_list(request: HttpRequest) -> JsonResponse:
	"""Return all active exams; each includes the level_id it maps to (if any)."""
	from administration.models import Exam
	exams = Exam.objects.filter(is_active=True).order_by('order', 'code')
	data = []
	for exam in exams:
		level = exam.levels.filter(is_active=True).order_by('order', 'level_number').first()
		data.append({
			'id': exam.id,
			'code': exam.code,
			'name': exam.name,
			'description': exam.description,
			'level_id': level.id if level else None,
		})
	return JsonResponse({'exams': data})


@api_login_required
def levels_list(request: HttpRequest) -> JsonResponse:
	"""Return list of all active levels."""
	levels = Level.objects.filter(is_active=True).order_by('order', 'level_number')
	data = [
		{
			'id': level.id,
			'level_number': level.level_number,
			'name': level.name or f'Level {level.level_number}',
			'description': level.description,
		}
		for level in levels
	]
	return JsonResponse({'levels': data})


@api_login_required
def units_list(request: HttpRequest, level_id: int) -> JsonResponse:
	"""Return list of units for a given level."""
	level = get_object_or_404(Level, pk=level_id, is_active=True)
	units = level.units.filter(is_active=True).order_by('order', 'unit_number')
	from course.models import GrammarLearnItem
	
	data = [
		{
			'id': unit.id,
			'unit_number': unit.unit_number,
			'name': unit.name or f'Unit {unit.unit_number}',
			'description': unit.description,
			'vocab_count': unit.vocabulary.count(),
			'grammar_count': (lambda learn_count, legacy_count: learn_count if learn_count > 0 else legacy_count)(
				GrammarLearnItem.objects.filter(unit=unit).count(),
				unit.grammar.count(),
			),
		}
		for unit in units
	]
	return JsonResponse({
		'level': {
			'id': level.id,
			'level_number': level.level_number,
			'name': level.name or f'Level {level.level_number}',
			'exam_code': (f"N{level.exam.code}" if level.exam and str(level.exam.code).isdigit() else (level.exam.code if level.exam else None)),
			'exam_name': level.exam.name if level.exam else None,
		},
		'units': data
	})


@api_login_required
def vocabulary_study(request: HttpRequest, unit_id: int) -> JsonResponse:
	"""Return vocabulary items for study mode filtered by the user's exam level.

	Each item includes hint metadata:
	  my_hint: str | null
	  friends_hints: [{user_id, display_name}]  (friends who have a hint for this word)
	"""
	unit = get_object_or_404(Unit, pk=unit_id, is_active=True)
	vocab_qs = _filter_vocab_by_user_exam(unit.vocabulary.all(), request.user).order_by('order', 'id')
	vocab_list = list(vocab_qs)
	vocab_ids = [v.id for v in vocab_list]

	# Fetch my hints in bulk
	from hints.models import VocabularyHint
	my_hints: dict = {
		h.vocabulary_item_id: h.hint_text
		for h in VocabularyHint.objects.filter(user=request.user, vocabulary_item_id__in=vocab_ids)
	}

	# Fetch friends who have hints for these vocab items
	from django.db.models import Q as _Q
	from social.models import Friendship
	uid = request.user.id
	friendships = Friendship.objects.filter(_Q(user1_id=uid) | _Q(user2_id=uid))
	friend_ids = [f.user2_id if f.user1_id == uid else f.user1_id for f in friendships]

	from collections import defaultdict
	friends_hints_by_vocab: dict = defaultdict(list)
	if friend_ids:
		friends_qs = (
			VocabularyHint.objects
			.filter(vocabulary_item_id__in=vocab_ids, user_id__in=friend_ids)
			.select_related('user', 'user__profile')
		)
		for h in friends_qs:
			profile = getattr(h.user, 'profile', None)
			display = getattr(profile, 'display_username', None) or h.user.first_name or h.user.username
			pic_url = None
			if profile and getattr(profile, 'profile_picture', None):
				try:
					pic_url = request.build_absolute_uri(profile.profile_picture.url)
				except Exception:
					pass
			friends_hints_by_vocab[h.vocabulary_item_id].append({
				'user_id': h.user_id,
				'display_name': display,
				'profile_picture': pic_url,
			})

	data = [
		{
			'id': item.id,
			'target': item.target,
			'correct': item.correct,
			'my_hint': my_hints.get(item.id),
			'friends_hints': friends_hints_by_vocab.get(item.id, []),
		}
		for item in vocab_list
	]

	return JsonResponse({
		'unit': {
			'id': unit.id,
			'unit_number': unit.unit_number,
			'name': unit.name or f'Unit {unit.unit_number}',
			'level': unit.level.name or f'Level {unit.level.level_number}',
		},
		'vocabulary': data
	})


@api_login_required
def vocabulary_quiz(request: HttpRequest, unit_id: int) -> JsonResponse:
	"""Return shuffled quiz questions filtered by the user's exam level."""
	unit = get_object_or_404(Unit, pk=unit_id, is_active=True)
	vocab = _filter_vocab_by_user_exam(unit.vocabulary.all(), request.user).order_by('order', 'id')
	
	questions = []
	for item in vocab:
		# Shuffle the four option values, then assign them to slots A-D
		values = [item.correct, item.wrong1, item.wrong2, item.wrong3]
		random.shuffle(values)
		keys = ['A', 'B', 'C', 'D']
		shuffled_options = dict(zip(keys, values))

		# The correct answer is whichever slot now holds item.correct
		correct_answer_key = next(k for k, v in shuffled_options.items() if v == item.correct)

		questions.append({
			'id': item.id,
			'target': item.target,
			'options': shuffled_options,
			'correct_answer': correct_answer_key,
		})
	
	return JsonResponse({
		'unit': {
			'id': unit.id,
			'unit_number': unit.unit_number,
			'name': unit.name or f'Unit {unit.unit_number}',
			'level': unit.level.name or f'Level {unit.level.level_number}',
		},
		'questions': questions
	})


@api_login_required
def grammar_view(request: HttpRequest, unit_id: int) -> JsonResponse:
	"""Return grammar content for a unit."""
	unit = get_object_or_404(Unit, pk=unit_id, is_active=True)
	grammar = unit.grammar.all().order_by('order', 'id')
	
	data = [
		{
			'id': item.id,
			'title': item.title,
			'content': item.content,
		}
		for item in grammar
	]
	
	return JsonResponse({
		'unit': {
			'id': unit.id,
			'unit_number': unit.unit_number,
			'name': unit.name or f'Unit {unit.unit_number}',
			'level': unit.level.name or f'Level {unit.level.level_number}',
		},
		'grammar': data
	})


@api_login_required
def grammar_learn_view(request: HttpRequest, unit_id: int) -> JsonResponse:
	"""Return structured Grammar Learn sections for a unit.

	GET params:
	  ?exam_code=N5_G01 (prefix match supported, e.g. exam_code=N5)
	"""
	from course.models import GrammarLearnItem

	unit = get_object_or_404(Unit, pk=unit_id, is_active=True)
	exam_code = (request.GET.get('exam_code') or '').strip().upper()

	qs = GrammarLearnItem.objects.filter(unit=unit)
	if exam_code:
		qs = qs.filter(exam_code__startswith=exam_code)

	items = list(qs.order_by('topic_order', 'id'))

	# Group rows that share the same topic_order into a single "card".
	# The first row in each group carries the card-level fields; subsequent
	# rows contribute extra examples.
	from collections import OrderedDict
	cards: OrderedDict = OrderedDict()
	for it in items:
		key = it.topic_order
		if key not in cards:
			cards[key] = {
				'id': it.id,
				'exam_level': it.exam_level,
				'exam_code': it.exam_code,
				'topic_order': it.topic_order,
				'title': it.title,
				'main_character': it.main_character,
				'logic_formula': it.logic_formula,
				'explanation': it.explanation,
				'examples': [],
				'visual_type': it.visual_type,
				'pakka_tip': it.pakka_tip,
			}
		if it.example_jp:
			cards[key]['examples'].append({'jp': it.example_jp, 'en': it.example_en})

	data = list(cards.values())

	return JsonResponse({
		'unit': {
			'id': unit.id,
			'unit_number': unit.unit_number,
			'name': unit.name or f'Unit {unit.unit_number}',
			'level': unit.level.name or f'Level {unit.level.level_number}',
		},
		'exam_code': exam_code,
		'items': data,
	})


@api_login_required
def grammar_pakka_session(request: HttpRequest, unit_id: int) -> JsonResponse:
	"""Return Grammar Pakka items (Blueprint/Builder/Heavy Loop/Beast Mode) for a unit.

	GET params:
	  ?exam_code=N5_G01 (optional; prefix match supported, e.g. exam_code=N5)
	"""
	from course.models import GrammarPakkaItem

	unit = get_object_or_404(Unit, pk=unit_id, is_active=True)
	exam_code = (request.GET.get('exam_code') or '').strip().upper()

	qs = GrammarPakkaItem.objects.filter(unit=unit)
	if exam_code:
		qs = qs.filter(exam_code__startswith=exam_code)
	items = list(qs.order_by('order', 'id'))

	def _split_blocks(value: str) -> list[str]:
		parts = [p.strip() for p in (value or '').split(',')]
		return [p for p in parts if p]

	data = [
		{
			'id': it.id,
			'step_type': it.step_type,
			'exam_level': it.exam_level,
			'exam_code': it.exam_code,
			'logic_formula': it.logic_formula,
			'english_prompt': it.english_prompt,
			'correct_sentence': it.correct_sentence,
			'word_blocks': _split_blocks(it.word_blocks),
			'particle_target': it.particle_target,
			'distractors': _split_blocks(getattr(it, 'distractors', '')),
			'explanation_hint': it.explanation_hint,
			'order': it.order,
		}
		for it in items
	]

	return JsonResponse({
		'unit': {
			'id': unit.id,
			'unit_number': unit.unit_number,
			'name': unit.name or f'Unit {unit.unit_number}',
			'level': unit.level.name or f'Level {unit.level.level_number}',
		},
		'exam_code': exam_code,
		'items': data,
	})


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for Adaptive Quiz
# ─────────────────────────────────────────────────────────────────────────────

def _build_adaptive_options(vocab, all_vocab: list, states: dict, mode: str) -> dict:
	"""Build answer options using smart distractor logic.

	Normal mode: prompt=Hiragana, options=English meanings.
	Flip mode:   prompt=English, options=Hiragana targets.

	Distractor priority (normal): weak words first, then phonetically-similar
	(same first kana), then any other unit words, then vocab's own wrong* fields.
	Distractor priority (flip): same logic but for hiragana targets.
	"""
	import random

	is_flip = mode in ('flip', 'speed_flip')
	target_start = (vocab.target or '')[:1]

	if is_flip:
		# Options are hiragana — correct = vocab.target, wrongs = other hiragana
		correct_val = vocab.target
		prompt_val  = vocab.correct

		weak_pool, phonetic_pool, other_pool = [], [], []
		for v in all_vocab:
			if v.id == vocab.id:
				continue
			st = states.get(v.id)
			if st and st.is_weak:
				weak_pool.append(v.target)
			elif (v.target or '')[:1] == target_start:
				phonetic_pool.append(v.target)
			else:
				other_pool.append(v.target)
	else:
		# Options are English — correct = vocab.correct, wrongs = other English
		correct_val = vocab.correct
		prompt_val  = vocab.target

		weak_pool, phonetic_pool, other_pool = [], [], []
		for v in all_vocab:
			if v.id == vocab.id:
				continue
			st = states.get(v.id)
			if st and st.is_weak:
				weak_pool.append(v.correct)
			elif (v.target or '')[:1] == target_start:
				phonetic_pool.append(v.correct)
			else:
				other_pool.append(v.correct)

	# Fill from own wrong fields as fallback
	own_wrongs = [vocab.wrong1, vocab.wrong2, vocab.wrong3]

	chosen: list[str] = []
	seen: set[str] = {correct_val}
	for pool in (weak_pool, phonetic_pool, other_pool, own_wrongs):
		random.shuffle(pool)
		for d in pool:
			if d and d not in seen:
				chosen.append(d)
				seen.add(d)
			if len(chosen) == 3:
				break
		if len(chosen) == 3:
			break

	# Pad if not enough unique distractors
	idx = 1
	while len(chosen) < 3:
		placeholder = f'—{idx}—'
		if placeholder not in seen:
			chosen.append(placeholder)
		idx += 1

	all_choices = [correct_val] + chosen[:3]
	random.shuffle(all_choices)

	letters = ['A', 'B', 'C', 'D']
	correct_answer = letters[all_choices.index(correct_val)]

	return {
		'prompt': prompt_val,
		'choices': {l: v for l, v in zip(letters, all_choices)},
		'correct_answer': correct_answer,
	}


def _get_surprise_review_items(user, exclude_unit_id: int) -> list[dict]:
	"""Return up to 3 overdue items from units OTHER than current unit."""
	from course.models import UserVocabState

	now = timezone.now()
	overdue = (
		UserVocabState.objects
		.select_related('vocab_item', 'vocab_item__unit')
		.filter(user=user, due_at__lte=now, mastered=False)
		.exclude(vocab_item__unit_id=exclude_unit_id)
		.order_by('due_at')[:3]
	)

	items = []
	for st in overdue:
		v = st.vocab_item
		timer_map = {'normal': 10, 'flip': 5, 'speed': 2}
		opts = _build_adaptive_options(v, [], {}, st.mode)
		items.append({
			'vocab_id': v.id,
			'prompt': opts['prompt'],
			'prompt_type': 'english' if st.mode in ('flip', 'speed_flip') else 'hiragana',
			'options': opts['choices'],
			'correct_answer': opts['correct_answer'],
			'mode': st.mode,
			'timer_seconds': timer_map.get(st.mode, 10),
			'streak_correct': st.streak_correct,
			'lapses': st.lapses,
			'is_weak': bool(st.is_weak),
			'mastered': False,
			'is_surprise': True,
			'unit_name': v.unit.name or f'Unit {v.unit.unit_number}',
		})
	return items


# ─────────────────────────────────────────────────────────────────────────────
# Adaptive Quiz APIs
# ─────────────────────────────────────────────────────────────────────────────

@api_login_required
def adaptive_quiz_session(request: HttpRequest, unit_id: int) -> JsonResponse:
	"""Build an adaptive quiz session for a unit.

	Returns vocab items sorted by learning priority with mode, timer, and smart options.
	GET params:
	  ?exam=N5  (optional)
	"""
	user: User = request.user  # type: ignore[assignment]
	exam_code = (request.GET.get('exam') or '').strip().upper()

	unit = get_object_or_404(Unit, pk=unit_id, is_active=True)

	vocab_qs = _filter_vocab_by_user_exam(VocabularyItem.objects.filter(unit=unit), user)
	# Allow an explicit ?exam= override to narrow further (e.g. admin testing)
	if exam_code:
		from administration.models import Exam
		try:
			exam_obj = Exam.objects.get(code=exam_code)
			vocab_qs = vocab_qs.filter(Q(exam=exam_obj) | Q(exam__isnull=True))
		except Exam.DoesNotExist:
			pass
	vocab_list = list(vocab_qs.order_by('order', 'id'))

	if not vocab_list:
		return JsonResponse({'detail': 'No vocabulary found for this unit/exam'}, status=404)

	vocab_ids = [v.id for v in vocab_list]

	from course.models import UserVocabState
	states: dict = {
		s.vocab_item_id: s
		for s in UserVocabState.objects.filter(user=user, vocab_item_id__in=vocab_ids)
	}

	now = timezone.now()
	timer_map = {'normal': 10, 'flip': 5, 'speed': 2}

	session_items = []
	mastered_count = 0
	for vocab in vocab_list:
		st = states.get(vocab.id)
		if st:
			is_overdue = bool(st.due_at and st.due_at <= now)
			if st.mastered and not is_overdue:
				mastered_count += 1
				continue  # already mastered & not due for surprise review
			if is_overdue:
				priority = 10
			elif st.is_weak:
				priority = 7
			elif st.streak_correct == 0 and st.lapses == 0:
				priority = 4  # unseen but state exists
			else:
				priority = 2
			mode   = st.mode
			streak = st.streak_correct
			lapses = st.lapses
			mastered = st.mastered
		else:
			priority = 4  # unseen
			mode     = 'normal'
			streak   = 0
			lapses   = 0
			mastered  = False

		opts = _build_adaptive_options(vocab, vocab_list, states, mode)
		session_items.append({
			'vocab_id':      vocab.id,
			'prompt':        opts['prompt'],
			'prompt_type':   'english' if mode in ('flip',) else 'hiragana',
			'options':       opts['choices'],
			'correct_answer': opts['correct_answer'],
			'mode':          mode,
			'timer_seconds': timer_map.get(mode, 10),
			'streak_correct': streak,
			'lapses':        lapses,
			'is_weak':       bool(st.is_weak) if st else False,
			'mastered':      mastered,
			'priority':      priority,
		})

	# Sort: highest priority first
	session_items.sort(key=lambda x: -x['priority'])

	total = len(vocab_list)
	mastery_pct = int(mastered_count / total * 100) if total else 0

	# Surprise reviews from other units
	surprise = _get_surprise_review_items(user, unit.id)

	return JsonResponse({
		'unit': {
			'id': unit.id,
			'unit_number': unit.unit_number,
			'name': unit.name or f'Unit {unit.unit_number}',
			'level': unit.level.name or f'Level {unit.level.level_number}',
		},
		'exam': exam_code,
		'items': session_items,
		'surprise_review': surprise,
		'total_vocab': total,
		'mastered_count': mastered_count,
		'mastery_percent': mastery_pct,
	})


@api_login_required
def vocab_state_submit(request: HttpRequest) -> JsonResponse:
	"""Submit a vocabulary quiz answer and update the user's learning state.

	POST body: { vocab_id, correct (bool), mode }
	Returns updated state + next recommended timer.
	"""
	if request.method != 'POST':
		return JsonResponse({'detail': 'POST required'}, status=405)

	user: User = request.user  # type: ignore[assignment]
	try:
		payload = json.loads(request.body.decode('utf-8'))
	except Exception:
		return JsonResponse({'detail': 'Invalid JSON'}, status=400)

	vocab_id = payload.get('vocab_id')
	correct  = bool(payload.get('correct', False))
	mode     = (payload.get('mode') or 'normal').strip()

	if not vocab_id:
		return JsonResponse({'detail': 'vocab_id required'}, status=400)

	from course.models import UserVocabState, VocabularyItem as VI
	try:
		vocab = VI.objects.get(id=vocab_id)
	except VI.DoesNotExist:
		return JsonResponse({'detail': 'Vocab not found'}, status=404)

	st, _ = UserVocabState.objects.get_or_create(
		user=user,
		vocab_item=vocab,
	)

	now = timezone.now()
	st.last_answered_at = now

	if correct:
		st.streak_correct += 1
		st.is_weak = False

		if mode == 'normal':
			st.streak_normal += 1

		# Mode progression
		MODE_NORMAL = UserVocabState.Mode.NORMAL
		MODE_FLIP   = UserVocabState.Mode.FLIP
		MODE_SPEED  = UserVocabState.Mode.SPEED

		if mode == 'normal' and st.streak_normal >= 3:
			# Promote to Flip mode
			st.mode = MODE_FLIP
			st.streak_correct = 0  # reset streak for new challenge
		elif mode == 'flip' and st.streak_correct >= 2:
			# Promote to Speed mode
			st.mode = MODE_SPEED
			st.streak_correct = 0
		elif mode == 'speed' and st.streak_correct >= 2:
			# Mastered!
			st.mastered = True
			award_xp(user_id=user.pk, points=20, reason='vocab_mastered')

		# Extend spaced-repetition interval
		from datetime import timedelta as _td
		st.half_life_days = min(float(st.half_life_days) * 2.0, 365.0)
		st.due_at = now + _td(days=float(st.half_life_days))

		# XP per mode
		xp_by_mode = {'normal': 2, 'flip': 5, 'speed': 10}
		award_xp(user_id=user.pk, points=xp_by_mode.get(mode, 2), reason='vocab_correct')

	else:
		# Wrong answer
		st.lapses        += 1
		st.streak_correct = 0
		st.is_weak        = True

		# Downgrade on wrong in advanced modes
		if mode == 'speed':
			st.mode = UserVocabState.Mode.FLIP
			# Keep some progress: streak_normal stays so flip is still unlocked
		elif mode == 'flip':
			st.mode = UserVocabState.Mode.NORMAL
			st.streak_normal = max(0, int(st.streak_normal) - 1)

		st.due_at         = now  # immediately due (overdue)
		st.half_life_days = max(0.5, float(st.half_life_days) * 0.5)

	st.save()

	timer_map = {'normal': 10, 'flip': 5, 'speed': 2}
	return JsonResponse({
		'vocab_id':       vocab_id,
		'correct':        correct,
		'streak_correct': st.streak_correct,
		'streak_normal':  st.streak_normal,
		'lapses':         st.lapses,
		'is_weak':        st.is_weak,
		'mode':           st.mode,
		'timer_seconds':  timer_map.get(st.mode, 10),
		'mastered':       st.mastered,
		'due_at':         st.due_at.isoformat() if st.due_at else None,
	})


@api_login_required
def unit_mastery(request: HttpRequest, unit_id: int) -> JsonResponse:
	"""Return mastery breakdown for the Growth Visualizer.

	Each stage is weighted for a smooth 0–100% growth bar:
	  unseen=0, normal=15, flip=50, speed=80, mastered=100
	"""
	user: User = request.user  # type: ignore[assignment]
	exam_code = (request.GET.get('exam') or '').strip().upper()

	unit = get_object_or_404(Unit, pk=unit_id, is_active=True)
	vocab_qs = VocabularyItem.objects.filter(unit=unit)
	if exam_code:
		from administration.models import Exam
		try:
			exam_obj = Exam.objects.get(code=exam_code)
			vocab_qs = vocab_qs.filter(exam=exam_obj)
		except Exam.DoesNotExist:
			pass

	total = vocab_qs.count()
	if total == 0:
		return JsonResponse({'mastery_percent': 0, 'mastered': 0, 'total': 0, 'breakdown': {}})

	vocab_ids = list(vocab_qs.values_list('id', flat=True))
	from course.models import UserVocabState
	qs = UserVocabState.objects.filter(user=user, vocab_item_id__in=vocab_ids)

	n_mastered = qs.filter(mastered=True).count()
	n_speed    = qs.filter(mode='speed', mastered=False).count()
	n_flip     = qs.filter(mode='flip', mastered=False).count()
	n_normal   = qs.filter(mode='normal', mastered=False).count()
	n_unseen   = total - qs.count()

	score = (
		n_mastered * 100 +
		n_speed    * 80 +
		n_flip     * 50 +
		n_normal   * 15 +
		n_unseen   * 0
	)
	mastery_pct = int(score / total) if total else 0

	return JsonResponse({
		'unit_id':        unit_id,
		'exam':           exam_code,
		'total':          total,
		'mastered':       n_mastered,
		'mastery_percent': mastery_pct,
		'breakdown': {
			'mastered': n_mastered,
			'speed':    n_speed,
			'flip':     n_flip,
			'normal':   n_normal,
			'unseen':   n_unseen,
		},
	})


@api_login_required
def update_growth_theme(request: HttpRequest) -> JsonResponse:
	"""POST { growth_theme: 'bodybuilder'|'tree'|'city' } to set user's visualizer theme."""
	if request.method != 'POST':
		return JsonResponse({'detail': 'POST required'}, status=405)

	try:
		payload = json.loads(request.body.decode('utf-8'))
	except Exception:
		return JsonResponse({'detail': 'Invalid JSON'}, status=400)

	theme = (payload.get('growth_theme') or '').strip().lower()
	valid = {'bodybuilder', 'tree', 'city'}
	if theme not in valid:
		return JsonResponse({'detail': f'Invalid theme. Choose from: {", ".join(sorted(valid))}'}, status=400)

	user: User = request.user  # type: ignore[assignment]
	User.objects.filter(pk=user.pk).update(growth_theme=theme)
	return JsonResponse({'growth_theme': theme})


# ── Quiz Score Save ───────────────────────────────────────────────────────────

@api_login_required
def save_quiz_score(request: HttpRequest) -> JsonResponse:
	"""POST { unit_id, quiz_type, score, total } to save a quiz result and award XP.

	XP is only awarded when:
	- percentage >= 75
	- User has not previously reached 75%+ for this quiz_type + unit combination
	  (if they already passed 75%, only incremental improvement earns XP)
	"""
	if request.method != 'POST':
		return JsonResponse({'detail': 'POST required'}, status=405)

	try:
		payload = json.loads(request.body.decode('utf-8'))
	except Exception:
		return JsonResponse({'detail': 'Invalid JSON'}, status=400)

	unit_id = payload.get('unit_id')
	quiz_type = (payload.get('quiz_type') or 'vocab').strip()
	score = int(payload.get('score', 0))
	total = int(payload.get('total', 0))

	valid_types = {'vocab', 'grammar', 'pakka', 'daily_revise'}
	if quiz_type not in valid_types:
		return JsonResponse({'detail': 'Invalid quiz_type'}, status=400)

	unit = None
	if unit_id:
		from course.models import Unit as CourseUnit
		unit = CourseUnit.objects.filter(pk=unit_id).first()

	percentage = round((score / total) * 100) if total > 0 else 0

	# XP rates per quiz type
	xp_rate_map = {
		'vocab': 3,
		'grammar': 4,
		'pakka': 5,
		'daily_revise': 3,
	}
	xp_per_correct = xp_rate_map.get(quiz_type, 2)

	# Only award XP for scores >= 75%, and only for new progress beyond previous best
	xp_earned = 0
	already_passed = False
	passed_75 = percentage >= 75

	if passed_75:
		prev_best = (
			QuizScore.objects
			.filter(user=request.user, quiz_type=quiz_type, unit=unit, percentage__gte=75)
			.order_by('-score')
			.first()
		)
		if prev_best is None:
			# First time reaching 75%+ — award full XP
			xp_earned = score * xp_per_correct
		else:
			already_passed = True
			# Award XP only for improvement beyond previous best score
			new_correct = max(0, score - prev_best.score)
			xp_earned = new_correct * xp_per_correct

	qs = QuizScore.objects.create(
		user=request.user,
		unit=unit,
		quiz_type=quiz_type,
		score=score,
		total=total,
		xp_earned=xp_earned,
	)

	if xp_earned > 0:
		award_xp(user_id=request.user.pk, points=xp_earned, reason=f'{quiz_type}_quiz')
		touch_study_streak(user_id=request.user.pk, today=timezone.localdate())

	return JsonResponse({
		'saved': True,
		'percentage': percentage,
		'xp_earned': xp_earned,
		'score_id': qs.id,
		'passed_75': passed_75,
		'already_passed': already_passed,
	})


@api_login_required
def quiz_scores_history(request: HttpRequest) -> JsonResponse:
	"""Return last 20 quiz scores for the current user."""
	scores = QuizScore.objects.filter(user=request.user).select_related('unit').order_by('-created_at')[:20]
	data = [
		{
			'id': s.id,
			'quiz_type': s.quiz_type,
			'unit': s.unit.name if s.unit else None,
			'score': s.score,
			'total': s.total,
			'percentage': s.percentage,
			'xp_earned': s.xp_earned,
			'created_at': s.created_at.isoformat(),
		}
		for s in scores
	]
	return JsonResponse({'scores': data})


# ── Daily Revise API ──────────────────────────────────────────────────────────

@api_login_required
def daily_revise_units(request: HttpRequest) -> JsonResponse:
	"""Return units where user scored >= 75% in vocab or grammar quiz.
	Also returns count of pending wrong-answer review items due today.
	"""
	user: User = request.user  # type: ignore[assignment]
	from course.models import Unit as CourseUnit
	from .models import DailyReviseQuestion
	import datetime

	today = datetime.date.today()

	# Find units with >= 75% quiz score
	scored_units = (
		QuizScore.objects
		.filter(user=user, percentage__gte=75)
		.values_list('unit_id', flat=True)
		.distinct()
	)
	units = CourseUnit.objects.filter(pk__in=scored_units, is_active=True).select_related('level')

	data = [
		{
			'id': u.id,
			'unit_number': u.unit_number,
			'name': u.name or f'Unit {u.unit_number}',
			'level': u.level.name if u.level else '',
		}
		for u in units
	]

	# Count of pending wrong-answer items due today
	pending_wrongs = DailyReviseQuestion.objects.filter(
		user=user, is_active=True, next_review_date__lte=today
	).count()

	return JsonResponse({'units': data, 'pending_wrongs': pending_wrongs})


@api_login_required
def daily_revise_quiz(request: HttpRequest) -> JsonResponse:
	"""Return a randomized quiz pool for daily revision.

	Query params:
	  - mode: 'all' | 'vocab' | 'grammar' (default 'all')
	  - include_wrongs: '1' (default) — include wrong-answer review items
	"""
	user: User = request.user  # type: ignore[assignment]
	from course.models import Unit as CourseUnit, VocabularyItem
	from .models import DailyReviseQuestion
	import datetime

	today = datetime.date.today()
	mode = request.GET.get('mode', 'all')
	# Frontend offers a Grammar toggle; until grammar MCQ is implemented for units,
	# treat 'grammar' as 'vocab' to avoid returning an empty quiz.
	if mode == 'grammar':
		mode = 'vocab'
	include_wrongs = request.GET.get('include_wrongs', '1') != '0'

	# ── Gather eligible units (>= 75% quiz score) ────────────────────────────
	scored_units_ids = list(
		QuizScore.objects
		.filter(user=user, percentage__gte=75)
		.values_list('unit_id', flat=True)
		.distinct()
	)

	questions = []

	# ── Vocabulary questions from eligible units ──────────────────────────────
	if mode in ('all', 'vocab'):
		vocab_qs = VocabularyItem.objects.filter(
			unit_id__in=scored_units_ids, unit__is_active=True
		).select_related('unit')
		vocab_qs = _filter_vocab_by_user_exam(vocab_qs, user)
		for item in vocab_qs:
			values = [item.correct, item.wrong1, item.wrong2, item.wrong3]
			random.shuffle(values)
			keys = ['A', 'B', 'C', 'D']
			shuffled = dict(zip(keys, values))
			correct_key = next(k for k, v in shuffled.items() if v == item.correct)
			questions.append({
				'id': item.id,
				'source': 'unit',
				'type': 'vocab',
				'unit_id': item.unit_id,
				'unit_name': item.unit.name or f'Unit {item.unit.unit_number}',
				'target': item.target,
				'options': shuffled,
				'correct_answer': correct_key,
				'is_review': False,
			})

	# Grammar MCQ: GrammarLearnItem has no MCQ fields; grammar daily revise skipped for now.

	# ── Wrong-answer review items due today ───────────────────────────────────
	if include_wrongs:
		pending = DailyReviseQuestion.objects.filter(
			user=user, is_active=True, next_review_date__lte=today
		).select_related('vocabulary_item', 'grammar_item',
						  'vocabulary_item__unit', 'grammar_item__unit')

		for rev in pending:
			if rev.question_type == 'vocab' and rev.vocabulary_item:
				item = rev.vocabulary_item
				values = [item.correct, item.wrong1, item.wrong2, item.wrong3]
				random.shuffle(values)
				keys = ['A', 'B', 'C', 'D']
				shuffled = dict(zip(keys, values))
				correct_key = next(k for k, v in shuffled.items() if v == item.correct)
				questions.append({
					'id': item.id,
					'review_id': rev.id,
					'source': 'review',
					'type': 'vocab',
					'unit_id': item.unit_id,
					'unit_name': item.unit.name if item.unit else '',
					'target': item.target,
					'options': shuffled,
					'correct_answer': correct_key,
					'is_review': True,
					'wrong_count': rev.wrong_count,
				})
			# grammar review items skipped (no MCQ grammar model)

	random.shuffle(questions)
	return JsonResponse({'questions': questions, 'total': len(questions)})


@api_login_required
def daily_revise_answer(request: HttpRequest) -> JsonResponse:
	"""Record a daily revise answer and update spaced-repetition schedule.

	POST body:
	  {
	    "question_type": "vocab" | "grammar",
	    "item_id": <int>,           -- VocabularyItem.id or GrammarLearnItem.id
	    "is_correct": true/false,
	    "review_id": <int|null>     -- DailyReviseQuestion.id if this is a review item
	  }

	Algorithm:
	  - Wrong answer (new item): create DailyReviseQuestion with next_review_date = today + 4
	  - Wrong answer (existing review item): extend by 2 days from today
	  - Correct answer (review item): mark is_active = False (stop repeating)
	  - Correct answer (new item): do nothing (no tracking needed)
	"""
	if request.method != 'POST':
		return JsonResponse({'error': 'POST required'}, status=405)

	import json, datetime
	from .models import DailyReviseQuestion
	from course.models import VocabularyItem

	try:
		body = json.loads(request.body or '{}')
	except ValueError:
		return JsonResponse({'error': 'Invalid JSON'}, status=400)

	user: User = request.user  # type: ignore[assignment]
	today = datetime.date.today()
	question_type = body.get('question_type')
	item_id = body.get('item_id')
	is_correct = bool(body.get('is_correct', False))
	review_id = body.get('review_id')

	if question_type not in ('vocab', 'grammar') or not item_id:
		return JsonResponse({'error': 'question_type and item_id required'}, status=400)

	xp_earned = 0

	if review_id:
		# This is a review item
		try:
			rev = DailyReviseQuestion.objects.get(id=review_id, user=user)
		except DailyReviseQuestion.DoesNotExist:
			return JsonResponse({'error': 'Review item not found'}, status=404)

		if is_correct:
			rev.is_active = False
			rev.last_answered_date = today
			rev.save()
			xp_earned = 5  # bonus for clearing a review
			from .xp import award_xp
			award_xp(user.id, xp_earned, 'daily_revise_correct_review')
		else:
			# Extend: next_review_date = today + 2 extra days
			rev.wrong_count += 1
			rev.review_interval = 2
			rev.next_review_date = today + datetime.timedelta(days=2)
			rev.last_answered_date = today
			rev.save()
	else:
		# New question (not a review item)
		if not is_correct:
			# Create or update DailyReviseQuestion
			if question_type == 'vocab':
				try:
					vocab = VocabularyItem.objects.get(id=item_id)
				except VocabularyItem.DoesNotExist:
					return JsonResponse({'error': 'VocabularyItem not found'}, status=404)
				rev, created = DailyReviseQuestion.objects.get_or_create(
					user=user, vocabulary_item=vocab,
					defaults={
						'question_type': 'vocab',
						'next_review_date': today + datetime.timedelta(days=4),
						'review_interval': 4,
						'last_answered_date': today,
						'is_active': True,
					}
				)
				if not created and rev.is_active:
					# Already tracking — reset with +4
					rev.wrong_count += 1
					rev.review_interval = 4
					rev.next_review_date = today + datetime.timedelta(days=4)
					rev.last_answered_date = today
					rev.save()
				elif not created and not rev.is_active:
					# Was cleared before, reactivate
					rev.is_active = True
					rev.wrong_count += 1
					rev.review_interval = 4
					rev.next_review_date = today + datetime.timedelta(days=4)
					rev.last_answered_date = today
					rev.save()
			else:
				# Grammar MCQ not yet supported
				pass
		else:
			# Correct on first try — award small XP
			xp_earned = 3
			from .xp import award_xp
			award_xp(user.id, xp_earned, 'daily_revise_correct')

	return JsonResponse({'success': True, 'xp_earned': xp_earned})


@api_login_required
def daily_revise_content(request: HttpRequest, unit_id: int) -> JsonResponse:
	"""Return ALL vocabulary and grammar questions for a unit (for daily revision)."""
	unit = get_object_or_404(Unit, pk=unit_id, is_active=True)
	user: User = request.user  # type: ignore[assignment]

	# All vocabulary — shuffle options
	vocab_qs = _filter_vocab_by_user_exam(unit.vocabulary.all(), user).order_by('order', 'id')
	vocab_questions = []
	for item in vocab_qs:
		values = [item.correct, item.wrong1, item.wrong2, item.wrong3]
		random.shuffle(values)
		keys = ['A', 'B', 'C', 'D']
		shuffled = dict(zip(keys, values))
		correct_key = next(k for k, v in shuffled.items() if v == item.correct)
		vocab_questions.append({
			'id': item.id,
			'type': 'vocab',
			'target': item.target,
			'options': shuffled,
			'correct_answer': correct_key,
		})

	# All grammar questions from GrammarPakka (if available)
	grammar_qs = unit.grammar.all().order_by('order', 'id')
	grammar_data = [
		{'id': g.id, 'type': 'grammar_info', 'title': g.title, 'content': g.content}
		for g in grammar_qs
	]

	return JsonResponse({
		'unit': {
			'id': unit.id,
			'name': unit.name or f'Unit {unit.unit_number}',
			'level': unit.level.name if unit.level else '',
		},
		'vocab_questions': vocab_questions,
		'grammar_info': grammar_data,
		'total_vocab': len(vocab_questions),
	})
