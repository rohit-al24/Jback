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
from course.models import (
	Level,
	Unit,
	VocabularyItem,
	GrammarContent,
	GrammarLearnItem,
	GrammarPakkaItem,
)


def _safe_int(value) -> int | None:
	try:
		if value is None:
			return None
		# Pandas/Excel often gives floats like 1.0
		return int(value)
	except Exception:
		try:
			return int(float(str(value)))
		except Exception:
			return None


def _level_number_from_exam_code(exam_code: str) -> int:
	code = (exam_code or "").strip().upper()
	# Product convention: N5 content maps to Level 1; N4 maps to Level 2.
	if code == "N5":
		return 1
	if code == "N4":
		return 2
	return 1


def _resolve_or_create_unit(unit_value: int, exam_code: str) -> Unit | None:
	"""Resolve a Unit from import value.

	- If a Unit exists with pk == unit_value, use it (backward-compatible).
	- Otherwise treat unit_value as unit_number and auto-create the Unit.
	"""
	if not unit_value or int(unit_value) <= 0:
		return None

	unit = Unit.objects.filter(id=unit_value).first()
	if unit:
		return unit

	level_number = _level_number_from_exam_code(exam_code)
	level, _ = Level.objects.get_or_create(
		level_number=level_number,
		defaults={
			"name": f"Level {level_number}",
			"description": "",
			"is_active": True,
			"order": level_number,
		},
	)

	unit, _ = Unit.objects.get_or_create(
		level=level,
		unit_number=int(unit_value),
		defaults={
			"name": f"Unit {int(unit_value)}",
			"description": "",
			"is_active": True,
			"order": int(unit_value),
		},
	)
	return unit

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


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
	list_display = ("level_number", "name", "is_active", "order")
	list_filter = ("is_active",)
	search_fields = ("name",)
	ordering = ("order", "level_number")


class UnitInline(admin.TabularInline):
	model = Unit
	extra = 1
	fields = ("unit_number", "name", "is_active", "order")


class VocabularyItemInline(admin.TabularInline):
	model = VocabularyItem
	extra = 1
	fields = ("exam", "target", "correct", "wrong1", "wrong2", "wrong3", "correct_answer", "order")
	readonly_fields = ("correct_answer",)


class GrammarContentInline(admin.StackedInline):
	model = GrammarContent
	extra = 1
	fields = ("exam", "title", "content", "order")


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
	list_display = ("level", "unit_number", "name", "is_active", "order")
	list_filter = ("level", "is_active")
	search_fields = ("name",)
	ordering = ("level", "order", "unit_number")
	inlines = [VocabularyItemInline, GrammarContentInline]


