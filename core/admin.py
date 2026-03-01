from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.shortcuts import redirect, render
from django.urls import path

from .models import (
	College,
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

# Customize admin site headers
admin.site.site_header = "BenGo Administration"
admin.site.site_title = "BenGo Admin Portal"
admin.site.index_title = "Welcome to BenGo Admin"


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
		(
			"Profile",
			{
				"fields": (
					"role",
					"college",
					"referral_code",
					"referred_by",
					"streak_count",
					"last_study_date",
				)
			},
		),
	)
	list_display = (
		"username",
		"email",
		"role",
		"target_level",
		"subscription_status",
		"total_points",
		"is_staff",
	)
	list_filter = ("role", "target_level", "subscription_status", "is_staff")
	search_fields = ("username", "email", "first_name", "last_name")


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


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
	change_list_template = "admin/core/college/change_list.html"
	list_display = ("code", "name", "city", "student_count")
	search_fields = ("code", "name", "city")
	list_filter = ("city",)
	
	def student_count(self, obj):
		return obj.students.count()
	student_count.short_description = "Students"

	def get_urls(self):
		urls = super().get_urls()
		custom = [
			path(
				"import/",
				self.admin_site.admin_view(self.import_colleges_view),
				name="core_college_import",
			),
		]
		return custom + urls

	def import_colleges_view(self, request):
		if request.method == "POST":
			f = request.FILES.get("file")
			if not f:
				messages.error(request, "Please choose an Excel/CSV file")
				return redirect("..")

			try:
				import pandas as pd
			except Exception:
				messages.error(request, "Missing dependency: pandas")
				return redirect("..")

			name = (getattr(f, "name", "") or "").lower()
			try:
				if name.endswith(".csv"):
					df = pd.read_csv(f, header=None)
				else:
					df = pd.read_excel(f, header=None)
			except Exception as e:
				messages.error(request, f"Failed to read file: {e}")
				return redirect("..")

			if df.shape[1] < 2:
				messages.error(request, "File must have at least 2 columns: code, name")
				return redirect("..")

			created = 0
			updated = 0
			skipped = 0
			for _, row in df.iterrows():
				code = str(row.iloc[0]).strip() if row.iloc[0] is not None else ""
				college_name = str(row.iloc[1]).strip() if row.iloc[1] is not None else ""
				if code.lower() in {"nan", "none"}:
					code = ""
				if college_name.lower() in {"nan", "none"}:
					college_name = ""
				code = code.strip().upper()
				college_name = college_name.strip()
				if not code or not college_name:
					skipped += 1
					continue

				obj, was_created = College.objects.update_or_create(
					code=code,
					defaults={"name": college_name},
				)
				if was_created:
					created += 1
				else:
					updated += 1

			messages.success(
				request,
				f"Import completed: {created} created, {updated} updated, {skipped} skipped",
			)
			return redirect("..")

		context = dict(
			self.admin_site.each_context(request),
			title="Import Colleges",
		)
		return render(request, "admin/core/college/import_colleges.html", context)
