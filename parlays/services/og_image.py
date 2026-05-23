"""
Server-side Open Graph preview images for public parlays.

Renders 1200x630 PNGs with Pillow, caches by content version, and falls back
to a static image when generation fails.
"""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from PIL import Image, ImageDraw, ImageFont

from parlays.models import Parlay
from parlays.opengraph import (
    format_odds_display,
    parlay_opengraph_title,
    parlay_ownership_segments,
)
from parlays.utils import format_dollars

logger = logging.getLogger(__name__)

OG_WIDTH = 1200
OG_HEIGHT = 630
OG_IMAGE_VERSION = 3

COLOR_BG = (15, 23, 42)
COLOR_EMERALD = (52, 211, 153)
COLOR_WHITE = (241, 245, 249)
COLOR_MUTED = (148, 163, 184)
COLOR_PANEL = (30, 41, 59)
COLOR_BORDER = (51, 65, 85)
COLOR_BAR_BG = (30, 41, 59)
COLOR_BAR_BORDER = (51, 65, 85)
COLOR_ACCENT_LINE = (16, 185, 129)

MARGIN_X = 72
BRAND_Y = 56
TITLE_Y = 108
METRICS_Y = 200
METRICS_BOX_W = 252
METRICS_BOX_H = 168
METRICS_BOX_GAP = 24
METRICS_TO_SPLIT_GAP = 24
SPLIT_LABEL_TO_BAR_GAP = 10
BAR_W = 1056
BAR_H = 32
LEGEND_BELOW_BAR_GAP = 18
MAX_LEGEND_ITEMS = 5
MAX_TITLE_DISPLAY_LEN = 52
MAX_METRIC_VALUE_LEN = 14

FALLBACK_STATIC = "img/og-parlay-fallback.png"
CACHE_KEY_PREFIX = "parlay_og"


@dataclass(frozen=True)
class ParlayOGSnapshot:
    title: str
    legs: str
    odds: str
    payout: str
    participants: str
    segments: tuple[dict, ...]


def _og_layout() -> dict[str, int]:
    metrics_bottom = METRICS_Y + METRICS_BOX_H
    split_label_y = metrics_bottom + METRICS_TO_SPLIT_GAP
    bar_y = split_label_y + 26 + SPLIT_LABEL_TO_BAR_GAP
    legend_y = bar_y + BAR_H + LEGEND_BELOW_BAR_GAP
    return {
        "metrics_y": METRICS_Y,
        "split_label_y": split_label_y,
        "bar_x": MARGIN_X,
        "bar_y": bar_y,
        "legend_y": legend_y,
    }


def build_parlay_og_snapshot(parlay: Parlay) -> ParlayOGSnapshot:
    title = parlay_opengraph_title(parlay)
    if len(title) > MAX_TITLE_DISPLAY_LEN:
        title = title[: MAX_TITLE_DISPLAY_LEN - 1].rstrip() + "…"

    payout = (
        format_dollars(parlay.potential_payout)
        if parlay.potential_payout
        else "TBD"
    )
    participants = str(1 + parlay.participant_count)

    leg_count = parlay.legs.count()

    return ParlayOGSnapshot(
        title=title,
        legs=str(leg_count),
        odds=format_odds_display(parlay.odds_american),
        payout=payout,
        participants=participants,
        segments=tuple(parlay_ownership_segments(parlay)),
    )


def compute_og_cache_version(parlay: Parlay) -> str:
    """Content hash so cache invalidates when parlay data changes."""
    digest = hashlib.sha256()
    digest.update(f"v{OG_IMAGE_VERSION}".encode())
    digest.update(
        f"{parlay.pk}|{parlay.updated_at}|{parlay.odds_american}|"
        f"{parlay.potential_payout}|{parlay.external_link}|{parlay.creator_nickname}".encode(),
    )
    for leg in parlay.legs.all().order_by("sort_order", "pk"):
        digest.update(f"|leg:{leg.description}:{leg.leg_type}:{leg.sort_order}".encode())
    for participant in parlay.participants.all().order_by("joined_at", "pk"):
        digest.update(
            f"|p:{participant.nickname}:{participant.status}:"
            f"{participant.contribution_amount}".encode(),
        )
    return digest.hexdigest()[:24]


def og_cache_key(parlay: Parlay) -> str:
    return f"{CACHE_KEY_PREFIX}:{parlay.pk}:{compute_og_cache_version(parlay)}"


def invalidate_parlay_og_cache(parlay_id) -> None:
    """Best-effort cache bust when parlay-related rows change."""
    cache.delete(f"{CACHE_KEY_PREFIX}:invalidate:{parlay_id}")


def _fallback_png_bytes() -> bytes:
    for base in (Path(settings.BASE_DIR) / "static", Path(settings.STATIC_ROOT or "")):
        path = base / FALLBACK_STATIC
        if path.is_file():
            return path.read_bytes()
    logger.warning("OG fallback image missing at %s", FALLBACK_STATIC)
    return _render_minimal_fallback()


