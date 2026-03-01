from django.contrib import admin

from .models import AdminPermission, Role, RolePermission, UserRole


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
	search_fields = ("user__username", "role__name")
	autocomplete_fields = ("user", "role")