@admin.register(VocabularyItem)
class VocabularyItemAdmin(admin.ModelAdmin):
	change_list_template = "admin/course/vocabularyitem/change_list.html"
	list_display = ("unit", "exam", "target", "correct", "correct_answer", "order")
	list_filter = ("unit__level", "unit", "exam")
	search_fields = ("target", "correct")
	readonly_fields = ("correct_answer",)

	def get_urls(self):
		urls = super().get_urls()
		custom = [
			path(
				"import/",
				self.admin_site.admin_view(self.import_vocabulary_view),
				name="course_vocabularyitem_import",
			),
		]
		return custom + urls

	def import_vocabulary_view(self, request):
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

			if df.shape[1] < 7:
				messages.error(request, "File must have 7 columns: unit_number, exam_code, target, correct, wrong1, wrong2, wrong3")
				return redirect("..")

			from administration.models import Exam
			import random

			created = 0
			updated = 0
			skipped = 0
			for _, row in df.iterrows():
				try:
					unit_value = _safe_int(row.iloc[0]) if pd.notna(row.iloc[0]) else None
					exam_code = str(row.iloc[1]).strip().upper() if pd.notna(row.iloc[1]) else ""
					target = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
					correct = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
					wrong1 = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
					wrong2 = str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else ""
					wrong3 = str(row.iloc[6]).strip() if pd.notna(row.iloc[6]) else ""

					if not unit_value or not target or not correct or not wrong1 or not wrong2 or not wrong3:
						skipped += 1
						continue

					# Resolve/create unit from a numeric unit number (or legacy pk)
					unit = _resolve_or_create_unit(unit_value, exam_code)
					if unit is None:
						skipped += 1
						continue

					# Get exam if provided
					exam = None
					if exam_code:
						try:
							exam = Exam.objects.get(code=exam_code)
						except Exam.DoesNotExist:
							pass

					# Auto-shuffle and determine correct_answer
					options = [
						('A', correct),
						('B', wrong1),
						('C', wrong2),
						('D', wrong3),
					]
					random.shuffle(options)
					correct_answer = 'A'
					for label, value in options:
						if value == correct:
							correct_answer = label
							break

					obj, was_created = VocabularyItem.objects.update_or_create(
						unit=unit,
						target=target,
						defaults={
							"exam": exam,
							"correct": correct,
							"wrong1": wrong1,
							"wrong2": wrong2,
							"wrong3": wrong3,
							"correct_answer": correct_answer,
						},
					)
					if was_created:
						created += 1
					else:
						updated += 1
				except Exception:
					skipped += 1
					continue

			messages.success(
				request,
				f"Import completed: {created} created, {updated} updated, {skipped} skipped",
			)
			return redirect("..")

		context = dict(
			self.admin_site.each_context(request),
			title="Import Vocabulary",
		)
		return render(request, "admin/course/vocabularyitem/import_vocabulary.html", context)

	def save_model(self, request, obj, form, change):
		"""Auto-shuffle options and calculate correct_answer before saving."""
		import random
		
		# Create a list of all options with their labels
		options = [
			('A', obj.correct),
			('B', obj.wrong1),
			('C', obj.wrong2),
			('D', obj.wrong3),
		]
		
		# Shuffle the options
		random.shuffle(options)
		
		# Find which position the correct answer landed in
		for label, value in options:
			if value == obj.correct:
				obj.correct_answer = label
				break
		
		# Save the shuffled positions back to the model
		# Note: We're keeping the original fields as-is in the DB
		# The shuffle only determines correct_answer
		# The frontend will shuffle based on correct_answer when displaying
		
		super().save_model(request, obj, form, change)


@admin.register(GrammarContent)
class GrammarContentAdmin(admin.ModelAdmin):
	change_list_template = "admin/course/grammarcontent/change_list.html"
	list_display = ("unit", "exam", "title", "order")
	list_filter = ("unit__level", "unit", "exam")
	search_fields = ("title", "content")

	def get_urls(self):
		urls = super().get_urls()
		custom = [
			path(
				"import/",
				self.admin_site.admin_view(self.import_grammar_view),
				name="course_grammarcontent_import",
			),
		]
		return custom + urls

	def import_grammar_view(self, request):
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

			if df.shape[1] < 4:
				messages.error(request, "File must have 4 columns: unit_number, exam_code, title, content")
				return redirect("..")

			from administration.models import Exam

			created = 0
			updated = 0
			skipped = 0
			for _, row in df.iterrows():
				try:
					unit_value = _safe_int(row.iloc[0]) if pd.notna(row.iloc[0]) else None
					exam_code = str(row.iloc[1]).strip().upper() if pd.notna(row.iloc[1]) else ""
					title = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
					content = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""

					if not unit_value or not content:
						skipped += 1
						continue

					# Resolve/create unit from a numeric unit number (or legacy pk)
					unit = _resolve_or_create_unit(unit_value, exam_code)
					if unit is None:
						skipped += 1
						continue

					# Get exam if provided
					exam = None
					if exam_code:
						try:
							exam = Exam.objects.get(code=exam_code)
						except Exam.DoesNotExist:
							pass

					obj, was_created = GrammarContent.objects.update_or_create(
						unit=unit,
						title=title,
						defaults={
							"exam": exam,
							"content": content,
						},
					)
					if was_created:
						created += 1
					else:
						updated += 1
				except Exception:
					skipped += 1
					continue

			messages.success(
				request,
				f"Import completed: {created} created, {updated} updated, {skipped} skipped",
			)
			return redirect("..")

		context = dict(
			self.admin_site.each_context(request),
			title="Import Grammar",
		)
		return render(request, "admin/course/grammarcontent/import_grammar.html", context)


