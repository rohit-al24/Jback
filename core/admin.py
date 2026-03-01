from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
	Mondai,
	MondaiQuestion,
	MondaiVocabulary,
	MasteredQuestion,
	Question,
	ReviewQueue,
	SubscriptionPlan,
	User,
	UserSubscription,
	VideoCompletion,
	WeeklyContent,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
	fieldsets = DjangoUserAdmin.fieldsets + (
		(
			"Learning",
			{
				"fields": (
					"target_level",
					"total_points",
					"subscription_status",
				)
			},
		),
	)
	list_display = (
		"username",
		"email",
		"target_level",
		"subscription_status",
		"total_points",
		"is_staff",
	)


@admin.action(description="Approve selected weekly content")
def approve_weekly_content(modeladmin, request, queryset):
	queryset.update(is_approved=True)


@admin.register(WeeklyContent)
class WeeklyContentAdmin(admin.ModelAdmin):
	list_display = ("level", "week_number", "is_approved", "created_at")
	list_filter = ("level", "is_approved")
	actions = [approve_weekly_content]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
	list_display = ("id", "weekly_content", "correct_answer", "created_at")
	list_filter = ("weekly_content__level", "weekly_content__week_number")
	search_fields = ("prompt",)


@admin.register(ReviewQueue)
class ReviewQueueAdmin(admin.ModelAdmin):
	list_display = ("user", "question", "scheduled_date", "created_at")
	list_filter = ("scheduled_date", "user")


@admin.register(MasteredQuestion)
class MasteredQuestionAdmin(admin.ModelAdmin):
	list_display = ("user", "question", "mastered_at")
	list_filter = ("user",)


@admin.register(VideoCompletion)
class VideoCompletionAdmin(admin.ModelAdmin):
	list_display = ("user", "weekly_content", "completed_at")
	list_filter = ("weekly_content__level", "weekly_content__week_number")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
	list_display = ("code", "display_name", "price_paise", "duration_days", "is_active")
	list_filter = ("is_active",)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
	list_display = ("user", "plan", "started_at", "ends_at", "is_active")
	list_filter = ("is_active", "plan")


@admin.register(Mondai)
class MondaiAdmin(admin.ModelAdmin):
	list_display = ("public_id", "name", "status", "created_by", "updated_at")
	list_filter = ("status",)
	search_fields = ("public_id", "name", "created_by__username")


@admin.register(MondaiVocabulary)
class MondaiVocabularyAdmin(admin.ModelAdmin):
	list_display = ("mondai", "term", "reading", "meaning", "order")
	list_filter = ("mondai",)
	search_fields = ("term", "reading", "meaning")


@admin.register(MondaiQuestion)
class MondaiQuestionAdmin(admin.ModelAdmin):
	list_display = ("mondai", "id", "correct_answer", "order")
	list_filter = ("mondai",)
	search_fields = ("prompt",)
