from __future__ import annotations

from dataclasses import dataclass
import random
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import Mondai
from .roles import ROLE_SENSEI, ROLE_SHITSUMON, ROLE_STUDENT


@dataclass(frozen=True)
class RoleChoice:
    value: str
    label: str


ROLE_CHOICES = (
    RoleChoice(ROLE_STUDENT, "Student"),
    RoleChoice(ROLE_SHITSUMON, "Shitsumon"),
    RoleChoice(ROLE_SENSEI, "Sensei"),
)


def portal_index(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "core/portal_index.html",
        {
            "role_choices": ROLE_CHOICES,
        },
    )


def portal_login(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        # If already logged in, go back to portal.
        if request.user.is_authenticated:
            return redirect("portal_index")
        return render(request, "core/portal_login.html", {"role_choices": ROLE_CHOICES})

    username = (request.POST.get("username") or "").strip()
    password = request.POST.get("password") or ""
    role = (request.POST.get("role") or ROLE_STUDENT).strip()

    if role not in {c.value for c in ROLE_CHOICES}:
        messages.error(request, "Invalid role")
        return redirect("portal_login")

    user = authenticate(request, username=username, password=password)
    if user is None:
        messages.error(request, "Invalid username or password")
        return redirect("portal_login")

    # Enforce role membership.
    if not user.groups.filter(name=role).exists() and not (role == ROLE_STUDENT):
        messages.error(request, f"Your account does not have the '{role}' role")
        return redirect("portal_login")

    login(request, user)

    if role == ROLE_SHITSUMON:
        return redirect("shitsumon_dashboard")
    if role == ROLE_SENSEI:
        return redirect("sensei_dashboard")

    return redirect("portal_index")


@login_required
def portal_logout(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("portal_index")


def _require_group(request: HttpRequest, group_name: str) -> HttpResponse | None:
    if not request.user.is_authenticated:
        return redirect("portal_login")
    if not request.user.groups.filter(name=group_name).exists() and not request.user.is_superuser:
        return HttpResponse("Forbidden", status=403)
    return None


def shitsumon_dashboard(request: HttpRequest) -> HttpResponse:
    forbidden = _require_group(request, ROLE_SHITSUMON)
    if forbidden:
        return forbidden

    mondais = Mondai.objects.filter(created_by=request.user).order_by("-updated_at")
    return render(request, "core/shitsumon_dashboard.html", {"mondais": mondais})


def shitsumon_create(request: HttpRequest) -> HttpResponse:
    forbidden = _require_group(request, ROLE_SHITSUMON)
    if forbidden:
        return forbidden

    mondai = Mondai.objects.create(created_by=request.user, status=Mondai.Status.DRAFT)
    return redirect("shitsumon_edit", public_id=mondai.public_id)


def shitsumon_edit(request: HttpRequest, public_id: str) -> HttpResponse:
    forbidden = _require_group(request, ROLE_SHITSUMON)
    if forbidden:
        return forbidden

    from .mondai_forms import MondaiForm, MondaiQuestionFormSet, MondaiVocabFormSet

    mondai = get_object_or_404(Mondai, public_id=public_id, created_by=request.user)

    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip()

        if action == "import_questions":
            upload = request.FILES.get("questions_file")
            if not upload:
                messages.error(request, "Please upload a CSV or Excel (.xlsx) file")
                return redirect("shitsumon_edit", public_id=mondai.public_id)

            try:
                import pandas as pd
            except Exception:
                messages.error(request, "pandas is not installed on the server")
                return redirect("shitsumon_edit", public_id=mondai.public_id)

            suffix = Path(getattr(upload, "name", "")).suffix.lower()
            try:
                if suffix in {".xlsx", ".xls"}:
                    df = pd.read_excel(upload)
                elif suffix == ".csv":
                    df = pd.read_csv(upload)
                else:
                    messages.error(request, "Unsupported file type. Upload .csv or .xlsx")
                    return redirect("shitsumon_edit", public_id=mondai.public_id)
            except Exception as e:
                messages.error(request, f"Failed to read file: {e}")
                return redirect("shitsumon_edit", public_id=mondai.public_id)

            if df is None or df.empty:
                messages.error(request, "File has no rows")
                return redirect("shitsumon_edit", public_id=mondai.public_id)

            def _norm(s: str) -> str:
                return " ".join((s or "").strip().lower().split())

            # Map columns case/space-insensitively.
            colmap = {_norm(str(c)): str(c) for c in df.columns}
            required = [
                "transcript source",
                "target word",
                "wrong 1",
                "wrong 2",
                "wrong 3",
                "correct translation",
            ]
            missing = [c for c in required if c not in colmap]
            if missing:
                messages.error(request, f"Missing required columns: {', '.join(missing)}")
                return redirect("shitsumon_edit", public_id=mondai.public_id)

            from .models import MondaiQuestion

            created = 0
            skipped = 0
            errors: list[str] = []

            max_order = mondai.questions.aggregate(m=Max("order")).get("m")
            next_order = int(max_order or 0)

            with transaction.atomic():
                for i, row in df.iterrows():
                    try:
                        target = row[colmap["target word"]]
                        correct = row[colmap["correct translation"]]
                        w1 = row[colmap["wrong 1"]]
                        w2 = row[colmap["wrong 2"]]
                        w3 = row[colmap["wrong 3"]]

                        # Skip empty rows
                        target_s = "" if pd.isna(target) else str(target).strip()
                        correct_s = "" if pd.isna(correct) else str(correct).strip()
                        w1_s = "" if pd.isna(w1) else str(w1).strip()
                        w2_s = "" if pd.isna(w2) else str(w2).strip()
                        w3_s = "" if pd.isna(w3) else str(w3).strip()

                        if not target_s and not correct_s and not w1_s and not w2_s and not w3_s:
                            skipped += 1
                            continue

                        if not target_s or not correct_s or not w1_s or not w2_s or not w3_s:
                            skipped += 1
                            errors.append(f"Row {int(i) + 2}: missing Target Word / Correct / Wrong options")
                            continue

                        options = [correct_s, w1_s, w2_s, w3_s]
                        random.shuffle(options)
                        try:
                            correct_idx = options.index(correct_s)
                        except ValueError:
                            skipped += 1
                            errors.append(f"Row {int(i) + 2}: correct translation not found after shuffle")
                            continue

                        next_order += 1
                        MondaiQuestion.objects.create(
                            mondai=mondai,
                            prompt=f"What is the meaning of {target_s}?",
                            option_a=options[0],
                            option_b=options[1],
                            option_c=options[2],
                            option_d=options[3],
                            correct_answer="ABCD"[correct_idx],
                            order=next_order,
                        )
                        created += 1
                    except Exception as e:
                        skipped += 1
                        errors.append(f"Row {int(i) + 2}: {e}")

            if created == 0:
                messages.error(request, "No questions were imported. Check file contents.")
            else:
                messages.success(request, f"Imported {created} questions ({skipped} skipped)")
                if errors:
                    messages.warning(request, "Some rows were skipped: " + " | ".join(errors[:5]))

            return redirect("shitsumon_edit", public_id=mondai.public_id)

        if action == "reset_questions":
            # Remove all existing questions for this Mondai
            count = mondai.questions.count()
            if count > 0:
                mondai.questions.all().delete()
                messages.success(request, f"Removed {count} questions")
            else:
                messages.info(request, "No questions to remove")
            return redirect("shitsumon_edit", public_id=mondai.public_id)

        form = MondaiForm(request.POST, request.FILES, instance=mondai)
        vocab_formset = MondaiVocabFormSet(request.POST, instance=mondai, prefix="vocab")
        q_formset = MondaiQuestionFormSet(request.POST, instance=mondai, prefix="q")

        if form.is_valid() and vocab_formset.is_valid() and q_formset.is_valid():
            form.save()
            vocab_formset.save()
            q_formset.save()

            if action == "submit":
                mondai.status = Mondai.Status.PENDING
                mondai.review_note = ""
                mondai.reviewed_by = None
                mondai.reviewed_at = None
                mondai.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])
                messages.success(request, "Mondai submitted for Sensei approval")
            else:
                messages.success(request, "Mondai saved")

            return redirect("shitsumon_edit", public_id=mondai.public_id)

        messages.error(request, "Please fix the errors and try again")
    else:
        form = MondaiForm(instance=mondai)
        vocab_formset = MondaiVocabFormSet(instance=mondai, prefix="vocab")
        q_formset = MondaiQuestionFormSet(instance=mondai, prefix="q")

    return render(
        request,
        "core/shitsumon_edit.html",
        {
            "mondai": mondai,
            "form": form,
            "vocab_formset": vocab_formset,
            "q_formset": q_formset,
        },
    )


