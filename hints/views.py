from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.utils import timezone

from core.decorators import api_login_required
from course.models import VocabularyItem
from social.models import Friendship
from .models import HintUsage, VocabularyHint


def _profile_pic_url(profile, request: HttpRequest) -> str | None:
    if not profile or not getattr(profile, "profile_picture", None):
        return None
    try:
        url = profile.profile_picture.url
        updated_at = getattr(profile, "updated_at", None)
        if updated_at:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}v={int(updated_at.timestamp())}"
        return request.build_absolute_uri(url)
    except Exception:
        return None


@api_login_required
def vocab_hints(request: HttpRequest, vocab_id: int) -> JsonResponse:
    """GET: get my hint + friends' hints. POST: save/update my hint."""

    vocab = VocabularyItem.objects.filter(pk=vocab_id).first()
    if not vocab:
        return JsonResponse({"detail": "Vocabulary not found"}, status=404)

    if request.method == "GET":
        # My hint
        my_hint = (
            VocabularyHint.objects
            .filter(user=request.user, vocabulary_item_id=vocab_id)
            .select_related("user", "user__profile")
            .first()
        )
        my_profile = getattr(request.user, "profile", None)
        my_display_name = (
            getattr(my_profile, "display_username", None)
            or request.user.first_name
            or request.user.username
        )

        # Friends' hints
        from django.db.models import Q
        uid = request.user.id
        from django.contrib.auth import get_user_model
        User = get_user_model()
        friendships = Friendship.objects.filter(Q(user1_id=uid) | Q(user2_id=uid))
        friend_ids = [
            f.user2_id if f.user1_id == uid else f.user1_id
            for f in friendships
        ]
        friends_hints = (
            VocabularyHint.objects
            .filter(vocabulary_item_id=vocab_id, user_id__in=friend_ids)
            .select_related("user", "user__profile")
        )

        friends_data = []
        for h in friends_hints:
            profile = getattr(h.user, "profile", None)
            friends_data.append({
                "user_id": h.user_id,
                "display_name": (getattr(profile, "display_username", None) or h.user.first_name or h.user.username),
                "profile_picture": _profile_pic_url(profile, request),
                "hint_text": h.hint_text,
                "updated_at": h.updated_at.isoformat(),
            })

        return JsonResponse({
            "my_hint": {
                "hint_text": my_hint.hint_text if my_hint else None,
                "has_hint": bool(my_hint),
                "display_name": my_display_name,
                "profile_picture": _profile_pic_url(my_profile, request),
                "updated_at": my_hint.updated_at.isoformat() if my_hint else None,
            },
            "friends_hints": friends_data,
        })

    if request.method == "POST":
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({"detail": "Invalid JSON"}, status=400)

        hint_text = (body.get("hint_text") or "").strip()
        if not hint_text:
            # Delete hint if empty
            VocabularyHint.objects.filter(user=request.user, vocabulary_item_id=vocab_id).delete()
            return JsonResponse({"detail": "Hint deleted"})

        if len(hint_text) > 2000:
            return JsonResponse({"detail": "Hint too long (max 2000 chars)"}, status=400)

        hint, created = VocabularyHint.objects.update_or_create(
            user=request.user,
            vocabulary_item_id=vocab_id,
            defaults={"hint_text": hint_text},
        )
        return JsonResponse({
            "detail": "Hint saved",
            "created": created,
            "hint_text": hint.hint_text,
        })

    return JsonResponse({"detail": "Method not allowed"}, status=405)


@api_login_required
def use_quiz_hint(request: HttpRequest, vocab_id: int) -> JsonResponse:
    """Return my hint for a vocab during a quiz. Deducts from daily limit."""
    if request.method != "GET":
        return JsonResponse({"detail": "GET required"}, status=405)

    today = timezone.localdate()
    if not HintUsage.can_use(request.user.id, today):
        return JsonResponse({
            "detail": "Daily hint limit reached (3 per day)",
            "remaining": 0,
        }, status=429)

    hint = VocabularyHint.objects.filter(
        user=request.user, vocabulary_item_id=vocab_id
    ).first()

    if not hint:
        return JsonResponse({"hint_text": None, "has_hint": False, "remaining": None})

    # Only deduct if the user actually has a hint to view
    new_count = HintUsage.increment(request.user.id, today)
    remaining = max(0, HintUsage.DAILY_LIMIT - new_count)

    return JsonResponse({
        "hint_text": hint.hint_text,
        "has_hint": True,
        "remaining": remaining,
    })


@api_login_required
def hint_usage_today(request: HttpRequest) -> JsonResponse:
    """Returns how many hints the user has used today."""
    today = timezone.localdate()
    obj = HintUsage.objects.filter(user=request.user, date=today).first()
    used = obj.count if obj else 0
    return JsonResponse({
        "used": used,
        "limit": HintUsage.DAILY_LIMIT,
        "remaining": max(0, HintUsage.DAILY_LIMIT - used),
    })

