from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("course", "0008_grammar_learn_content"),
    ]

    operations = [
        migrations.AddField(
            model_name="grammarpakkaitem",
            name="distractors",
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name="GrammarLearnItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("exam_level", models.PositiveSmallIntegerField(default=5)),
                ("exam_code", models.CharField(max_length=32)),
                ("topic_order", models.PositiveIntegerField(default=0)),
                ("title", models.CharField(max_length=200)),
                ("logic_formula", models.CharField(blank=True, max_length=255)),
                ("explanation", models.TextField(blank=True)),
                ("example_jp", models.TextField(blank=True)),
                ("example_en", models.TextField(blank=True)),
                ("visual_type", models.CharField(blank=True, max_length=64)),
                ("pakka_tip", models.TextField(blank=True)),
                (
                    "unit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grammar_learn_items",
                        to="course.unit",
                    ),
                ),
            ],
            options={
                "db_table": "core_grammarlearnitem",
                "ordering": ["topic_order", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="grammarlearnitem",
            index=models.Index(fields=["unit", "topic_order"], name="gli_unit_topic_order_idx"),
        ),
        migrations.AddIndex(
            model_name="grammarlearnitem",
            index=models.Index(fields=["exam_level", "exam_code"], name="gli_exam_meta_idx"),
        ),
        migrations.AddIndex(
            model_name="grammarlearnitem",
            index=models.Index(fields=["unit", "exam_code"], name="gli_unit_exam_idx"),
        ),
    ]
