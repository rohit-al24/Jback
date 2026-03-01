from __future__ import annotations

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_user_totp_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="mondai",
            name="week_start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="mondai",
            name="week_end_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="XPEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("points", models.IntegerField()),
                ("reason", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField(db_index=True, default=timezone.now)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="xp_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["created_at"], name="core_xpevent_created_at_idx"),
                    models.Index(fields=["user", "created_at"], name="core_xpevent_user_created_at_idx"),
                ]
            },
        ),
        migrations.CreateModel(
            name="DailyQuizTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("target_questions", models.PositiveIntegerField(default=10)),
                ("answered_questions", models.PositiveIntegerField(default=0)),
                ("rewarded", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["user", "date"], name="core_dailyquiztask_user_date_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "date"), name="unique_daily_quiz_task"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MondaiAnswerAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("selected", models.CharField(max_length=1)),
                ("correct", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=timezone.now)),
                (
                    "mondai_question",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="core.mondaiquestion"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "date"], name="core_mondaiattempt_user_date_idx"),
                    models.Index(fields=["mondai_question", "date"], name="core_mondaiattempt_q_date_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "mondai_question", "date"), name="unique_mondai_attempt_per_day"),
                ],
            },
        ),
    ]
