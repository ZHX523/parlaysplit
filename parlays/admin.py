from django.contrib import admin

from .models import OCRUpload, Parlay, ParlayLeg, Participant


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
    readonly_fields = ("id", "slug", "host_code", "created_at", "updated_at")
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


@admin.register(OCRUpload)
class OCRUploadAdmin(admin.ModelAdmin):
    list_display = ("id", "parlay", "status", "created_at", "processed_at")
    list_filter = ("status",)
    readonly_fields = ("raw_text", "parsed_data", "created_at", "processed_at")

