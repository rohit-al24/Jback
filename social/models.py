from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class FriendRequest(models.Model):
    """Friend request from one user to another."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_requests",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_requests",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_user", "to_user"],
                name="unique_friend_request",
            )
        ]
        indexes = [
            models.Index(fields=["to_user", "status"]),
            models.Index(fields=["from_user", "status"]),
        ]

    def __str__(self) -> str:
        return f"Request({self.from_user_id} \u2192 {self.to_user_id}, {self.status})"


class Friendship(models.Model):
    """Bidirectional friendship. Always store user1_id < user2_id."""

    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_as_user1",
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_as_user2",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user1", "user2"],
                name="unique_friendship",
            )
        ]
        indexes = [
            models.Index(fields=["user1"]),
            models.Index(fields=["user2"]),
        ]

    def __str__(self) -> str:
        return f"Friends({self.user1_id}, {self.user2_id})"

    @classmethod
    def are_friends(cls, uid1: int, uid2: int) -> bool:
        lo, hi = (uid1, uid2) if uid1 < uid2 else (uid2, uid1)
        return cls.objects.filter(user1_id=lo, user2_id=hi).exists()

    @classmethod
    def create_friendship(cls, uid1: int, uid2: int) -> "Friendship":
        lo, hi = (uid1, uid2) if uid1 < uid2 else (uid2, uid1)
        obj, _ = cls.objects.get_or_create(user1_id=lo, user2_id=hi)
        return obj


class MutualStreak(models.Model):
    """Snapchat-style mutual streak between two friends.
    Both must do a study activity each day to maintain it.
    """

    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mutual_streaks_as_user1",
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mutual_streaks_as_user2",
    )
    streak_count = models.PositiveIntegerField(default=0)
    last_date = models.DateField(null=True, blank=True)
    user1_done_today = models.BooleanField(default=False)
    user2_done_today = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user1", "user2"],
                name="unique_mutual_streak",
            )
        ]

    def __str__(self) -> str:
        return f"MutualStreak({self.user1_id}, {self.user2_id}, {self.streak_count})"

    @classmethod
    def get_or_create_for(cls, uid1: int, uid2: int) -> "MutualStreak":
        lo, hi = (uid1, uid2) if uid1 < uid2 else (uid2, uid1)
        obj, _ = cls.objects.get_or_create(user1_id=lo, user2_id=hi)
        return obj


class Message(models.Model):
    """Direct message between friends."""

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["sender", "receiver", "created_at"]),
            models.Index(fields=["receiver", "is_read"]),
        ]
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Message({self.sender_id} \u2192 {self.receiver_id})"


class UserProfile(models.Model):
    """Extended profile: display username, bio, profile picture."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_username = models.CharField(max_length=40, unique=True, blank=True)
    bio = models.CharField(max_length=280, blank=True)
    profile_picture = models.ImageField(
        upload_to="profile_pics/",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile({self.user_id})"


class AppFeatures(models.Model):
    """Admin-controlled feature flags.

    Stored in DB so production (cloud) can toggle without redeploy.
    """

    audio_calls_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "App Features"
        verbose_name_plural = "App Features"

    @classmethod
    def get_solo(cls) -> "AppFeatures":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self) -> str:
        return "AppFeatures"
