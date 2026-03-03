# Generated migration for course app
# Uses RunSQL because VocabularyItem is managed=False and cannot be resolved
# in Django's migration state graph.

from django.db import migrations


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS "course_uservocabstate" (
    "id"                INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "streak_correct"    INTEGER NOT NULL DEFAULT 0,
    "streak_normal"     INTEGER NOT NULL DEFAULT 0,
    "lapses"            INTEGER NOT NULL DEFAULT 0,
    "is_weak"           BOOL    NOT NULL DEFAULT 0,
    "mode"              VARCHAR(10) NOT NULL DEFAULT 'normal',
    "mastered"          BOOL    NOT NULL DEFAULT 0,
    "last_answered_at"  DATETIME,
    "due_at"            DATETIME,
    "half_life_days"    REAL    NOT NULL DEFAULT 1.0,
    "user_id"           INTEGER NOT NULL REFERENCES "core_user" ("id") DEFERRABLE INITIALLY DEFERRED,
    "vocab_item_id"     INTEGER NOT NULL REFERENCES "core_vocabularyitem" ("id") DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT "unique_user_vocab_state" UNIQUE ("user_id", "vocab_item_id")
)
"""

CREATE_INDEXES_SQL = [
    'CREATE INDEX IF NOT EXISTS "course_uservocabstate_user_mastered_idx" ON "course_uservocabstate" ("user_id", "mastered")',
    'CREATE INDEX IF NOT EXISTS "course_uservocabstate_user_due_idx"     ON "course_uservocabstate" ("user_id", "due_at")',
    'CREATE INDEX IF NOT EXISTS "course_uservocabstate_user_weak_idx"    ON "course_uservocabstate" ("user_id", "is_weak")',
    'CREATE INDEX IF NOT EXISTS "course_uservocabstate_last_ans"         ON "course_uservocabstate" ("last_answered_at")',
    'CREATE INDEX IF NOT EXISTS "course_uservocabstate_due_at"           ON "course_uservocabstate" ("due_at")',
]

DROP_TABLE_SQL = 'DROP TABLE IF EXISTS "course_uservocabstate"'


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        # Ensure core_vocabularyitem and core_user tables already exist
        ('core', '0010_add_exam_to_course_models'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_TABLE_SQL,
            reverse_sql=DROP_TABLE_SQL,
        ),
        *[
            migrations.RunSQL(sql=idx_sql, reverse_sql=migrations.RunSQL.noop)
            for idx_sql in CREATE_INDEXES_SQL
        ],
    ]
