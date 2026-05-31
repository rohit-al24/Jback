from __future__ import annotations

import json
import os

from django.contrib.auth import get_user_model
from django.db import models as django_models
from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from core.decorators import api_login_required
from .models import AppFeatures, FriendRequest, Friendship, Message, MutualStreak, UserProfile, UserSettings

User = get_user_model()


def _profile_pic_url(profile, request):
    if not profile or not profile.profile_picture:
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


def _user_summary(user, request=None):
    profile = getattr(user, "profile", None)
    return {
        "id": user.id,
        "username": user.username,
        "display_username": getattr(profile, "display_username", None) or user.username,
        "full_name": user.get_full_name() or user.username,
        "first_name": user.first_name,
        "college": user.college.name if user.college else None,
        "level": getattr(user, "target_level", None),
        "streak": getattr(user, "streak_count", 0),
        "profile_picture": _profile_pic_url(profile, request) if request else None,
    }


# ── Feature Flags ───────────────────────────────────────────────────────────

@api_login_required
def app_features(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"detail": "GET required"}, status=405)
    flags = AppFeatures.get_solo()
    return JsonResponse({
        "audio_calls_enabled": bool(flags.audio_calls_enabled),
    })


# ── Friend Requests ──────────────────────────────────────────────────────────

@api_login_required
def send_friend_request(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    to_user_id = body.get("to_user_id")
    if not to_user_id:
        return JsonResponse({"detail": "to_user_id required"}, status=400)

    if to_user_id == request.user.id:
        return JsonResponse({"detail": "Cannot send request to yourself"}, status=400)

    if Friendship.are_friends(request.user.id, to_user_id):
        return JsonResponse({"detail": "Already friends"}, status=400)

    to_user = User.objects.filter(pk=to_user_id).first()
    if not to_user:
        return JsonResponse({"detail": "User not found"}, status=404)

    # Check if reverse request exists — auto-accept
    reverse = FriendRequest.objects.filter(
        from_user_id=to_user_id, to_user_id=request.user.id, status="pending"
    ).first()
    if reverse:
        reverse.status = "accepted"
        reverse.save(update_fields=["status", "updated_at"])
        Friendship.create_friendship(request.user.id, to_user_id)
        return JsonResponse({"detail": "Friendship created (auto-accept)", "status": "accepted"})

    freq, created = FriendRequest.objects.get_or_create(
        from_user_id=request.user.id,
        to_user_id=to_user_id,
        defaults={"status": "pending"},
    )
    if not created and freq.status == "rejected":
        freq.status = "pending"
        freq.save(update_fields=["status", "updated_at"])

    return JsonResponse({"detail": "Request sent", "request_id": freq.id, "status": freq.status})


@api_login_required
def incoming_requests(request: HttpRequest) -> JsonResponse:
    reqs = (
        FriendRequest.objects
        .filter(to_user=request.user, status="pending")
        .select_related("from_user", "from_user__college", "from_user__profile")
        .order_by("-created_at")
    )
    data = []
    for r in reqs:
        s = _user_summary(r.from_user, request)
        s["request_id"] = r.id
        s["sent_at"] = r.created_at.isoformat()
        data.append(s)
    return JsonResponse({"requests": data})


@api_login_required
@require_http_methods(["POST"])
def respond_to_request(request: HttpRequest) -> JsonResponse:
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    request_id = body.get("request_id")
    action = body.get("action")  # "accept" | "reject"

    if action not in ("accept", "reject"):
        return JsonResponse({"detail": "action must be accept or reject"}, status=400)

    freq = FriendRequest.objects.filter(pk=request_id, to_user=request.user, status="pending").first()
    if not freq:
        return JsonResponse({"detail": "Request not found"}, status=404)

    if action == "accept":
        freq.status = "accepted"
        freq.save(update_fields=["status", "updated_at"])
        Friendship.create_friendship(request.user.id, freq.from_user_id)
        return JsonResponse({"detail": "Friendship created"})
    else:
        freq.status = "rejected"
        freq.save(update_fields=["status", "updated_at"])
        return JsonResponse({"detail": "Request rejected"})


@api_login_required
def friends_list(request: HttpRequest) -> JsonResponse:
    uid = request.user.id
    friendships = Friendship.objects.filter(
        Q(user1_id=uid) | Q(user2_id=uid)
    ).select_related("user1__college", "user1__profile", "user2__college", "user2__profile")

    friends = []
    for f in friendships:
        friend = f.user2 if f.user1_id == uid else f.user1
        s = _user_summary(friend, request)
        # Mutual streak
        ms = MutualStreak.objects.filter(
            Q(user1_id=uid, user2_id=friend.id) | Q(user1_id=friend.id, user2_id=uid)
        ).first()
        s["mutual_streak"] = ms.streak_count if ms else 0
        friends.append(s)
    return JsonResponse({"friends": friends})


# ── User Search ───────────────────────────────────────────────────────────────

@api_login_required
def search_users(request: HttpRequest) -> JsonResponse:
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"users": []})

    users = (
        User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(profile__display_username__icontains=query)
        )
        .exclude(pk=request.user.id)
        .select_related("college", "profile")[:20]
    )

    results = []
    for u in users:
        s = _user_summary(u, request)
        s["is_friend"] = Friendship.are_friends(request.user.id, u.id)
        results.append(s)
    return JsonResponse({"users": results})


