from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Import Grammar Pakka items from a CSV matching the 8-column structure."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            type=str,
            help=(
                "Path to CSV file with headers: unit_id, step_type, exam_level, exam_code, logic_formula, english_prompt, correct_sentence, "
                "word_blocks, particle_target, distractors, explanation_hint (distractors optional; exam_* optional)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate rows but do not write to the database.",
        )

    def handle(self, *args, **options):
        from course.models import GrammarPakkaItem, Unit
        from administration.models import Exam

        csv_path = Path(options["csv_path"])
        dry_run: bool = bool(options["dry_run"])

        if not csv_path.exists():
            raise CommandError(f"File not found: {csv_path}")

        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            required = {
                "unit_id",
                "step_type",
                "logic_formula",
                "english_prompt",
                "correct_sentence",
                "word_blocks",
                "particle_target",
                "explanation_hint",
            }
            if not reader.fieldnames:
                raise CommandError("CSV has no headers")

            header_set = set(reader.fieldnames)
            missing = required - header_set
            if missing:
                raise CommandError(f"Missing required columns: {', '.join(sorted(missing))}")

            rows = list(reader)

        created = 0
        updated = 0

        @transaction.atomic
        def _write():
            nonlocal created, updated

            for i, row in enumerate(rows, start=2):
                try:
                    unit_id = int((row.get("unit_id") or "").strip())
                    step_type = int((row.get("step_type") or "").strip())
                except ValueError:
                    raise CommandError(f"Row {i}: unit_id and step_type must be integers")

                # Optional extended metadata
                exam_level_raw = (row.get("exam_level") or "").strip()
                exam_code = (row.get("exam_code") or "").strip().upper()
                exam_level = 1
                if exam_level_raw:
                    try:
                        exam_level = int(exam_level_raw)
                    except ValueError:
                        raise CommandError(f"Row {i}: exam_level must be an integer")
                else:
                    # Infer from exam_code prefix like N5_...
                    if exam_code.startswith("N5"):
                        exam_level = 5
                    elif exam_code.startswith("N4"):
                        exam_level = 4
                    elif exam_code.startswith("N3"):
                        exam_level = 3
                    elif exam_code.startswith("N2"):
                        exam_level = 2
                    elif exam_code.startswith("N1"):
                        exam_level = 1

                exam_fk = None
                if exam_code.startswith("N5"):
                    exam_fk = Exam.objects.filter(code="N5").first()
                elif exam_code.startswith("N4"):
                    exam_fk = Exam.objects.filter(code="N4").first()

                unit = Unit.objects.filter(pk=unit_id).first()
                if not unit:
                    raise CommandError(f"Row {i}: unit_id={unit_id} not found")

                logic_formula = (row.get("logic_formula") or "").strip()
                english_prompt = (row.get("english_prompt") or "").strip()
                correct_sentence = (row.get("correct_sentence") or "").strip()
                word_blocks = (row.get("word_blocks") or "").strip()
                particle_target = (row.get("particle_target") or "").strip()
                distractors = (row.get("distractors") or "").strip()
                explanation_hint = (row.get("explanation_hint") or "").strip()

                if not english_prompt:
                    raise CommandError(f"Row {i}: english_prompt is required")
                if not correct_sentence:
                    raise CommandError(f"Row {i}: correct_sentence is required")

                obj, was_created = GrammarPakkaItem.objects.update_or_create(
                    unit=unit,
                    step_type=step_type,
                    english_prompt=english_prompt,
                    defaults={
                        "exam": exam_fk,
                        "exam_level": exam_level,
                        "exam_code": exam_code,
                        "logic_formula": logic_formula,
                        "correct_sentence": correct_sentence,
                        "word_blocks": word_blocks,
                        "particle_target": particle_target,
                        "distractors": distractors,
                        "explanation_hint": explanation_hint,
                    },
                )

                if was_created:
                    created += 1
                else:
                    updated += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry run: validated {len(rows)} rows"))
            return

        _write()
        self.stdout.write(self.style.SUCCESS(f"Imported Grammar Pakka: created={created}, updated={updated}"))
