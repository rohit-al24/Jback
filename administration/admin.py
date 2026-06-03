from django.contrib import admin

from .models import (
    AdminPermission, Role, RolePermission, UserRole, Exam,
    CollegeDepartment, StudentProfile, StaffProfile, SchoolClass,
    ClassStudent, CollegeAdminAssignment, SenseiAssignment,
    MentorAssignment, MentorChangeRequest,
)


@admin.register(AdminPermission)
class AdminPermissionAdmin(admin.ModelAdmin):
	list_display = ("code", "name", "is_active", "created_at")
	list_filter = ("is_active",)
	search_fields = ("code", "name")


class RolePermissionInline(admin.TabularInline):
	model = RolePermission
	extra = 0
	autocomplete_fields = ("permission",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
	list_display = ("name", "is_active", "created_at")
	list_filter = ("is_active",)
	search_fields = ("name",)
	inlines = (RolePermissionInline,)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
	list_display = ("user", "role", "created_at")
	list_filter = ("role",)
	search_fields = ("user__username",)
	autocomplete_fields = ("user", "role")


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
	list_display = ("code", "name", "is_active", "order")
	list_filter = ("is_active",)


@admin.register(CollegeDepartment)
class CollegeDepartmentAdmin(admin.ModelAdmin):
	list_display = ("dep_name", "display_id", "college", "created_at")
	list_filter = ("college",)
	search_fields = ("dep_name",)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "register_number", "college", "department", "created_at")
	list_filter = ("college", "department")
	search_fields = ("register_number", "user__username", "user__email")


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "staff_id", "college", "department", "created_at")
	list_filter = ("college", "department")
	search_fields = ("staff_id", "user__username", "user__email")


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
	list_display = ("name", "college", "sensei", "created_at")
	list_filter = ("college",)
	search_fields = ("name",)


@admin.register(ClassStudent)
class ClassStudentAdmin(admin.ModelAdmin):
	list_display = ("school_class", "student", "added_at")
	list_filter = ("school_class__college",)


@admin.register(CollegeAdminAssignment)
class CollegeAdminAssignmentAdmin(admin.ModelAdmin):
	list_display = ("user", "college", "assigned_at")
	list_filter = ("college",)


@admin.register(SenseiAssignment)
class SenseiAssignmentAdmin(admin.ModelAdmin):
	list_display = ("user", "college", "assigned_at")
	list_filter = ("college",)


@admin.register(MentorAssignment)
class MentorAssignmentAdmin(admin.ModelAdmin):
	list_display = ("mentor", "student", "assigned_at")


@admin.register(MentorChangeRequest)
class MentorChangeRequestAdmin(admin.ModelAdmin):
	list_display = ("student", "requested_mentor", "college", "status", "created_at")
	list_filter = ("status", "college")
