import uuid

from decimal import Decimal



from django.conf import settings

from django.core.validators import MaxValueValidator, MinValueValidator

from django.db import models

from django.db.models import Sum

from django.utils import timezone





class LegType(models.TextChoices):

    MONEYLINE = "moneyline", "Moneyline"

    SPREAD = "spread", "Spread"

    TOTAL_POINTS = "total_points", "Total Points"

    PLAYER_PROP = "player_prop", "Player Prop"


LEG_TYPE_DESCRIPTION_HINTS = {
    LegType.MONEYLINE: "Knicks to win",
    LegType.SPREAD: "Chiefs -3.5",
    LegType.TOTAL_POINTS: "Over 8.5 runs",
    LegType.PLAYER_PROP: "Jalen Brunson Over 25 points",
}



class ParlayStatus(models.TextChoices):

    DRAFT = "draft", "Draft"

    OPEN = "open", "Open for participants"

    LOCKED = "locked", "Locked"

    SETTLED = "settled", "Settled (informational)"





class Parlay(models.Model):

    """A shareable group parlay coordination record."""



    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    slug = models.SlugField(
        max_length=96,
        unique=True,
        editable=False,
        help_text="Public URL segment, e.g. jordan-parlay-3-legs-x7k2m9.",
    )
    host_code = models.CharField(
        max_length=8,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Alphanumeric code for the host to find and manage this parlay (expires after 72 hours).",
    )
    host_code_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="After this time the parlay is unavailable (public and host pages).",
    )

    creator_nickname = models.CharField(max_length=64, default="HOST")

    odds_american = models.IntegerField(

        null=True,

        blank=True,

        help_text="American odds, e.g. +450",

    )

    odds_decimal = models.DecimalField(

        max_digits=10,

        decimal_places=4,

        null=True,

        blank=True,

    )

    wager_amount = models.DecimalField(

        max_digits=12,

        decimal_places=2,

        validators=[MinValueValidator(Decimal("0.01"))],

        default=Decimal("0.00"),

    )

    potential_payout = models.DecimalField(

        max_digits=12,

        decimal_places=2,

        null=True,

        blank=True,

        validators=[MinValueValidator(Decimal("0.00"))],

    )

    split_offered_percent = models.DecimalField(

        max_digits=5,

        decimal_places=2,

        default=Decimal("100.00"),

        validators=[

            MinValueValidator(Decimal("1")),

            MaxValueValidator(Decimal("100")),

        ],

        help_text="Percent of wager friends may claim in total (host keeps the rest).",

    )

    external_link = models.URLField(max_length=500, blank=True)

    notes = models.TextField(blank=True)

    status = models.CharField(

        max_length=16,

        choices=ParlayStatus.choices,

        default=ParlayStatus.OPEN,

    )

    is_public = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)



    class Meta:

        ordering = ["-created_at"]

        verbose_name_plural = "parlays"



    def __str__(self):

        return f"Parlay {self.slug} by {self.creator_nickname}"



    def save(self, *args, **kwargs):
        from datetime import timedelta

        ttl_hours = getattr(settings, "HOST_CODE_TTL_HOURS", 72)
        if not self.slug:
            self.slug = f"pending-{uuid.uuid4().hex[:10]}"
        if not self.host_code_expires_at:
            self.host_code_expires_at = timezone.now() + timedelta(hours=ttl_hours)
        if not self.host_code and not self.is_expired:
            from .utils import generate_host_code

            self.host_code = generate_host_code()
        super().save(*args, **kwargs)

    @property
    def access_expires_at(self):
        from datetime import timedelta

        if self.host_code_expires_at:
            return self.host_code_expires_at
        if self.created_at:
            return self.created_at + timedelta(
                hours=getattr(settings, "HOST_CODE_TTL_HOURS", 72)
            )
        return None

    @property
    def is_expired(self) -> bool:
        expires = self.access_expires_at
        return expires is not None and timezone.now() >= expires

    def clear_host_code_if_expired(self) -> bool:
        """Remove host_code when past expiry; returns True if cleared."""
        if not self.is_expired or not self.host_code:
            return False
        self.host_code = None
        self.save(update_fields=["host_code", "updated_at"])
        return True

    @property
    def host_code_active(self) -> bool:
        return bool(self.host_code) and not self.is_expired

    def get_absolute_url(self) -> str:
        return f"/p/{self.slug}/"

    @property
    def share_url(self):
        """Public link for friends to view and join."""
        return f"{settings.SITE_URL}{self.get_absolute_url()}"

    @property
    def host_url(self):
        """Host link to manage the parlay (do not share with participants)."""
        return f"{settings.SITE_URL}/host/{self.host_code}/"



    def _contributions_sum(self, *, status: str | None = None) -> Decimal:
        qs = self.participants
        if status is not None:
            qs = qs.filter(status=status)
        total = qs.aggregate(total=Sum("contribution_amount"))["total"]
        return total or Decimal("0.00")

    @property

    def total_contributions(self) -> Decimal:

        return self._contributions_sum(status=ParticipantStatus.APPROVED)

    @property

    def pending_contributions_total(self) -> Decimal:

        return self._contributions_sum(status=ParticipantStatus.PENDING)

    @property

    def participant_count(self) -> int:

        return self.participants.count()

    @property

    def approved_participant_count(self) -> int:

        return self.participants.filter(status=ParticipantStatus.APPROVED).count()

    @property

    def friends_have_joined(self) -> bool:

        """True when at least one friend is approved on the parlay."""

        return self.participants.filter(status=ParticipantStatus.APPROVED).exists()



    @property

    def max_friends_stake(self) -> Decimal:

        """Dollar amount friends may claim in aggregate."""

        if self.wager_amount <= 0:

            return Decimal("0.00")

        pool = self.wager_amount * (self.split_offered_percent / Decimal("100"))

        return pool.quantize(Decimal("0.01"))



    @property

    def host_reserved_stake(self) -> Decimal:

        """Minimum wager slice reserved for the host."""

        reserved = self.wager_amount - self.max_friends_stake

        return max(Decimal("0.00"), reserved).quantize(Decimal("0.01"))



    @property

    def host_reserved_percent(self) -> Decimal:

        return (Decimal("100") - self.split_offered_percent).quantize(Decimal("0.01"))



    @property

    def remaining_for_friends(self) -> Decimal:

        """Wager dollars still available for friends to claim (approved + pending holds)."""

        claimed = self.total_contributions + self.pending_contributions_total

        remaining = self.max_friends_stake - claimed

        return max(Decimal("0.00"), remaining).quantize(Decimal("0.01"))



    @property

    def host_stake_amount(self) -> Decimal:

        """Wager slice kept by the host (wager minus friend contributions)."""

        remaining = self.wager_amount - self.total_contributions

        return max(Decimal("0.00"), remaining).quantize(Decimal("0.01"))



    @property

    def remaining_wager(self) -> Decimal:

        return self.remaining_for_friends



    def _share_of_wager(self, amount: Decimal) -> Decimal | None:

        if self.wager_amount <= 0:

            return None

        return amount / self.wager_amount



    def ownership_percent_for(self, contribution: Decimal) -> Decimal | None:

        share = self._share_of_wager(contribution)

        if share is None:

            return None

        return (share * Decimal("100")).quantize(Decimal("0.01"))



    def host_ownership_percent(self) -> Decimal | None:

        return self.ownership_percent_for(self.host_stake_amount)



    def estimated_payout_for(self, contribution: Decimal) -> Decimal | None:

        if not self.potential_payout:

            return None

        share = self._share_of_wager(contribution)

        if share is None:

            return None

        return (self.potential_payout * share).quantize(Decimal("0.01"))



    def host_estimated_payout(self) -> Decimal | None:

        return self.estimated_payout_for(self.host_stake_amount)





