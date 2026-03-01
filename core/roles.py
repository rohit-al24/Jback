from __future__ import annotations

from django.contrib.auth.models import Group


ROLE_STUDENT = "student"
ROLE_SHITSUMON = "shitsumon"
ROLE_SENSEI = "sensei"

ALL_ROLES = (ROLE_STUDENT, ROLE_SHITSUMON, ROLE_SENSEI)


def ensure_role_groups(sender, **kwargs):
    """Ensure the role Groups exist.

    Runs on Django's post_migrate signal.
    """

    for role in ALL_ROLES:
        Group.objects.get_or_create(name=role)
