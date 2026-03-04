from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Import Pakka Grammar Learn cards from a CSV (Blueprint + Sensei tips)."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            type=str,
            help=(
                "Path to CSV with headers: exam_level, unit_id, topic_order, title, logic_formula, explanation, example_jp, example_en, visual_type, pakka_tip "
                "(exam_code optional; if omitted it is derived as N{exam_level}_G{unit_number:02d})."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate rows but do not write to the database.",
        )

    def handle(self, *args, **options):
        from course.models import GrammarLearnItem, Unit

        csv_path = Path(options["csv_path"])
        dry_run: bool = bool(options["dry_run"])

        if not csv_path.exists():
            raise CommandError(f"File not found: {csv_path}")

        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise CommandError("CSV has no headers")

            required = {
                "exam_level",
                "unit_id",
                "topic_order",
                "title",
                "logic_formula",
                "explanation",
                "example_jp",
                "example_en",
            }
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
                except ValueError:
                    raise CommandError(f"Row {i}: unit_id must be an integer")

                unit = Unit.objects.filter(pk=unit_id).first()
                if not unit:
                    raise CommandError(f"Row {i}: unit_id={unit_id} not found")

                exam_level_raw = (row.get("exam_level") or "").strip()
                exam_level = 0
                if exam_level_raw:
                    try:
                        exam_level = int(exam_level_raw)
                    except ValueError:
                        raise CommandError(f"Row {i}: exam_level must be an integer")

                if exam_level <= 0:
                    raise CommandError(f"Row {i}: exam_level is required and must be an integer greater than 0")

                exam_code = (row.get("exam_code") or "").strip().upper()
                if not exam_code:
                    exam_code = f"N{exam_level}_G{unit.unit_number:02d}"

                topic_order_raw = (row.get("topic_order") or row.get("order") or "").strip()
                topic_order = 0
                if topic_order_raw:
                    try:
                        topic_order = int(topic_order_raw)
                    except ValueError:
                        raise CommandError(f"Row {i}: topic_order must be an integer")

                title = (row.get("title") or "").strip()
                logic_formula = (row.get("logic_formula") or "").strip()
                explanation = (row.get("explanation") or "").strip()
                example_jp = (row.get("example_jp") or "").strip()
                example_en = (row.get("example_en") or "").strip()
                visual_type = (row.get("visual_type") or "").strip()
                pakka_tip = (row.get("pakka_tip") or row.get("sensei_tip") or "").strip()

                if not title:
                    raise CommandError(f"Row {i}: title is required")
                if not logic_formula:
                    raise CommandError(f"Row {i}: logic_formula is required")
                if not explanation:
                    raise CommandError(f"Row {i}: explanation is required")
                if not example_jp:
                    raise CommandError(f"Row {i}: example_jp is required")
                if not example_en:
                    raise CommandError(f"Row {i}: example_en is required")

                obj, was_created = GrammarLearnItem.objects.update_or_create(
                    unit=unit,
                    exam_code=exam_code,
                    topic_order=topic_order,
                    title=title,
                    defaults={
                        "exam_level": exam_level,
                        "logic_formula": logic_formula,
                        "explanation": explanation,
                        "example_jp": example_jp,
                        "example_en": example_en,
                        "visual_type": visual_type,
                        "pakka_tip": pakka_tip,
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
        self.stdout.write(self.style.SUCCESS(f"Imported Grammar Learn: created={created}, updated={updated}"))