class ParlayLeg(models.Model):

    parlay = models.ForeignKey(

        Parlay,

        on_delete=models.CASCADE,

        related_name="legs",

    )

    leg_type = models.CharField(

        max_length=32,

        choices=LegType.choices,

        default=LegType.MONEYLINE,

    )

    description = models.CharField(max_length=500)

    sort_order = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)



    class Meta:

        ordering = ["sort_order", "created_at"]



    def __str__(self):

        return f"{self.get_leg_type_display()}: {self.description[:60]}"





class ParticipantStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"


class Participant(models.Model):

    parlay = models.ForeignKey(

        Parlay,

        on_delete=models.CASCADE,

        related_name="participants",

    )

    nickname = models.CharField(max_length=64)

    contribution_amount = models.DecimalField(

        max_digits=12,

        decimal_places=2,

        validators=[MinValueValidator(Decimal("0.01"))],

    )

    session_key = models.CharField(max_length=64, blank=True, db_index=True)

    status = models.CharField(
        max_length=16,
        choices=ParticipantStatus.choices,
        default=ParticipantStatus.APPROVED,
        db_index=True,
    )

    joined_at = models.DateTimeField(auto_now_add=True)



    class Meta:

        ordering = ["-joined_at"]

        constraints = [

            models.UniqueConstraint(

                fields=["parlay", "nickname"],

                name="unique_participant_nickname_per_parlay",

            ),

        ]



    def __str__(self):

        from .utils import format_dollars

        return f"{self.nickname} ({format_dollars(self.contribution_amount)})"



    @property

    def ownership_percent(self) -> Decimal | None:

        return self.parlay.ownership_percent_for(self.contribution_amount)



    @property

    def estimated_payout(self) -> Decimal | None:

        return self.parlay.estimated_payout_for(self.contribution_amount)





