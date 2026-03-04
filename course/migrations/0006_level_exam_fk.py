"""Add exam_id FK to core_level so each Level maps to an Exam (N5/N4 etc.)."""

import django.db.models.deletion
from django.db import migrations, models


ADD_SQL = """
ALTER TABLE core_level ADD COLUMN exam_id INTEGER NULL
    REFERENCES administration_exam(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS core_level_exam_id_idx ON core_level(exam_id);
"""

REVERSE_SQL = """
-- SQLite does not support DROP COLUMN in older versions; leave it.
"""


class Migration(migrations.Migration):

    dependencies = [
        ('administration', '0002_exam'),
        ('course', '0005_grammar_pakka_item'),
    ]

    operations = [
        migrations.RunSQL(ADD_SQL, reverse_sql=REVERSE_SQL),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='level',
                    name='exam',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='levels',
                        to='administration.exam',
                    ),
                ),
            ],
        ),
    ]
