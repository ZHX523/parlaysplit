"""Open Graph copy and ownership data for parlay pages."""

from __future__ import annotations

from django.urls import reverse

from parlays.models import Parlay, ParticipantStatus
from parlays.seo import absolute_url, parlay_public_url
from parlays.utils import build_ownership_bar, format_dollars, ownership_color

MAX_OG_TITLE_LEN = 120


def format_odds_display(odds_american: int | None) -> str:
    if odds_american is None:
        return "—"
    if odds_american > 0:
        return f"+{odds_american}"
    return str(odds_american)


def parlay_ownership_segments(parlay: Parlay) -> list[dict]:
    approved = list(
        parlay.participants.filter(status=ParticipantStatus.APPROVED).order_by(
            "joined_at",
        ),
    )
    rows = [
        {
            "is_host": True,
            "nickname": parlay.creator_nickname,
            "ownership": parlay.host_ownership_percent(),
            "color": ownership_color(is_host=True),
        },
    ]
    for friend_index, participant in enumerate(approved):
        rows.append(
            {
                "is_host": False,
                "nickname": participant.nickname,
                "ownership": parlay.ownership_percent_for(
                    participant.contribution_amount,
                ),
                "color": ownership_color(is_host=False, friend_index=friend_index),
            },
        )
    return build_ownership_bar(rows)


def format_leg_count_label(count: int) -> str:
    if count == 1:
        return "1 Leg"
    return f"{count} Legs"


def parlay_opengraph_title(parlay: Parlay) -> str:
    """e.g. Jordan Parlay - 3 Legs (+1850)"""
    name = (parlay.creator_nickname or "HOST").strip()
    leg_count = parlay.legs.count()
    legs_part = format_leg_count_label(leg_count)
    odds = format_odds_display(parlay.odds_american)
    if odds != "—":
        title = f"{name} Parlay - {legs_part} ({odds})"
    else:
        title = f"{name} Parlay - {legs_part}"
    if len(title) > MAX_OG_TITLE_LEN:
        return title[: MAX_OG_TITLE_LEN - 1].rstrip() + "…"
    return title


def parlay_opengraph_description(parlay: Parlay) -> str:
    """e.g. 4 participants • Estimated payout $1,950"""
    participants = 1 + parlay.participant_count
    word = "participant" if participants == 1 else "participants"
    if parlay.potential_payout:
        payout = format_dollars(parlay.potential_payout)
        return f"{participants} {word} • Estimated payout {payout}"
    return f"{participants} {word} • Estimated payout TBD"


def parlay_opengraph_page_url(request, parlay: Parlay) -> str:
    return parlay_public_url(request, parlay)


def parlay_opengraph_image_url(request, parlay: Parlay) -> str:
    path = reverse("parlays:og_image", kwargs={"slug": parlay.slug})
    return absolute_url(request, path)


def render_parlay_og_png(parlay: Parlay) -> bytes:
    from parlays.services.og_image import get_parlay_og_image_bytes

    return get_parlay_og_image_bytes(parlay)


def render_parlay_og_svg(parlay: Parlay) -> str:
    from parlays.services.og_image import build_parlay_og_snapshot

    snapshot = build_parlay_og_snapshot(parlay)
    from xml.sax.saxutils import escape

    title = escape(snapshot.title)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#0f172a"/>
  <text x="72" y="72" fill="#94a3b8" font-family="system-ui,sans-serif" font-size="28">ParlaySplit</text>
  <text x="72" y="148" fill="#f1f5f9" font-family="system-ui,sans-serif" font-size="48" font-weight="700">{title}</text>
  <text x="72" y="220" fill="#34d399" font-family="system-ui,sans-serif" font-size="32">{escape(snapshot.legs)} legs · {escape(snapshot.odds)} · {escape(snapshot.payout)} · {escape(snapshot.participants)} participants</text>
</svg>"""
