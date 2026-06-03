from __future__ import annotations

from django.conf import settings
from django.db import models


# ── Role constants (single source of truth) ─────────────────────────────────

ROLE_MASTER_ADMIN = "master_admin"
ROLE_COLLEGE_ADMIN = "college_admin"
ROLE_SENSEI = "sensei"
ROLE_STAFF = "staff"
ROLE_STUDENT = "student"

ALL_SYSTEM_ROLES = [
    ROLE_MASTER_ADMIN,
    ROLE_COLLEGE_ADMIN,
    ROLE_SENSEI,
    ROLE_STAFF,
    ROLE_STUDENT,
]

# role → list of page/resource codes it can access
ROLE_DEFAULT_PERMISSIONS: dict[str, list[str]] = {
    ROLE_MASTER_ADMIN: ["admin.*", "college.*", "global.*"],
    ROLE_COLLEGE_ADMIN: ["college.*", "department.*", "sensei.*", "class.*", "student.*", "staff.*", "request.*"],
    ROLE_SENSEI: ["sensei.classes", "sensei.students"],
    ROLE_STAFF: ["staff.mentees"],
    ROLE_STUDENT: ["student.profile", "student.mentor"],
}


class AdminPermission(models.Model):
	"""App-level permission catalogue (separate from Django's auth.Permission).

	This exists to satisfy product requirements for custom role/permission tables
	under the `administration` app.
	"""

	code = models.SlugField(max_length=64, unique=True)
	name = models.CharField(max_length=80)
	description = models.TextField(blank=True)
	is_active = models.BooleanField(default=True)

	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["code"]

	def __str__(self) -> str:
		return self.code


class Role(models.Model):
	name = models.CharField(max_length=40, unique=True)
	description = models.TextField(blank=True)
	is_active = models.BooleanField(default=True)

	permissions = models.ManyToManyField(
		AdminPermission,
		through="RolePermission",
		related_name="roles",
		blank=True,
	)

	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["name"]

	def __str__(self) -> str:
		return self.name


class RolePermission(models.Model):
	role = models.ForeignKey(Role, on_delete=models.CASCADE)
	permission = models.ForeignKey(AdminPermission, on_delete=models.CASCADE)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["role", "permission"], name="unique_role_permission"),
		]

	def __str__(self) -> str:
		return f"{self.role} → {self.permission}"


class UserRole(models.Model):
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	role = models.ForeignKey(Role, on_delete=models.CASCADE)

	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["user", "role"], name="unique_user_role"),
		]
		indexes = [models.Index(fields=["user", "role"])]

	def __str__(self) -> str:
		return f"{self.user} → {self.role}"


class Exam(models.Model):
	"""Exam levels (N5, N4, etc.) for Japanese language proficiency."""
	code = models.CharField(max_length=10, unique=True, help_text="Exam code (e.g., N5, N4)")
	name = models.CharField(max_length=100, help_text="Full name of the exam")
	description = models.TextField(blank=True)
	is_active = models.BooleanField(default=True)
	order = models.PositiveIntegerField(default=0)

	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["order", "code"]

	def __str__(self) -> str:
		return self.code


# ── School structure models ──────────────────────────────────────────────────

class CollegeDepartment(models.Model):
	"""A department within a college.

	`display_id` is a user-visible, editable ID (starts from 1, unique per college).
	"""

	display_id = models.PositiveIntegerField(
		help_text="Visible department ID (editable, unique per college)"
	)
	dep_name = models.CharField(max_length=120)
	college = models.ForeignKey(
		"core.College",
		on_delete=models.CASCADE,
		related_name="departments",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["college", "dep_name"], name="unique_dept_name_per_college"),
			models.UniqueConstraint(fields=["college", "display_id"], name="unique_dept_display_id_per_college"),
		]
		ordering = ["college", "display_id"]

	def __str__(self) -> str:
		return f"{self.college} / {self.dep_name} (#{self.display_id})"


class StudentProfile(models.Model):
	"""Extended profile for students."""

	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="student_profile",
	)
	register_number = models.CharField(max_length=60, unique=True)
	college = models.ForeignKey(
		"core.College",
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="student_profiles",
	)
	department = models.ForeignKey(
		CollegeDepartment,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="students",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self) -> str:
		return f"StudentProfile({self.user_id} | {self.register_number})"


class StaffProfile(models.Model):
	"""Extended profile for staff."""

	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="staff_profile",
	)
	staff_id = models.CharField(max_length=60, unique=True)
	college = models.ForeignKey(
		"core.College",
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="staff_profiles",
	)
	department = models.ForeignKey(
		CollegeDepartment,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="staff_members",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self) -> str:
		return f"StaffProfile({self.user_id} | {self.staff_id})"


class SchoolClass(models.Model):
	"""A class/section within a college (e.g. CS-A, EEE-B)."""

	name = models.CharField(max_length=80)
	college = models.ForeignKey(
		"core.College",
		on_delete=models.CASCADE,
		related_name="classes",
	)
	sensei = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="sensei_classes",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["college", "name"], name="unique_class_name_per_college"),
		]
		ordering = ["college", "name"]

	def __str__(self) -> str:
		return f"{self.college} / {self.name}"


class ClassStudent(models.Model):
	"""Many-to-many: students enrolled in a class."""

	school_class = models.ForeignKey(
		SchoolClass,
		on_delete=models.CASCADE,
		related_name="class_students",
	)
	student = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="enrolled_classes",
	)
	added_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["school_class", "student"], name="unique_class_student"),
		]

	def __str__(self) -> str:
		return f"{self.school_class} ← {self.student_id}"


class CollegeAdminAssignment(models.Model):
	"""Marks a user as the admin of a specific college."""

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="college_admin_of",
	)
	college = models.ForeignKey(
		"core.College",
		on_delete=models.CASCADE,
		related_name="college_admins",
	)
	assigned_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["user", "college"], name="unique_college_admin"),
		]

	def __str__(self) -> str:
		return f"CollegeAdmin({self.user_id} → {self.college_id})"


class SenseiAssignment(models.Model):
	"""Marks a user as a sensei within a college."""

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="sensei_of",
	)
	college = models.ForeignKey(
		"core.College",
		on_delete=models.CASCADE,
		related_name="senseis",
	)
	assigned_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=["user", "college"], name="unique_sensei_per_college"),
		]

	def __str__(self) -> str:
		return f"Sensei({self.user_id} @ {self.college_id})"


class MentorAssignment(models.Model):
	"""One-to-one: a staff member is mentor for a student."""

	student = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="mentor_assignment",
	)
	mentor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="mentees",
	)
	assigned_at = models.DateTimeField(auto_now_add=True)

	def __str__(self) -> str:
		return f"Mentor({self.mentor_id} → student {self.student_id})"


class MentorChangeRequest(models.Model):
	"""Student requests a change of mentor — goes to college admin."""

	class Status(models.TextChoices):
		PENDING = "pending", "Pending"
		APPROVED = "approved", "Approved"
		REJECTED = "rejected", "Rejected"

	student = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="mentor_change_requests",
	)
	requested_mentor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="incoming_mentor_requests",
	)
	college = models.ForeignKey(
		"core.College",
		on_delete=models.CASCADE,
		related_name="mentor_requests",
	)
	reason = models.TextField(blank=True)
	status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self) -> str:
		return f"MentorChangeRequest({self.student_id}, {self.status})"

