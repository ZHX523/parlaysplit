"""
Export compact OCR correction rows (JSON Lines).

Usage:
  python manage.py export_ocr_feedback --edited-only
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from parlays.models import OCRScanFeedback


class Command(BaseCommand):
    help = "Export compact OCR correction logs as JSONL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default="ocr_feedback_export.jsonl",
            help="Output file path.",
        )
        parser.add_argument(
            "--edited-only",
            action="store_true",
            help="Only rows where the user changed OCR prefill.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max rows (0 = all).",
        )
        parser.add_argument(
            "--include-parsed",
            action="store_true",
            help="Include full parsed_data/raw_text (much larger files).",
        )

    def handle(self, *args, **options):
        qs = OCRScanFeedback.objects.select_related("ocr_upload").order_by("-created_at")
        if options["edited_only"]:
            qs = qs.filter(was_edited=True)
        if options["limit"]:
            qs = qs[: options["limit"]]

        out_path = Path(options["out"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with out_path.open("w", encoding="utf-8") as fh:
            for row in qs.iterator():
                record = {
                    "ocr_upload_id": str(row.ocr_upload_id),
                    "parlay_id": str(row.parlay_id) if row.parlay_id else None,
                    "parser_sportsbook": row.parser_sportsbook,
                    "was_edited": row.was_edited,
                    "predicted_leg_count": row.predicted_leg_count,
                    "submitted_leg_count": row.submitted_leg_count,
                    "corrections": row.corrections,
                    "created_at": row.created_at.isoformat(),
                }
                if options["include_parsed"]:
                    record["parsed_data"] = row.ocr_upload.parsed_data
                    record["raw_text"] = row.ocr_upload.raw_text
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Exported {count} row(s) to {out_path}")
        )
