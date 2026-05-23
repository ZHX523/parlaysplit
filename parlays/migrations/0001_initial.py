import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Parlay",
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
                ("slug", models.SlugField(editable=False, max_length=12, unique=True)),
                ("creator_nickname", models.CharField(max_length=64)),
                (
                    "sportsbook",
                    models.CharField(
                        choices=[
                            ("fanduel", "FanDuel"),
                            ("draftkings", "DraftKings"),
                            ("betmgm", "BetMGM"),
                            ("caesars", "Caesars"),
                            ("espnbet", "ESPN BET"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=32,
                    ),
                ),
                (
                    "odds_american",
                    models.IntegerField(
                        blank=True,
                        help_text="American odds, e.g. +450",
                        null=True,
                    ),
                ),
                (
                    "odds_decimal",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=10, null=True
                    ),
                ),
                (
                    "wager_amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=12,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0.01"))
                        ],
                    ),
                ),
                (
                    "potential_payout",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0.00"))
                        ],
                    ),
                ),
                ("external_link", models.URLField(blank=True, max_length=500)),
                ("notes", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("open", "Open for participants"),
                            ("locked", "Locked"),
                            ("settled", "Settled (informational)"),
                        ],
                        default="open",
                        max_length=16,
                    ),
                ),
                ("is_public", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name_plural": "parlays",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="OCRUpload",
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
                ("image", models.ImageField(upload_to="ocr/%Y/%m/%d/")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("raw_text", models.TextField(blank=True)),
                ("parsed_data", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "parlay",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ocr_uploads",
                        to="parlays.parlay",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ParlayLeg",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("description", models.CharField(max_length=500)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "parlay",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="legs",
                        to="parlays.parlay",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "created_at"],
            },
        ),
        migrations.CreateModel(
            name="Participant",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nickname", models.CharField(max_length=64)),
                (
                    "contribution_amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0.01"))
                        ],
                    ),
                ),
                (
                    "session_key",
                    models.CharField(blank=True, db_index=True, max_length=64),
                ),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "parlay",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participants",
                        to="parlays.parlay",
                    ),
                ),
            ],
            options={
                "ordering": ["-joined_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="participant",
            constraint=models.UniqueConstraint(
                fields=("parlay", "nickname"),
                name="unique_participant_nickname_per_parlay",
            ),
        ),
    ]