def shitsumon_fix_week(request: HttpRequest, public_id: str) -> HttpResponse:
    forbidden = _require_group(request, ROLE_SHITSUMON)
    if forbidden:
        return forbidden

    mondai = get_object_or_404(Mondai, public_id=public_id, created_by=request.user)
    if mondai.status != Mondai.Status.APPROVED:
        messages.error(request, "Mondai must be approved by Sensei before fixing the week")
        return redirect("shitsumon_dashboard")

    if request.method != "POST":
        return HttpResponse("Method Not Allowed", status=405)

    week_start = (request.POST.get("week_start_date") or "").strip()
    week_end = (request.POST.get("week_end_date") or "").strip()
    if not week_start or not week_end:
        messages.error(request, "Start and end date are required")
        return redirect("shitsumon_dashboard")

    try:
        from datetime import date

        start_date = date.fromisoformat(week_start)
        end_date = date.fromisoformat(week_end)
    except Exception:
        messages.error(request, "Invalid date format")
        return redirect("shitsumon_dashboard")

    if end_date < start_date:
        messages.error(request, "End date cannot be before start date")
        return redirect("shitsumon_dashboard")
    # Week window should be at most 7 days (select a calendar week).
    if (end_date - start_date).days > 6:
        messages.error(request, "Week range must be within 7 days")
        return redirect("shitsumon_dashboard")

    mondai.week_start_date = start_date
    mondai.week_end_date = end_date
    mondai.save(update_fields=["week_start_date", "week_end_date", "updated_at"])
    messages.success(request, "Week fixed successfully")
    return redirect("shitsumon_dashboard")


