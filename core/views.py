from __future__ import annotations

import json
import random
from io import BytesIO

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import F
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .decorators import api_login_required
from .models import MasteredQuestion, Question, ReviewQueue, User, VideoCompletion, WeeklyContent
from .models import College
from .services import schedule_two_reviews_for_wrong_answer
from .streaks import touch_study_streak
from .models import Mondai


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
	selected = payload.get("selected")
	if not question_id or selected not in {"A", "B", "C", "D"}:
		return JsonResponse({"detail": "question_id and selected(A-D) required"}, status=400)

	question = get_object_or_404(Question.objects.select_related("weekly_content"), pk=question_id)

	touch_study_streak(user_id=user.pk, today=today)

	is_correct = selected == question.correct_answer
	if is_correct:
		User.objects.filter(pk=user.pk).update(total_points=F("total_points") + 1)
		MasteredQuestion.objects.get_or_create(user=user, question=question)
		# Clear any scheduled review items for this question today.
		ReviewQueue.objects.filter(user=user, question=question, scheduled_date=today).delete()
	else:
		schedule_two_reviews_for_wrong_answer(user=user, question=question, today=today)

	return JsonResponse({"correct": is_correct})


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
