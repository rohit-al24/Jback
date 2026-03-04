from django.db import migrations


def _infer_level(exam_code: str) -> int | None:
    code = (exam_code or "").upper()
    if code.startswith("N5"):
        return 5
    if code.startswith("N4"):
        return 4
    if code.startswith("N3"):
        return 3
    if code.startswith("N2"):
        return 2
    if code.startswith("N1"):
        return 1
    return None


def forwards(apps, schema_editor):
    GrammarPakkaItem = apps.get_model("course", "GrammarPakkaItem")
    GrammarLearnItem = apps.get_model("course", "GrammarLearnItem")

    for prefix, level in (("N5", 5), ("N4", 4), ("N3", 3), ("N2", 2), ("N1", 1)):
        GrammarPakkaItem.objects.filter(exam_code__startswith=prefix).exclude(exam_level=level).update(exam_level=level)
        GrammarLearnItem.objects.filter(exam_code__startswith=prefix).exclude(exam_level=level).update(exam_level=level)

    # Also fix rows where exam_level is 0/1 but exam_code is known
    for Model in (GrammarPakkaItem, GrammarLearnItem):
        for obj in Model.objects.filter(exam_level__in=[0, 1]).exclude(exam_code="").only("id", "exam_code", "exam_level"):
            inferred = _infer_level(obj.exam_code)
            if inferred and obj.exam_level != inferred:
                Model.objects.filter(pk=obj.pk).update(exam_level=inferred)


def backwards(apps, schema_editor):
    # No-op: leaving normalized values in place is safe.
    return


class Migration(migrations.Migration):
    dependencies = [
        ("course", "0009_grammar_learn_item_and_distractors"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