def shitsumon_transcribe(request: HttpRequest, public_id: str) -> HttpResponse:
    forbidden = _require_group(request, ROLE_SHITSUMON)
    if forbidden:
        return forbidden

    if request.method != "POST":
        return HttpResponse("Method Not Allowed", status=405)

    mondai = get_object_or_404(Mondai, public_id=public_id, created_by=request.user)

    # If already transcribed, return immediately (unless user forces re-run).
    force = (request.POST.get("force") or "").strip() in {"1", "true", "yes"}
    if mondai.transcript and not force:
        return JsonResponse(
            {
                "public_id": mondai.public_id,
                "language": None,
                "language_probability": None,
                "transcript": mondai.transcript,
                "cached": True,
            }
        )

    source: str | None = None
    if mondai.video_type == Mondai.VideoType.UPLOAD and mondai.video_file:
        source = mondai.video_file.path
    elif mondai.video_type in {Mondai.VideoType.LINK, Mondai.VideoType.EMBED}:
        source = mondai.video_url or mondai.video_embed_url

    if not source:
        return JsonResponse({"detail": "No video source to transcribe"}, status=400)

    from .transcription import TranscriptionError, transcribe_media

    try:
        result = transcribe_media(
            source,
            # Use a fast default for the UI button.
            model_size="turbo",
            device="cuda",
            compute_type="float16",
            language="ja",
            beam_size=3,
        )
    except TranscriptionError as e:
        return JsonResponse({"detail": str(e)}, status=400)

    mondai.transcript = result.text
    mondai.save(update_fields=["transcript", "updated_at"])

    return JsonResponse(
        {
            "public_id": mondai.public_id,
            "language": result.language,
            "language_probability": result.language_probability,
            "transcript": result.text,
            "cached": False,
        }
    )


def sensei_dashboard(request: HttpRequest) -> HttpResponse:
    forbidden = _require_group(request, ROLE_SENSEI)
    if forbidden:
        return forbidden

    mondais = Mondai.objects.all().order_by("-updated_at")
    return render(request, "core/sensei_dashboard.html", {"mondais": mondais})


def sensei_review(request: HttpRequest, public_id: str) -> HttpResponse:
    forbidden = _require_group(request, ROLE_SENSEI)
    if forbidden:
        return forbidden

    mondai = get_object_or_404(Mondai, public_id=public_id)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        note = (request.POST.get("note") or "").strip()

        if action == "approve":
            mondai.status = Mondai.Status.APPROVED
            mondai.review_note = note
            mondai.reviewed_by = request.user
            mondai.reviewed_at = timezone.now()
            mondai.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])
            messages.success(request, "Mondai approved")
            return redirect("sensei_dashboard")

        if action == "reject":
            mondai.status = Mondai.Status.REJECTED
            mondai.review_note = note
            mondai.reviewed_by = request.user
            mondai.reviewed_at = timezone.now()
            mondai.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at", "updated_at"])
            messages.success(request, "Mondai rejected")
            return redirect("sensei_dashboard")

        messages.error(request, "Invalid action")

    return render(request, "core/sensei_review.html", {"mondai": mondai})