# ── Profile ──────────────────────────────────────────────────────────────────

@api_login_required
def get_or_update_profile(request: HttpRequest) -> JsonResponse:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "GET":
        return JsonResponse({
            "display_username": profile.display_username or request.user.username,
            "bio": profile.bio,
            "profile_picture": _profile_pic_url(profile, request),
        })

    if request.method == "POST":
        # Handle multipart (profile picture upload)
        display_username = request.POST.get("display_username", "").strip()
        bio = request.POST.get("bio", "").strip()

        if display_username:
            # Ensure unique
            conflict = UserProfile.objects.filter(display_username=display_username).exclude(user=request.user).exists()
            if conflict:
                return JsonResponse({"detail": "Username already taken"}, status=400)
            profile.display_username = display_username

        if bio is not None:
            profile.bio = bio[:280]

        pic = request.FILES.get("profile_picture")
        if pic:
            # Validate file type
            allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
            if pic.content_type not in allowed_types:
                return JsonResponse({"detail": "Invalid image type"}, status=400)
            if pic.size > 5 * 1024 * 1024:  # 5MB limit
                return JsonResponse({"detail": "Image too large (max 5MB)"}, status=400)
            # Delete old file to avoid orphans
            if profile.profile_picture:
                try:
                    old_path = profile.profile_picture.path
                    if os.path.isfile(old_path):
                        os.remove(old_path)
                except Exception:
                    pass
            profile.profile_picture = pic

        if request.POST.get("remove_picture"):
            if profile.profile_picture:
                try:
                    old_path = profile.profile_picture.path
                    if os.path.isfile(old_path):
                        os.remove(old_path)
                except Exception:
                    pass
            profile.profile_picture = None

        profile.save()
        return JsonResponse({
            "detail": "Profile updated",
            "display_username": profile.display_username,
            "bio": profile.bio,
            "profile_picture": _profile_pic_url(profile, request),
        })

    return JsonResponse({"detail": "Method not allowed"}, status=405)


@api_login_required
def public_profile(request: HttpRequest, user_id: int) -> JsonResponse:
    user = User.objects.filter(pk=user_id).select_related("college", "profile").first()
    if not user:
        return JsonResponse({"detail": "Not found"}, status=404)
    s = _user_summary(user, request)
    s["is_friend"] = Friendship.are_friends(request.user.id, user_id)
    s["total_xp"] = getattr(user, "total_points", 0)
    return JsonResponse(s)


# ── Messaging ─────────────────────────────────────────────────────────────────

