"""Django OCR upload integration and legacy helpers."""

import logging
from decimal import Decimal, InvalidOperation

from parlays.models import LegType, Parlay, ParlayLeg
from parlays.services.odds import american_odds_to_payout

from .pipeline import process_image_bytes

logger = logging.getLogger(__name__)


def extract_text(image_bytes: bytes) -> str:
    """Backward-compatible raw text extraction."""
    result = process_image_bytes(image_bytes)
    return result.get("raw_text", "")


def parse_ocr_text(text: str) -> dict:
    """Parse already-extracted text (fallback / tests)."""
    from parlays.services.parsers.registry import parse_slip

    from .extract import OCRLine

    lines = [
        OCRLine(text=ln.strip(), words=(), top=i * 20, left=0, conf=0.6)
        for i, ln in enumerate(text.splitlines())
        if ln.strip()
    ]
    from .normalize import sanitize_parsed_result

    return sanitize_parsed_result(parse_slip(lines, text).to_legacy_dict())


class OCRService:
    @staticmethod
    def process_upload(ocr_upload) -> dict:
        ocr_upload.mark_processing()
        try:
            with ocr_upload.image.open("rb") as f:
                image_bytes = f.read()
            parsed = process_image_bytes(image_bytes)
            if parsed.get("error"):
                ocr_upload.mark_failed(parsed["error"])
                return parsed
            raw_text = parsed.get("raw_text", "")
            if not raw_text and not parsed.get("legs"):
                ocr_upload.mark_failed("No text detected in image.")
                return {}
            ocr_upload.mark_completed(raw_text, parsed)
            return parsed
        except Exception as exc:
            logger.exception("OCR failed for upload %s", ocr_upload.id)
            ocr_upload.mark_failed(str(exc))
            return {}


def apply_parsed_to_parlay(parlay: Parlay, parsed: dict, creator_nickname: str = ""):
    if creator_nickname:
        parlay.creator_nickname = creator_nickname
    odds = parsed.get("odds_american")
    if odds:
        parlay.odds_american = int(odds)
    if parsed.get("wager_amount"):
        try:
            parlay.wager_amount = Decimal(str(parsed["wager_amount"]))
        except InvalidOperation:
            pass
    if parlay.odds_american and parlay.wager_amount:
        payout = american_odds_to_payout(parlay.wager_amount, parlay.odds_american)
        if payout:
            parlay.potential_payout = payout
    elif parsed.get("potential_payout"):
        try:
            parlay.potential_payout = Decimal(str(parsed["potential_payout"]))
        except InvalidOperation:
            pass
    parlay.save()

    structured = parsed.get("legs") or []
    if structured:
        parlay.legs.all().delete()
        valid = {c[0] for c in LegType.choices}
        for i, leg in enumerate(structured):
            desc = leg.get("description") or leg.get("event") or ""
            if not desc:
                continue
            leg_type = leg.get("leg_type") or LegType.MONEYLINE
            if leg_type not in valid:
                leg_type = LegType.MONEYLINE
            ParlayLeg.objects.create(
                parlay=parlay,
                leg_type=leg_type,
                description=desc[:500],
                sort_order=i,
            )
        return

    leg_text = parsed.get("leg_descriptions", "")
    if leg_text:
        parlay.legs.all().delete()
        for i, line in enumerate(leg_text.splitlines()):
            line = line.strip()
            if line:
                ParlayLeg.objects.create(
                    parlay=parlay,
                    leg_type=LegType.MONEYLINE,
                    description=line[:500],
                    sort_order=i,
                )