class OCRUploadStatus(models.TextChoices):

    PENDING = "pending", "Pending"

    PROCESSING = "processing", "Processing"

    COMPLETED = "completed", "Completed"

    FAILED = "failed", "Failed"





class OCRUpload(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    parlay = models.ForeignKey(

        Parlay,

        on_delete=models.CASCADE,

        related_name="ocr_uploads",

        null=True,

        blank=True,

    )

    image = models.ImageField(upload_to="ocr/%Y/%m/%d/")

    status = models.CharField(

        max_length=16,

        choices=OCRUploadStatus.choices,

        default=OCRUploadStatus.PENDING,

    )

    raw_text = models.TextField(blank=True)

    parsed_data = models.JSONField(default=dict, blank=True)

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    processed_at = models.DateTimeField(null=True, blank=True)



    class Meta:

        ordering = ["-created_at"]



    def __str__(self):

        return f"OCR {self.id} ({self.status})"



    def mark_processing(self):

        self.status = OCRUploadStatus.PROCESSING

        self.save(update_fields=["status"])



    def mark_completed(self, raw_text: str, parsed_data: dict):

        self.status = OCRUploadStatus.COMPLETED

        self.raw_text = raw_text

        self.parsed_data = parsed_data

        self.processed_at = timezone.now()

        self.save(

            update_fields=["status", "raw_text", "parsed_data", "processed_at"],

        )



    def mark_failed(self, message: str):

        self.status = OCRUploadStatus.FAILED

        self.error_message = message

        self.processed_at = timezone.now()

        self.save(update_fields=["status", "error_message", "processed_at"])


class OCRScanFeedback(models.Model):
    """
    Compact OCR correction log (predicted vs submitted). Only material changes stored.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ocr_upload = models.OneToOneField(
        OCRUpload,
        on_delete=models.CASCADE,
        related_name="scan_feedback",
    )
    parlay = models.ForeignKey(
        Parlay,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocr_scan_feedback",
    )
    parser_sportsbook = models.CharField(max_length=32, blank=True)
    predicted_leg_count = models.PositiveSmallIntegerField(default=0)
    submitted_leg_count = models.PositiveSmallIntegerField(default=0)
    corrections = models.JSONField(
        default=dict,
        blank=True,
        help_text='Compact deltas only, e.g. {"f": {"odds_american": ["335","750"]}, "legs": [...]}.',
    )
    was_edited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "OCR scan feedback"
        verbose_name_plural = "OCR scan feedback"

    def __str__(self):
        flag = "edited" if self.was_edited else "ok"
        return f"OCR feedback {self.ocr_upload_id} ({flag})"