@api_login_required
def conversations_list(request: HttpRequest) -> JsonResponse:
    """List all conversations (distinct users) for the current user."""
    uid = request.user.id
    # Get latest message per conversation partner
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT partner_id, MAX(id) as last_msg_id
            FROM (
                SELECT receiver_id as partner_id, id FROM social_message WHERE sender_id = %s
                UNION ALL
                SELECT sender_id as partner_id, id FROM social_message WHERE receiver_id = %s
            ) t
            GROUP BY partner_id
            ORDER BY last_msg_id DESC
        """, [uid, uid])
        rows = cursor.fetchall()

    msg_ids = [r[1] for r in rows]
    messages = {m.id: m for m in Message.objects.filter(pk__in=msg_ids).select_related("sender", "receiver")}

    conversations = []
    for partner_id, last_msg_id in rows:
        msg = messages.get(last_msg_id)
        if not msg:
            continue
        partner = User.objects.filter(pk=partner_id).select_related("profile").first()
        if not partner:
            continue
        profile = getattr(partner, "profile", None)
        unread = Message.objects.filter(
            sender_id=partner_id, receiver_id=uid, is_read=False
        ).count()
        conversations.append({
            "partner": _user_summary(partner, request),
            "last_message": msg.content[:100],
            "last_message_at": msg.created_at.isoformat(),
            "unread_count": unread,
        })
    return JsonResponse({"conversations": conversations})


@api_login_required
def chat_messages(request: HttpRequest, partner_id: int) -> JsonResponse:
    if request.method == "GET":
        uid = request.user.id
        msgs = Message.objects.filter(
            (Q(sender_id=uid) & Q(receiver_id=partner_id)) |
            (Q(sender_id=partner_id) & Q(receiver_id=uid))
        ).order_by("created_at")[:100]

        partner = User.objects.filter(pk=partner_id).select_related("college", "profile").first()
        if not partner:
            return JsonResponse({"detail": "User not found"}, status=404)

        # Mark received messages as read
        Message.objects.filter(
            sender_id=partner_id, receiver_id=uid, is_read=False
        ).update(is_read=True)

        data = [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "content": m.content,
                "is_read": m.is_read,
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ]
        return JsonResponse({"messages": data, "partner": _user_summary(partner, request)})

    if request.method == "POST":
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({"detail": "Invalid JSON"}, status=400)

        content = (body.get("content") or "").strip()
        if not content:
            return JsonResponse({"detail": "content required"}, status=400)
        if len(content) > 2000:
            return JsonResponse({"detail": "Message too long"}, status=400)

        # Only friends can message
        if not Friendship.are_friends(request.user.id, partner_id):
            return JsonResponse({"detail": "You can only message friends"}, status=403)

        msg = Message.objects.create(
            sender=request.user,
            receiver_id=partner_id,
            content=content,
        )
        return JsonResponse({
            "id": msg.id,
            "sender_id": msg.sender_id,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
        })

    return JsonResponse({"detail": "Method not allowed"}, status=405)


# ── Mutual Streaks ────────────────────────────────────────────────────────────

@api_login_required
def mutual_streaks(request: HttpRequest) -> JsonResponse:
    uid = request.user.id
    streaks = MutualStreak.objects.filter(
        Q(user1_id=uid) | Q(user2_id=uid)
    ).select_related("user1__profile", "user2__profile")

    data = []
    for ms in streaks:
        partner = ms.user2 if ms.user1_id == uid else ms.user1
        i_done = ms.user1_done_today if ms.user1_id == uid else ms.user2_done_today
        they_done = ms.user2_done_today if ms.user1_id == uid else ms.user1_done_today
        data.append({
            "partner": _user_summary(partner, request),
            "streak_count": ms.streak_count,
            "last_date": ms.last_date.isoformat() if ms.last_date else None,
            "i_done_today": i_done,
            "they_done_today": they_done,
        })
    return JsonResponse({"mutual_streaks": data})


# ── User Settings ────────────────────────────────────────────────────────────

@api_login_required
def user_settings(request: HttpRequest) -> JsonResponse:
    """GET returns current settings. POST updates them."""
    settings_obj = UserSettings.for_user(request.user)
    if request.method == "GET":
        return JsonResponse({
            "hints_visible_to_friends": settings_obj.hints_visible_to_friends,
        })
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"detail": "Invalid JSON"}, status=400)
        if "hints_visible_to_friends" in data:
            settings_obj.hints_visible_to_friends = bool(data["hints_visible_to_friends"])
        settings_obj.save(update_fields=["hints_visible_to_friends", "updated_at"])
        return JsonResponse({
            "hints_visible_to_friends": settings_obj.hints_visible_to_friends,
        })
    return JsonResponse({"detail": "Method not allowed"}, status=405)

