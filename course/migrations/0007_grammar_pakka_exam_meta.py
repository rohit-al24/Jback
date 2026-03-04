from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("course", "0006_level_exam_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="grammarpakkaitem",
            name="exam_level",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="grammarpakkaitem",
            name="exam_code",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddIndex(
            model_name="grammarpakkaitem",
            index=models.Index(fields=["exam_level", "exam_code"], name="gpi_exam_meta_idx"),
        ),
    ]
