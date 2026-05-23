"""Render a sample OG preview PNG using the production image service."""
import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from parlays.models import Parlay
from parlays.services.og_image import build_parlay_og_snapshot, render_parlay_og_png_from_snapshot

# Sample snapshot when no DB parlay exists
SAMPLE = None

try:
    parlay = (
        Parlay.objects.prefetch_related("legs", "participants")
        .filter(is_public=True)
        .first()
    )
    if parlay:
        SAMPLE = build_parlay_og_snapshot(parlay)
except Exception:
    pass

if SAMPLE is None:
    from parlays.services.og_image import ParlayOGSnapshot

    SAMPLE = ParlayOGSnapshot(
        title="Jordan Parlay - 3 Legs (+1850)",
        legs="3",
        odds="+1850",
        payout="$1,950.00",
        participants="4",
        segments=(),
    )

out = Path(__file__).resolve().parent.parent / "static/img/og-parlay-preview-sample.png"
out.write_bytes(render_parlay_og_png_from_snapshot(SAMPLE))
print(out)
