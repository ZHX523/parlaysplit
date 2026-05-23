"""
OCR pipeline optimized for FanDuel and DraftKings bet slip screenshots.
"""
import logging
import re
from decimal import Decimal, InvalidOperation
from io import BytesIO

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

from parlays.models import LegType, Parlay, ParlayLeg, Sportsbook
from parlays.services.odds import american_odds_to_payout

logger = logging.getLogger(__name__)

# American odds: +450, -110, etc.
ODDS_PATTERN = re.compile(r"(?<!\d)([+-]\d{3,5})(?!\d)")
# Money: $25.00, 25.00, $1,234.56
MONEY_PATTERN = re.compile(
    r"\$?\s*([\d,]+\.\d{2}|\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
)
PAYOUT_KEYWORDS = re.compile(
    r"(payout|to win|potential win|total payout|winnings)",
    re.IGNORECASE,
)
WAGER_KEYWORDS = re.compile(
    r"(wager|bet amount|total wager|stake|risk)",
    re.IGNORECASE,
)
SPORTSBOOK_HINTS = {
    Sportsbook.FANDUEL: re.compile(r"fanduel", re.IGNORECASE),
    Sportsbook.DRAFTKINGS: re.compile(r"draftkings|draft kings", re.IGNORECASE),
    Sportsbook.KALSHI: re.compile(r"kalshi", re.IGNORECASE),
    Sportsbook.BETMGM: re.compile(r"betmgm|mgm", re.IGNORECASE),
    Sportsbook.CAESARS: re.compile(r"caesars", re.IGNORECASE),
}


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """Grayscale, sharpen, threshold for OCR."""
    pil = Image.open(BytesIO(image_bytes))
    pil = pil.convert("RGB")
    pil = pil.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(pil)
    pil = enhancer.enhance(1.5)

    arr = np.array(pil)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(thresh, -1, kernel)
    return sharpened


def extract_text(image_bytes: bytes) -> str:
    processed = preprocess_image(image_bytes)
    pil = Image.fromarray(processed)
    config = "--psm 6 -c preserve_interword_spaces=1"
    text = pytesseract.image_to_string(pil, config=config)
    return text.strip()


def _parse_money(value: str) -> Decimal | None:
    try:
        cleaned = value.replace(",", "").strip()
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError):
        return None


def _find_money_near_keyword(lines: list[str], keyword_re: re.Pattern) -> Decimal | None:
    for i, line in enumerate(lines):
        if keyword_re.search(line):
            for check in [line] + lines[i + 1 : i + 3]:
                for match in MONEY_PATTERN.finditer(check):
                    amount = _parse_money(match.group(1))
                    if amount and amount > 0:
                        return amount
    return None


def _extract_all_money(text: str) -> list[Decimal]:
    amounts = []
    for match in MONEY_PATTERN.finditer(text):
        amount = _parse_money(match.group(1))
        if amount and amount >= Decimal("0.01"):
            amounts.append(amount)
    return amounts


def _detect_sportsbook(text: str) -> str:
    for book, pattern in SPORTSBOOK_HINTS.items():
        if pattern.search(text):
            return book
    return Sportsbook.OTHER


def _extract_odds(text: str) -> int | None:
    matches = ODDS_PATTERN.findall(text)
    for m in matches:
        try:
            val = int(m)
            if abs(val) >= 100:
                return val
        except ValueError:
            continue
    return None


def _extract_legs(lines: list[str], text: str) -> list[str]:
    """Heuristic leg extraction from OCR lines."""
    skip_patterns = [
        re.compile(r"^(bet slip|parlay|same game|receipt|total)", re.I),
        re.compile(r"^(wager|payout|odds|draftkings|fanduel)", re.I),
        re.compile(r"^\$"),
        re.compile(r"^[+-]\d+$"),
        re.compile(r"^\d+\.\d{2}$"),
    ]
    legs = []
    for line in lines:
        line = line.strip()
        if len(line) < 4 or len(line) > 200:
            continue
        if any(p.search(line) for p in skip_patterns):
            continue
        if line.count(" ") < 1 and not re.search(r"[A-Za-z]{3,}", line):
            continue
        legs.append(line)

    if len(legs) < 2:
        # FanDuel/DK often use bullet or numbered legs
        leg_blocks = re.findall(
            r"(?:\d+\)|•|-)\s*([A-Za-z][^\n]{8,120})",
            text,
        )
        legs.extend(leg_blocks)

    seen = set()
    unique = []
    for leg in legs:
        key = leg.lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(leg)
    return unique[:20]


def parse_ocr_text(text: str) -> dict:
    """Parse raw OCR text into structured parlay fields."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    joined = "\n".join(lines)

    sportsbook = _detect_sportsbook(joined)
    odds_american = _extract_odds(joined)

    wager = _find_money_near_keyword(lines, WAGER_KEYWORDS)
    payout = _find_money_near_keyword(lines, PAYOUT_KEYWORDS)

    all_money = _extract_all_money(joined)
    if wager is None and all_money:
        wager = min(all_money)
    if payout is None and all_money and len(all_money) >= 2:
        payout = max(all_money)

    legs = _extract_legs(lines, joined)

    return {
        "sportsbook": sportsbook,
        "odds_american": odds_american,
        "wager_amount": str(wager) if wager else "",
        "potential_payout": str(payout) if payout else "",
        "leg_descriptions": "\n".join(legs),
        "raw_line_count": len(lines),
    }


class OCRService:
    @staticmethod
    def process_upload(ocr_upload) -> dict:
        ocr_upload.mark_processing()
        try:
            with ocr_upload.image.open("rb") as f:
                image_bytes = f.read()
            raw_text = extract_text(image_bytes)
            if not raw_text:
                ocr_upload.mark_failed("No text detected in image.")
                return {}
            parsed = parse_ocr_text(raw_text)
            ocr_upload.mark_completed(raw_text, parsed)
            return parsed
        except Exception as exc:
            logger.exception("OCR failed for upload %s", ocr_upload.id)
            ocr_upload.mark_failed(str(exc))
            return {}


def apply_parsed_to_parlay(parlay: Parlay, parsed: dict, creator_nickname: str = ""):
    if creator_nickname:
        parlay.creator_nickname = creator_nickname
    if parsed.get("sportsbook"):
        parlay.sportsbook = parsed["sportsbook"]
    if parsed.get("odds_american"):
        parlay.odds_american = parsed["odds_american"]
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

    leg_text = parsed.get("leg_descriptions", "")
    if leg_text:
        parlay.legs.all().delete()
        for i, line in enumerate(leg_text.splitlines()):
            line = line.strip()
            if line:
                ParlayLeg.objects.create(
                    parlay=parlay,
                    leg_type=LegType.OTHER,
                    description=line[:500],
                    sort_order=i,
                )
