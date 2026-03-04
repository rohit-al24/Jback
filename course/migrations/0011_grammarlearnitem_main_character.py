from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("course", "0010_fix_exam_level_mapping"),
    ]

    operations = [
        migrations.AddField(
            model_name="grammarlearnitem",
            name="main_character",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
