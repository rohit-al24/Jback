"""
Migration: adds school structure models.
- CollegeDepartment
- StudentProfile
- StaffProfile
- SchoolClass
- ClassStudent
- CollegeAdminAssignment
- SenseiAssignment
- MentorAssignment
- MentorChangeRequest
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('administration', '0002_exam'),
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CollegeDepartment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('display_id', models.PositiveIntegerField(help_text='Visible department ID (editable, unique per college)')),
                ('dep_name', models.CharField(max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('college', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='departments', to='core.college')),
            ],
            options={'ordering': ['college', 'display_id']},
        ),
        migrations.AddConstraint(
            model_name='collegedepartment',
            constraint=models.UniqueConstraint(fields=['college', 'dep_name'], name='unique_dept_name_per_college'),
        ),
        migrations.AddConstraint(
            model_name='collegedepartment',
            constraint=models.UniqueConstraint(fields=['college', 'display_id'], name='unique_dept_display_id_per_college'),
        ),
        migrations.CreateModel(
            name='StudentProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('register_number', models.CharField(max_length=60, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='student_profile', to=settings.AUTH_USER_MODEL)),
                ('college', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_profiles', to='core.college')),
                ('department', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='students', to='administration.collegedepartment')),
            ],
        ),
        migrations.CreateModel(
            name='StaffProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('staff_id', models.CharField(max_length=60, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='staff_profile', to=settings.AUTH_USER_MODEL)),
                ('college', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='staff_profiles', to='core.college')),
                ('department', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='staff_members', to='administration.collegedepartment')),
            ],
        ),
        migrations.CreateModel(
            name='SchoolClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('college', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='classes', to='core.college')),
                ('sensei', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sensei_classes', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['college', 'name']},
        ),
        migrations.AddConstraint(
            model_name='schoolclass',
            constraint=models.UniqueConstraint(fields=['college', 'name'], name='unique_class_name_per_college'),
        ),
        migrations.CreateModel(
            name='ClassStudent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('school_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_students', to='administration.schoolclass')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrolled_classes', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='classstudent',
            constraint=models.UniqueConstraint(fields=['school_class', 'student'], name='unique_class_student'),
        ),
        migrations.CreateModel(
            name='CollegeAdminAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='college_admin_of', to=settings.AUTH_USER_MODEL)),
                ('college', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='college_admins', to='core.college')),
            ],
        ),
        migrations.AddConstraint(
            model_name='collegeadminassignment',
            constraint=models.UniqueConstraint(fields=['user', 'college'], name='unique_college_admin'),
        ),
        migrations.CreateModel(
            name='SenseiAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sensei_of', to=settings.AUTH_USER_MODEL)),
                ('college', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='senseis', to='core.college')),
            ],
        ),
        migrations.AddConstraint(
            model_name='senseiassignment',
            constraint=models.UniqueConstraint(fields=['user', 'college'], name='unique_sensei_per_college'),
        ),
        migrations.CreateModel(
            name='MentorAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mentor_assignment', to=settings.AUTH_USER_MODEL)),
                ('mentor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentees', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='MentorChangeRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentor_change_requests', to=settings.AUTH_USER_MODEL)),
                ('requested_mentor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incoming_mentor_requests', to=settings.AUTH_USER_MODEL)),
                ('college', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentor_requests', to='core.college')),
            ],
        ),
    ]
