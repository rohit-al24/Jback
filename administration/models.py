from __future__ import annotations

from django.conf import settings
from django.db import models


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
