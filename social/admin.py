from django.contrib import admin

from .models import AppFeatures, FriendRequest, Friendship, Message, MutualStreak, UserProfile


@admin.register(AppFeatures)
class AppFeaturesAdmin(admin.ModelAdmin):
	list_display = ("id", "audio_calls_enabled", "updated_at")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "display_username", "updated_at")
	search_fields = ("user__username", "display_username")


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
	list_display = ("from_user", "to_user", "status", "created_at", "updated_at")
	list_filter = ("status",)
	search_fields = ("from_user__username", "to_user__username")


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
	list_display = ("user1", "user2", "created_at")
	search_fields = ("user1__username", "user2__username")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
	list_display = ("sender", "receiver", "created_at", "is_read")
	search_fields = ("sender__username", "receiver__username", "content")
	list_filter = ("is_read",)


@admin.register(MutualStreak)
class MutualStreakAdmin(admin.ModelAdmin):
	list_display = ("user1", "user2", "streak_count", "last_date")
