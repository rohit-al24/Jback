"""Replace five numbered example_jp_N / example_en_N columns with a single
example_jp / example_en pair.  Existing data in _1 columns is preserved; _2–_5
are dropped (they were blank in production at this point).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("course", "0012_rename_example_fields_and_add_new_ones"),
    ]

    operations = [
        # Preserve row 1 data by renaming back to the canonical field names
        migrations.RenameField(
            model_name="grammarlearnitem",
            old_name="example_jp_1",
            new_name="example_jp",
        ),
        migrations.RenameField(
            model_name="grammarlearnitem",
            old_name="example_en_1",
            new_name="example_en",
        ),
        # Drop the extra numbered columns
        migrations.RemoveField(model_name="grammarlearnitem", name="example_jp_2"),
        migrations.RemoveField(model_name="grammarlearnitem", name="example_jp_3"),
        migrations.RemoveField(model_name="grammarlearnitem", name="example_jp_4"),
        migrations.RemoveField(model_name="grammarlearnitem", name="example_jp_5"),
        migrations.RemoveField(model_name="grammarlearnitem", name="example_en_2"),
        migrations.RemoveField(model_name="grammarlearnitem", name="example_en_3"),
        migrations.RemoveField(model_name="grammarlearnitem", name="example_en_4"),
        migrations.RemoveField(model_name="grammarlearnitem", name="example_en_5"),
    ]
