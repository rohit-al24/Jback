from __future__ import annotations

from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
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
        form = MondaiForm(request.POST, request.FILES, instance=mondai)
        vocab_formset = MondaiVocabFormSet(request.POST, instance=mondai, prefix="vocab")
        q_formset = MondaiQuestionFormSet(request.POST, instance=mondai, prefix="q")

        action = (request.POST.get("action") or "save").strip()

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
