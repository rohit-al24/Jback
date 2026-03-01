from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_college_user_role_user_college"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="totp_secret",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="user",
            name="totp_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