def _render_minimal_fallback() -> bytes:
    image = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), COLOR_BG)
    draw = ImageDraw.Draw(image)
    font = _load_font(48, bold=True)
    draw.text((MARGIN_X, OG_HEIGHT // 2 - 24), "ParlaySplit", fill=COLOR_EMERALD, font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold
        else ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _draw_accent_bar(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((0, 0, OG_WIDTH, 4), fill=COLOR_ACCENT_LINE)


def _draw_pill_bar(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    segments: tuple[dict, ...],
) -> None:
    radius = height // 2
    draw.rounded_rectangle((x, y, x + width, y + height), radius=radius, fill=COLOR_BAR_BG)

    if segments:
        seg_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        seg_draw = ImageDraw.Draw(seg_layer)
        cursor = 0
        for index, segment in enumerate(segments):
            pct = float(segment["percent"])
            if index == len(segments) - 1:
                seg_w = width - cursor
            else:
                seg_w = max(1, int(width * pct / 100))
            if seg_w < 1:
                continue
            color = _hex_to_rgb(segment["color"]) + (255,)
            seg_draw.rectangle((cursor, 0, cursor + seg_w, height), fill=color)
            cursor += seg_w

        mask = Image.new("L", (width, height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, width, height), radius=radius, fill=255)
        image.paste(seg_layer, (x, y), mask)

    draw.rounded_rectangle(
        (x, y, x + width, y + height),
        radius=radius,
        outline=COLOR_BAR_BORDER,
        width=1,
    )


def _draw_metric_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    label: str,
    value: str,
    *,
    font_label: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    font_value: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    draw.rounded_rectangle(
        (x, y, x + METRICS_BOX_W, y + METRICS_BOX_H),
        radius=20,
        fill=COLOR_PANEL,
        outline=COLOR_BORDER,
        width=2,
    )
    draw.text((x + 24, y + 28), label.upper(), fill=COLOR_MUTED, font=font_label)
    if len(value) > MAX_METRIC_VALUE_LEN:
        value = value[: MAX_METRIC_VALUE_LEN - 3] + "..."
    value_w = _text_width(draw, value, font_value)
    draw.text(
        (x + (METRICS_BOX_W - value_w) // 2, y + 72),
        value,
        fill=COLOR_EMERALD,
        font=font_value,
    )


def _draw_ownership_section(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    layout: dict[str, int],
    segments: tuple[dict, ...],
    *,
    font_label: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    font_legend: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    bar_x = layout["bar_x"]
    draw.text(
        (bar_x, layout["split_label_y"]),
        "OWNERSHIP SPLIT",
        fill=COLOR_MUTED,
        font=font_label,
    )
    _draw_pill_bar(image, draw, bar_x, layout["bar_y"], BAR_W, BAR_H, segments)

    shown = list(segments[:MAX_LEGEND_ITEMS])
    extra = len(segments) - len(shown)
    slot_w = BAR_W // max(len(shown), 1)
    legend_x = bar_x
    legend_y = layout["legend_y"]

    for segment in shown:
        swatch = 12
        draw.rounded_rectangle(
            (legend_x, legend_y, legend_x + swatch, legend_y + swatch),
            radius=3,
            fill=_hex_to_rgb(segment["color"]),
        )
        pct = float(segment["percent"])
        pct_text = f"{int(pct)}%" if pct == int(pct) else f"{pct:.1f}%"
        name = str(segment["nickname"])
        if len(name) > 14:
            name = name[:12] + "…"
        draw.text(
            (legend_x + 18, legend_y - 2),
            f"{name} {pct_text}",
            fill=COLOR_WHITE,
            font=font_legend,
        )
        legend_x += slot_w

    if extra > 0:
        draw.text(
            (legend_x + 8, legend_y - 2),
            f"+{extra} more",
            fill=COLOR_MUTED,
            font=font_legend,
        )


def render_parlay_og_png_from_snapshot(snapshot: ParlayOGSnapshot) -> bytes:
    image = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), COLOR_BG)
    draw = ImageDraw.Draw(image)
    _draw_accent_bar(draw)

    font_brand = _load_font(28)
    font_title = _load_font(48, bold=True)
    font_label = _load_font(22)
    font_value = _load_font(40, bold=True)
    font_legend = _load_font(18)

    layout = _og_layout()

    draw.text((MARGIN_X, BRAND_Y), "ParlaySplit", fill=COLOR_MUTED, font=font_brand)

    draw.text((MARGIN_X, TITLE_Y), snapshot.title, fill=COLOR_WHITE, font=font_title)

    metrics = [
        ("Legs", snapshot.legs),
        ("Odds", snapshot.odds),
        ("Est. Payout", snapshot.payout),
        ("Participants", snapshot.participants),
    ]
    for index, (label, value) in enumerate(metrics):
        x = MARGIN_X + index * (METRICS_BOX_W + METRICS_BOX_GAP)
        _draw_metric_card(
            draw,
            x,
            layout["metrics_y"],
            label,
            value,
            font_label=font_label,
            font_value=font_value,
        )

    _draw_ownership_section(
        image,
        draw,
        layout,
        snapshot.segments,
        font_label=font_label,
        font_legend=font_legend,
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_parlay_og_png(parlay: Parlay) -> bytes:
    """Render PNG bytes (uncached)."""
    return render_parlay_og_png_from_snapshot(build_parlay_og_snapshot(parlay))


def get_parlay_og_image_bytes(parlay: Parlay) -> bytes:
    """Cached PNG for CDN and social crawlers."""
    cache_key = og_cache_key(parlay)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        png_bytes = render_parlay_og_png(parlay)
    except Exception:
        logger.exception("Failed to render OG image for parlay %s", parlay.pk)
        png_bytes = _fallback_png_bytes()

    timeout = getattr(settings, "OG_IMAGE_CACHE_TIMEOUT", 86400)
    cache.set(cache_key, png_bytes, timeout=timeout)
    return png_bytes


def get_parlay_og_etag(parlay: Parlay) -> str:
    return f'"{compute_og_cache_version(parlay)}"'
