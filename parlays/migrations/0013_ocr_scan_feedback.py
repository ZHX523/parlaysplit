import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parlays", "0012_readable_public_slugs"),
    ]

    operations = [
        migrations.CreateModel(
            name="OCRScanFeedback",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("parser_sportsbook", models.CharField(blank=True, max_length=64)),
                (
                    "predicted_snapshot",
                    models.JSONField(
                        default=dict,
                        help_text="Normalized fields/ legs shown on the OCR review form.",
                    ),
                ),
                (
                    "submitted_snapshot",
                    models.JSONField(
                        default=dict,
                        help_text="Normalized parlay data the user actually created.",
                    ),
                ),
                (
                    "diff",
                    models.JSONField(
                        default=dict,
                        help_text="Field-by-field and leg-by-leg comparison.",
                    ),
                ),
                (
                    "was_edited",
                    models.BooleanField(
                        default=False,
                        help_text="True if any OCR-prefilled value differed from the submission.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "ocr_upload",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scan_feedback",
                        to="parlays.ocrupload",
                    ),
                ),
                (
                    "parlay",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ocr_scan_feedback",
                        to="parlays.parlay",
                    ),
                ),
            ],
            options={
                "verbose_name": "OCR scan feedback",
                "verbose_name_plural": "OCR scan feedback",
                "ordering": ["-created_at"],
            },
        ),
    ]
