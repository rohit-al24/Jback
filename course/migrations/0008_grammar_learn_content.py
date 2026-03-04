from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("course", "0007_grammar_pakka_exam_meta"),
    ]

    operations = [
        migrations.CreateModel(
            name="GrammarLearnContent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("exam_level", models.PositiveSmallIntegerField(default=1)),
                ("exam_code", models.CharField(blank=True, max_length=32)),
                ("section_title", models.CharField(max_length=200)),
                ("visual_type", models.CharField(max_length=64)),
                ("content_body", models.TextField()),
                ("sensei_tip", models.TextField(blank=True)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "unit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grammar_learn",
                        to="course.unit",
                    ),
                ),
            ],
            options={
                "db_table": "core_grammarlearncontent",
                "ordering": ["order", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="grammarlearncontent",
            index=models.Index(fields=["unit", "order"], name="glc_unit_order_idx"),
        ),
        migrations.AddIndex(
            model_name="grammarlearncontent",
            index=models.Index(fields=["exam_level", "exam_code"], name="glc_exam_meta_idx"),
        ),
        migrations.AddIndex(
            model_name="grammarlearncontent",
            index=models.Index(fields=["unit", "exam_code"], name="glc_unit_exam_idx"),
        ),
    ]