@admin.register(GrammarLearnItem)
class GrammarLearnItemAdmin(admin.ModelAdmin):
	change_list_template = "admin/course/grammarlearnitem/change_list.html"
	list_display = ("unit", "exam_code", "title", "topic_order", "visual_type")
	list_filter = ("unit__level", "unit", "exam_level", "exam_code", "visual_type")
	search_fields = ("title", "explanation", "exam_code")
	list_editable = ("topic_order",)
	fieldsets = (
		(
			"Core",
			{
				"fields": (
					"unit",
					"exam_level",
					"exam_code",
					"topic_order",
				)
			},
		),
		(
			"Content",
			{
				"fields": (
					"title",
					"main_character",
					"logic_formula",
					"explanation",
					"example_jp", "example_en",
					"visual_type",
					"pakka_tip",
				)
			},
		),
	)

	def get_urls(self):
		urls = super().get_urls()
		custom = [
			path(
				"import/",
				self.admin_site.admin_view(self.import_grammar_learn_view),
				name="course_grammarlearnitem_import",
			),
		]
		return custom + urls

	def import_grammar_learn_view(self, request):
		from administration.models import Exam
		import io

		# Step 1 – no POST yet: show upload form
		# Step 2 – file uploaded, no level chosen: parse file, show level chooser
		# Step 3 – file + level chosen: do the import

		# ── STAGE 3: actual import ──────────────────────────────────────────────
		if request.method == "POST" and request.POST.get("stage") == "import":
			level_id = _safe_int(request.POST.get("level_id"))
			raw_data = request.POST.get("raw_data", "")

			if not level_id or not raw_data:
				messages.error(request, "Missing level or data. Please start over.")
				return redirect(".")

			level = Level.objects.filter(pk=level_id).first()
			if not level:
				messages.error(request, "Selected level not found.")
				return redirect(".")

			try:
				import pandas as pd
				df = pd.read_csv(io.StringIO(raw_data))
			except Exception as e:
				messages.error(request, f"Failed to re-parse data: {e}")
				return redirect(".")

			# Derive exam from the level's linked Exam
			exam_obj = level.exam  # may be None
			exam_code_base = (exam_obj.code if exam_obj else "").strip().upper()
			# Numeric-only codes (e.g. "5") → prefix with N
			if exam_code_base.isdigit():
				exam_code_base = f"N{exam_code_base}"
			# Extract numeric part for exam_level field (N5 → 5)
			exam_level_int = 5
			if exam_code_base.upper().startswith("N"):
				try:
					exam_level_int = int(exam_code_base[1:])
				except ValueError:
					pass

			created = updated = skipped = 0
			errors = []

			REQUIRED = ["unit", "topic_order", "title", "logic_formula", "explanation"]

			for idx, row in df.iterrows():
				row_num = int(idx) + 2
				try:
					unit_num = _safe_int(row.get("unit") if hasattr(row, "get") else row["unit"])
					topic_order = _safe_int(row.get("topic_order") if hasattr(row, "get") else row["topic_order"])
					title = str(row.get("title", "") or "").strip()
					logic_formula = str(row.get("logic_formula", "") or "").strip()
					explanation = str(row.get("explanation", "") or "").strip()
					example_jp = str(row.get("example_jp", "") or "").strip()
					example_en = str(row.get("example_en", "") or "").strip()
					visual_type = str(row.get("visual_type", "") or "").strip()
					pakka_tip = str(row.get("pakka_tip", "") or "").strip()

					if not all([unit_num, topic_order, title, logic_formula, explanation]):
						skipped += 1
						errors.append(f"Row {row_num}: missing required field – skipped")
						continue

					# Resolve unit within the chosen level
					unit_obj, _ = Unit.objects.get_or_create(
						level=level,
						unit_number=unit_num,
						defaults={
							"name": f"Unit {unit_num}",
							"description": "",
							"is_active": True,
							"order": unit_num,
						},
					)

					exam_code = f"{exam_code_base}_G{unit_num:02d}"

					# unique key: one row per (unit, topic_order, example_jp)
					obj, was_created = GrammarLearnItem.objects.update_or_create(
						unit=unit_obj,
						topic_order=topic_order,
						example_jp=example_jp,
						defaults={
							"exam_level": exam_level_int,
							"exam_code": exam_code,
							"title": title,
							"logic_formula": logic_formula,
							"explanation": explanation,
							"example_en": example_en,
							"visual_type": visual_type,
							"pakka_tip": pakka_tip,
						},
					)
					if was_created:
						created += 1
					else:
						updated += 1
				except Exception as exc:
					skipped += 1
					errors.append(f"Row {row_num}: {exc}")
					continue

			summary = f"Import complete — {created} created, {updated} updated, {skipped} skipped."
			messages.success(request, summary)
			if errors:
				for e in errors[:10]:
					messages.warning(request, e)
			return redirect("..")

		# ── STAGE 2: file uploaded, choose level ──────────────────────────────
		if request.method == "POST" and request.POST.get("stage") == "choose_level":
			try:
				import pandas as pd
			except Exception:
				messages.error(request, "Missing dependency: pandas")
				return redirect(".")

			f = request.FILES.get("file")
			if not f:
				messages.error(request, "Please choose a file.")
				return redirect(".")

			name = (getattr(f, "name", "") or "").lower()
			try:
				if name.endswith(".csv"):
					df = pd.read_csv(f)
				else:
					df = pd.read_excel(f)
			except Exception as e:
				messages.error(request, f"Could not read file: {e}")
				return redirect(".")

			# Normalise column names
			df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

			REQUIRED_COLS = {"unit", "topic_order", "title", "logic_formula",
							 "explanation", "example_jp", "example_en"}
			missing = REQUIRED_COLS - set(df.columns)
			if missing:
				messages.error(request, f"Missing columns: {', '.join(sorted(missing))}")
				return redirect(".")

			# Serialise to CSV string to pass through the form
			raw_data = df.to_csv(index=False)
			preview_rows = df.head(5).to_dict("records")
			levels = Level.objects.select_related("exam").filter(is_active=True).order_by("level_number")
			total_rows = len(df)

			context = dict(
				self.admin_site.each_context(request),
				title="Import Grammar Learn Items — Select Level",
				raw_data=raw_data,
				preview_rows=preview_rows,
				levels=levels,
				total_rows=total_rows,
				stage="import",
			)
			return render(request, "admin/course/grammarlearnitem/import_grammar_learn.html", context)

		# ── STAGE 1: initial GET – show upload form ────────────────────────────
		context = dict(
			self.admin_site.each_context(request),
			title="Import Grammar Learn Items",
			stage="choose_level",
		)
		return render(request, "admin/course/grammarlearnitem/import_grammar_learn.html", context)


