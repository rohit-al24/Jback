from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class PushToken(models.Model):
    """FCM / Capacitor push notification token for a user's device."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_tokens",
    )
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=16, default="android")  # android / ios / web
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"PushToken(user={self.user_id}, platform={self.platform})"


class Notification(models.Model):
    """In-app notification record."""

    class Kind(models.TextChoices):
        FRIEND_REQUEST = "friend_request", "Friend Request"
        FRIEND_ACCEPTED = "friend_accepted", "Friend Accepted"
        CHAT_MESSAGE = "chat_message", "Chat Message"
        STREAK_REMINDER = "streak_reminder", "Streak Reminder"
        MUTUAL_STREAK_BROKEN = "mutual_streak_broken", "Mutual Streak Broken"
        ACHIEVEMENT = "achievement", "Achievement"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
        ]

    def __str__(self) -> str:
        return f"Notification({self.recipient_id}, {self.kind})"
