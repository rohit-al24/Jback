"""
Data migration: seed system roles + default permissions into the administration.Role
and administration.AdminPermission tables.
"""
from django.db import migrations


ROLES = [
    ("master_admin", "Master Administrator — full system access"),
    ("college_admin", "College Administrator — manages one or more colleges"),
    ("sensei", "Sensei — teacher assigned to classes"),
    ("staff", "Staff — college staff member / mentor"),
    ("student", "Student — enrolled student"),
]

# (role_name, [permission_codes])
PERMISSIONS: dict[str, list[tuple[str, str]]] = {
    "master_admin": [
        ("admin.colleges.view", "View all colleges"),
        ("admin.colleges.manage", "Create / edit colleges"),
        ("admin.users.view", "View all users"),
        ("admin.college_admin.assign", "Assign college admins"),
        ("global.dashboard", "Access global dashboard"),
    ],
    "college_admin": [
        ("college.departments.manage", "Manage departments"),
        ("college.sensei.manage", "Manage senseis"),
        ("college.classes.manage", "Manage classes"),
        ("college.students.view", "View students"),
        ("college.staff.view", "View staff"),
        ("college.requests.manage", "Manage mentor requests"),
    ],
    "sensei": [
        ("sensei.classes.view", "View assigned classes"),
        ("sensei.students.view", "View students in classes"),
    ],
    "staff": [
        ("staff.mentees.view", "View own mentees"),
    ],
    "student": [
        ("student.profile.view", "View own profile"),
        ("student.mentor.view", "View own mentor"),
        ("student.mentor.request_change", "Request mentor change"),
    ],
}


def seed_roles(apps, schema_editor):
    Role = apps.get_model("administration", "Role")
    AdminPermission = apps.get_model("administration", "AdminPermission")
    RolePermission = apps.get_model("administration", "RolePermission")

    for role_name, role_desc in ROLES:
        role, _ = Role.objects.get_or_create(name=role_name, defaults={"description": role_desc})
        for perm_code, perm_name in PERMISSIONS.get(role_name, []):
            perm, _ = AdminPermission.objects.get_or_create(
                code=perm_code,
                defaults={"name": perm_name},
            )
            RolePermission.objects.get_or_create(role=role, permission=perm)


def unseed_roles(apps, schema_editor):
    Role = apps.get_model("administration", "Role")
    role_names = [r[0] for r in ROLES]
    Role.objects.filter(name__in=role_names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("administration", "0003_school_structure"),
    ]

    operations = [
        migrations.RunPython(seed_roles, reverse_code=unseed_roles),
    ]
