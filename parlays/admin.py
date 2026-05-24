import json

from django.contrib import admin
from django.utils.html import format_html

from .models import OCRScanFeedback, OCRUpload, Parlay, ParlayLeg, Participant


class ParlayLegInline(admin.TabularInline):
    model = ParlayLeg
    fields = ("leg_type", "description", "sort_order")
    extra = 0


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    readonly_fields = ("joined_at",)
    fields = ("nickname", "contribution_amount", "status", "joined_at")


@admin.register(Parlay)
class ParlayAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "creator_nickname",
        "wager_amount",
        "split_offered_percent",
        "potential_payout",
        "status",
        "created_at",
    )
    list_filter = ("status", "is_public")
    search_fields = ("slug", "creator_nickname", "host_code", "id")
    readonly_fields = (
        "id",
        "slug",
        "host_code",
        "host_code_expires_at",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "creator_nickname",
                    "status",
                    "odds_american",
                    "wager_amount",
                    "split_offered_percent",
                    "potential_payout",
                    "is_public",
                ),
            },
        ),
        (
            "Identifiers",
            {"fields": ("id", "slug", "host_code", "external_link", "notes")},
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    inlines = [ParlayLegInline, ParticipantInline]


class OCRScanFeedbackInline(admin.StackedInline):
    model = OCRScanFeedback
    extra = 0
    max_num = 1
    can_delete = False
    readonly_fields = (
        "parlay",
        "parser_sportsbook",
        "was_edited",
        "predicted_leg_count",
        "submitted_leg_count",
        "corrections",
        "created_at",
        "corrections_summary",
    )
    fields = readonly_fields

    @admin.display(description="Summary")
    def corrections_summary(self, obj):
        if not obj or not obj.corrections:
            return "No corrections (scan matched submission)"
        parts = []
        for key, pair in (obj.corrections.get("f") or {}).items():
            if isinstance(pair, list) and len(pair) == 2:
                parts.append(f"{key}: {pair[0]} → {pair[1]}")
        for leg in obj.corrections.get("legs") or []:
            parts.append(f"leg {leg.get('i', '?')}: {leg.get('p', '')} → {leg.get('s', '')}")
        return format_html("<br>".join(parts[:12])) if parts else "—"


@admin.register(OCRUpload)
class OCRUploadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "parlay",
        "status",
        "feedback_edited",
        "created_at",
        "processed_at",
    )
    list_filter = ("status", "scan_feedback__was_edited")
    readonly_fields = ("raw_text", "parsed_data", "created_at", "processed_at")
    inlines = [OCRScanFeedbackInline]

    @admin.display(boolean=True, description="User edited OCR")
    def feedback_edited(self, obj):
        fb = getattr(obj, "scan_feedback", None)
        return bool(fb and fb.was_edited)


@admin.register(OCRScanFeedback)
class OCRScanFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "parser_sportsbook",
        "was_edited",
        "predicted_leg_count",
        "submitted_leg_count",
        "ocr_upload",
    )
    list_filter = ("was_edited", "parser_sportsbook")
    search_fields = ("ocr_upload__id", "parlay__slug")
    readonly_fields = (
        "ocr_upload",
        "parlay",
        "parser_sportsbook",
        "was_edited",
        "predicted_leg_count",
        "submitted_leg_count",
        "corrections",
        "created_at",
    )
