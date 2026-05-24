"""
Lightweight OCR correction logging: store only what the user changed vs scan prefill.

Runs after the HTTP response (on_commit). Skips unchanged scans by default.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

_MAX_LEG = getattr(settings, "OCR_FEEDBACK_MAX_LEG_CHARS", 200)


def _enabled() -> bool:
    return getattr(settings, "OCR_FEEDBACK_ENABLED", True)


def _store_unchanged() -> bool:
    return getattr(settings, "OCR_FEEDBACK_STORE_UNCHANGED", False)


def _clip(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= _MAX_LEG:
        return text
    return text[: _MAX_LEG - 1] + "…"


def _norm_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm_money(value: Any) -> str:
    text = _norm_str(value)
    if not text:
        return ""
    try:
        return f"{Decimal(str(text).replace(',', '')):.2f}"
    except (InvalidOperation, ValueError):
        return text


def _norm_odds(value: Any) -> str:
    text = _norm_str(value)
    if not text:
        return ""
    try:
        return str(int(text))
    except (TypeError, ValueError):
        digits = "".join(c for c in text if c.isdigit() or c in "+-")
        return digits or text


def _predicted_from_parsed(parsed: dict) -> dict:
    from parlays.forms import legs_initial_from_ocr

    legs_initial = legs_initial_from_ocr(parsed or {})
    return {
        "odds_american": _norm_odds(parsed.get("odds_american")),
        "wager_amount": _norm_money(parsed.get("wager_amount")),
        "legs": [
            {
                "t": _norm_str(leg.get("leg_type")),
                "d": _clip(_norm_str(leg.get("description"))),
            }
            for leg in legs_initial
            if _norm_str(leg.get("description"))
        ],
    }


def _submitted_from_post(post_data: dict) -> dict:
    types = post_data.get("leg_type") or []
    descs = post_data.get("leg_description") or []
    legs = []
    for leg_type, description in zip(types, descs):
        description = _clip(_norm_str(description))
        if not description:
            continue
        legs.append({"t": _norm_str(leg_type), "d": description})
    return {
        "odds_american": _norm_odds(post_data.get("odds_american")),
        "wager_amount": _norm_money(post_data.get("wager_amount")),
        "legs": legs,
    }


def build_compact_corrections(predicted: dict, submitted: dict) -> tuple[dict, bool]:
    """
    Return (corrections, was_edited). Empty corrections when nothing changed.
    """
    corrections: dict[str, Any] = {"f": {}, "legs": []}
    was_edited = False

    for key in ("odds_american", "wager_amount"):
        pred_val = _norm_str(predicted.get(key))
        sub_val = _norm_str(submitted.get(key))
        if pred_val != sub_val and (pred_val or sub_val):
            corrections["f"][key] = [pred_val, sub_val]
            was_edited = True

    pred_legs = predicted.get("legs") or []
    sub_legs = submitted.get("legs") or []
    if len(pred_legs) != len(sub_legs):
        corrections["f"]["leg_count"] = [len(pred_legs), len(sub_legs)]
        was_edited = True

    max_len = max(len(pred_legs), len(sub_legs))
    for i in range(max_len):
        pred_leg = pred_legs[i] if i < len(pred_legs) else {}
        sub_leg = sub_legs[i] if i < len(sub_legs) else {}
        if pred_leg.get("t") == sub_leg.get("t") and pred_leg.get("d") == sub_leg.get("d"):
            continue
        if not pred_leg.get("d") and not sub_leg.get("d"):
            continue
        corrections["legs"].append(
            {
                "i": i,
                "p": pred_leg.get("d", ""),
                "s": sub_leg.get("d", ""),
            }
        )
        was_edited = True

    if not corrections["f"]:
        del corrections["f"]
    if not corrections["legs"]:
        del corrections["legs"]
    if not was_edited:
        return {}, False
    return corrections, True


def _minimal_post(post) -> dict:
    return {
        "odds_american": post.get("odds_american"),
        "wager_amount": post.get("wager_amount"),
        "leg_type": post.getlist("leg_type"),
        "leg_description": post.getlist("leg_description"),
    }


def record_ocr_scan_feedback(ocr_upload_id: str, parlay_id: str, post_data: dict) -> None:
    """Persist compact correction row. Never raises."""
    if not _enabled():
        return

    from parlays.models import OCRScanFeedback, OCRUpload

    try:
        upload = OCRUpload.objects.only(
            "id", "parsed_data", "parlay_id"
        ).get(pk=ocr_upload_id)
        parsed = upload.parsed_data or {}
        predicted = _predicted_from_parsed(parsed)
        submitted = _submitted_from_post(post_data)
        corrections, was_edited = build_compact_corrections(predicted, submitted)

        if not was_edited and not _store_unchanged():
            return

        OCRScanFeedback.objects.update_or_create(
            ocr_upload_id=ocr_upload_id,
            defaults={
                "parlay_id": parlay_id,
                "parser_sportsbook": _norm_str(parsed.get("sportsbook"))[:32],
                "was_edited": was_edited,
                "predicted_leg_count": len(predicted.get("legs") or []),
                "submitted_leg_count": len(submitted.get("legs") or []),
                "corrections": corrections,
            },
        )
    except Exception:
        logger.exception("OCR feedback save failed upload=%s", ocr_upload_id)


def schedule_ocr_scan_feedback(ocr_upload_id: str, parlay_id: str, post) -> None:
    """Queue feedback write after the request finishes (non-blocking for the user)."""
    if not _enabled():
        return
    payload = _minimal_post(post)
    transaction.on_commit(
        lambda: record_ocr_scan_feedback(ocr_upload_id, parlay_id, payload)
    )