@admin.register(GrammarPakkaItem)
class GrammarPakkaItemAdmin(admin.ModelAdmin):
	change_list_template = "admin/course/grammarpakkaitem/change_list.html"
	list_display = ("unit", "exam_code", "step_type", "english_prompt", "order")
	list_filter = ("unit__level", "unit", "exam_level", "exam_code", "step_type")
	search_fields = ("english_prompt", "correct_sentence", "exam_code")
	list_editable = ("order",)
	fieldsets = (
		(
			"Core",
			{
				"fields": (
					"unit",
					"exam",
					"exam_level",
					"exam_code",
					"step_type",
					"order",
				)
			},
		),
		(
			"Question",
			{
				"fields": (
					"logic_formula",
					"english_prompt",
					"correct_sentence",
				)
			},
		),
		(
			"Answer Options",
			{
				"fields": (
					"word_blocks",
					"particle_target",
					"distractors",
					"explanation_hint",
				)
			},
		),
	)

	def get_urls(self):
		urls = super().get_urls()
		custom = [
			path(
				"import/",
				self.admin_site.admin_view(self.import_grammar_pakka_view),
				name="course_grammarpakkaitem_import",
			),
		]
		return custom + urls

	def import_grammar_pakka_view(self, request):
		import io

		def _null(val) -> str:
			"""Return blank for 'なし' or NaN-like values."""
			s = str(val or "").strip()
			return "" if s.lower() in ("なし", "nan", "none", "") else s

		# ── STAGE 3: actual import ──────────────────────────────────────────
		if request.method == "POST" and request.POST.get("stage") == "import":
			level_id = _safe_int(request.POST.get("level_id"))
			raw_data = request.POST.get("raw_data", "")

			if not level_id or not raw_data:
				messages.error(request, "Missing level or data. Please start over.")
				return redirect(".")

			level = Level.objects.filter(pk=level_id).first()
			if not level:
				messages.error(request, "Selected level not found.")
				return redirect(".")

			try:
				import pandas as pd
				df = pd.read_csv(io.StringIO(raw_data))
			except Exception as e:
				messages.error(request, f"Failed to re-parse data: {e}")
				return redirect(".")

			created = updated = skipped = 0
			errors = []

			for idx, row in df.iterrows():
				row_num = int(idx) + 2
				try:
					unit_num   = _safe_int(row.get("unit"))
					step_type  = _safe_int(row.get("step_type"))
					english    = _null(row.get("english_prompt", ""))
					correct    = _null(row.get("correct_sentence", ""))
					word_blks  = _null(row.get("word_blocks", ""))
					ptarget    = _null(row.get("particle_target", ""))
					distract   = _null(row.get("distractors", ""))
					hint       = _null(row.get("explanation_hint", ""))
					formula    = _null(row.get("logic_formula", ""))
					exam_level = _safe_int(row.get("exam_level")) or 5
					exam_code  = _null(row.get("exam_code", ""))
					order_val  = _safe_int(row.get("order")) or int(idx) + 1

					if not all([unit_num, step_type, english, correct]):
						skipped += 1
						errors.append(f"Row {row_num}: missing required field – skipped")
						continue

					unit_obj, _ = Unit.objects.get_or_create(
						level=level,
						unit_number=unit_num,
						defaults={
							"name": f"Unit {unit_num}",
							"description": "",
							"is_active": True,
							"order": unit_num,
						},
					)

					obj, was_created = GrammarPakkaItem.objects.update_or_create(
						unit=unit_obj,
						step_type=step_type,
						english_prompt=english,
						defaults={
							"exam_level": exam_level,
							"exam_code": exam_code,
							"logic_formula": formula,
							"correct_sentence": correct,
							"word_blocks": word_blks,
							"particle_target": ptarget,
							"distractors": distract,
							"explanation_hint": hint,
							"order": order_val,
						},
					)
					if was_created:
						created += 1
					else:
						updated += 1
				except Exception as exc:
					skipped += 1
					errors.append(f"Row {row_num}: {exc}")
					continue

			summary = f"Import complete — {created} created, {updated} updated, {skipped} skipped."
			messages.success(request, summary)
			for e in errors[:10]:
				messages.warning(request, e)
			return redirect("..")

		# ── STAGE 2: file uploaded, choose level ──────────────────────────
		if request.method == "POST" and request.POST.get("stage") == "choose_level":
			try:
				import pandas as pd
			except ImportError:
				messages.error(request, "Missing dependency: pandas")
				return redirect(".")

			f = request.FILES.get("file")
			if not f:
				messages.error(request, "Please choose a file.")
				return redirect(".")

			name = (getattr(f, "name", "") or "").lower()
			try:
				if name.endswith(".csv"):
					df = pd.read_csv(f)
				else:
					df = pd.read_excel(f)
			except Exception as e:
				messages.error(request, f"Could not read file: {e}")
				return redirect(".")

			df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

			REQUIRED_COLS = {"unit", "step_type", "english_prompt", "correct_sentence"}
			missing = REQUIRED_COLS - set(df.columns)
			if missing:
				messages.error(request, f"Missing columns: {', '.join(sorted(missing))}")
				return redirect(".")

			raw_data = df.to_csv(index=False)
			preview_rows = df.head(5).to_dict("records")
			levels = Level.objects.select_related("exam").filter(is_active=True).order_by("level_number")
			total_rows = len(df)

			context = dict(
				self.admin_site.each_context(request),
				title="Import Grammar Quiz Items — Select Level",
				raw_data=raw_data,
				preview_rows=preview_rows,
				levels=levels,
				total_rows=total_rows,
				stage="import",
			)
			return render(request, "admin/course/grammarpakkaitem/import_grammar_pakka.html", context)

		# ── STAGE 1: GET – show upload form ──────────────────────────────
		context = dict(
			self.admin_site.each_context(request),
			title="Import Grammar Quiz Items",
			stage="choose_level",
		)
		return render(request, "admin/course/grammarpakkaitem/import_grammar_pakka.html", context)
