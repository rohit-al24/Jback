from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("course", "0004_rename_uservocabstate_user_mastered_idx_course_user_user_id_9a6e8b_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="GrammarPakkaItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "step_type",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Blueprint"),
                            (2, "Builder"),
                            (3, "Heavy Loop"),
                            (4, "Beast Mode"),
                        ]
                    ),
                ),
                ("logic_formula", models.CharField(blank=True, max_length=255)),
                ("english_prompt", models.CharField(max_length=255)),
                ("correct_sentence", models.TextField()),
                ("word_blocks", models.TextField(blank=True)),
                ("particle_target", models.CharField(blank=True, max_length=32)),
                ("explanation_hint", models.TextField(blank=True)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "exam",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grammar_pakka_items",
                        to="administration.exam",
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grammar_pakka",
                        to="course.unit",
                    ),
                ),
            ],
            options={
                "db_table": "core_grammarpakkaitem",
                "ordering": ["order", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="grammarpakkaitem",
            index=models.Index(fields=["unit", "step_type", "order"], name="gpi_unit_step_order_idx"),
        ),
        migrations.AddConstraint(
            model_name="grammarpakkaitem",
            constraint=models.UniqueConstraint(
                fields=("unit", "step_type", "english_prompt"),
                name="unique_grammarpakka_unit_step_prompt",
            ),
        ),
    ]
