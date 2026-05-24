"""Shared helpers for sportsbook slip parsers."""

from __future__ import annotations

import re

from parlays.services.ocr.extract import OCRLine
from parlays.services.ocr.normalize import clean_text, normalize_time
from parlays.services.ocr.segmentation import AMERICAN_ODDS_RE, EVENT_RE

MONEY_RE = re.compile(r"\$?\s*([\d,]+\.\d{2})")

from .base import ParsedLeg

TIME_RE = re.compile(
    r"(\d{1,2}:?\d{0,2}\s*[AP]M(?:\s*ET)?|Sun|Mon|Tue|Wed|Thu|Fri|Sat)",
    re.I,
)
WAGER_RE = re.compile(r"(wager|risk|bet amount|total wager|place\s*bet)", re.I)
PAYOUT_RE = re.compile(r"(payout|to win|potential|total\s*payout|to\s*pay)", re.I)
PLACE_BET_RE = re.compile(r"place\s*bet\s*\$?\s*([\d,]+\.?\d*)", re.I)
PICK_PARLAY_RE = re.compile(r"(\d+)\s*pick\s+parlay", re.I)
LEG_PARLAY_RE = re.compile(r"(\d+)\s*leg\s+parlay", re.I)
SGP_RE = re.compile(r"same\s*game\s*parlay", re.I)


def map_leg_type(bet_type: str, selection: str) -> str:
    bt = bet_type.upper()
    sel = selection.lower()
    if "MONEYLINE" in bt:
        return "moneyline"
    if "SPREAD" in bt or "RUN LINE" in bt or "PUCK LINE" in bt:
        return "spread"
    if any(
        k in bt
        for k in (
            "PASSING",
            "RUSHING",
            "RECEIVING",
            "TOUCHDOWN",
            "REBOUND",
            "ASSIST",
            "POINTS",
            "YARDS",
            "PLAYER",
        )
    ):
        return "player_prop"
    if "OVER/UNDER" in bt or "TOTAL" in bt or sel in ("over", "under"):
        return "total_points"
    return "moneyline"


def build_description(leg: ParsedLeg) -> str:
    parts: list[str] = []
    if leg.selection:
        parts.append(leg.selection)
    if leg.bet_type:
        bt = leg.bet_type
        if leg.line:
            bt = f"{leg.line} {bt}".strip()
        parts.append(bt)
    elif leg.line:
        parts.append(leg.line)
    if leg.event:
        parts.append(leg.event)
    if leg.game_time:
        parts.append(leg.game_time)
    return " · ".join(parts)[:500]


def extract_shared_event(lines: list[OCRLine]) -> tuple[str, str]:
    event = ""
    game_time = ""
    for ln in lines:
        em = EVENT_RE.search(ln.text)
        if em:
            away = clean_text(em.group(1).strip())
            home = clean_text(em.group(2).strip())
            event = f"{away} @ {home}"
        tm = TIME_RE.search(ln.text)
        if tm and not game_time:
            game_time = normalize_time(tm.group(1))
    return event, game_time


def extract_wager_and_payout(lines: list[OCRLine], raw_text: str = "") -> tuple[str, str]:
    from .open_slip import extract_wager_and_payout_open

    joined = raw_text or "\n".join(ln.text for ln in lines)
    wager, payout = extract_wager_and_payout_open(lines, joined)
    if wager and payout:
        return wager, payout

    m_place = PLACE_BET_RE.search(joined)
    wager = m_place.group(1).replace(",", "") if m_place else ""

    payout = ""
    for ln in lines:
        if PAYOUT_RE.search(ln.text):
            m = MONEY_RE.search(ln.text)
            if m:
                payout = m.group(1).replace(",", "")
                break

    if not wager or not payout:
        for ln in lines:
            amounts = MONEY_RE.findall(ln.text)
            if len(amounts) >= 2 and PAYOUT_RE.search(ln.text):
                wager, payout = amounts[0].replace(",", ""), amounts[1].replace(",", "")
                break

    if not wager or not payout:
        for ln in lines:
            if re.search(r"final|quarter|placed\s*:|@\s+[A-Z]{2,4}\s", ln.text, re.I):
                continue
            amounts = MONEY_RE.findall(ln.text)
            if len(amounts) >= 2:
                if not wager:
                    wager = amounts[0].replace(",", "")
                if not payout:
                    payout = amounts[1].replace(",", "")
                if wager and payout:
                    break

    if not wager:
        wager = _money_near_keyword(lines, WAGER_RE)
    if not payout:
        payout = _money_near_keyword(lines, PAYOUT_RE)
    return wager, payout


def _money_near_keyword(lines: list[OCRLine], keyword_re: re.Pattern) -> str:
    for i, ln in enumerate(lines):
        if keyword_re.search(ln.text):
            for check in [ln.text] + [l.text for l in lines[i + 1 : i + 4]]:
                m = MONEY_RE.search(check)
                if m:
                    return m.group(1).replace(",", "")
    return ""


def extract_parlay_header(raw_text: str, lines: list[OCRLine]) -> tuple[str, str]:
    """Return (parlay_type label, total odds display)."""
    parlay_type = ""
    total_odds = ""

    scan = lines[: min(12, len(lines))]
    joined_top = " ".join(ln.text for ln in scan)

    if SGP_RE.search(joined_top):
        parlay_type = "Same Game Parlay"

    from .open_slip import extract_header_odds_open

    header_odds = extract_header_odds_open(lines[:12], raw_text)
    if header_odds:
        total_odds = header_odds

    for ln in scan:
        m_pick = PICK_PARLAY_RE.search(ln.text)
        m_leg = LEG_PARLAY_RE.search(ln.text)
        if m_pick:
            parlay_type = parlay_type or f"{m_pick.group(1)} Pick Parlay"
        elif m_leg:
            parlay_type = parlay_type or f"{m_leg.group(1)} Leg Parlay"

        if total_odds:
            continue
        for odds in AMERICAN_ODDS_RE.findall(ln.text):
            val = int(odds.replace("+", "").replace("-", ""))
            if abs(val) >= 100:
                total_odds = odds if odds.startswith(("+", "-")) else f"+{odds}"
                break
        if not total_odds:
            for num in re.findall(r"(?<!\d)(\+?\d{3,5})(?!\d)", ln.text):
                val = int(num.replace("+", "").replace("-", ""))
                if val >= 100:
                    total_odds = num if num.startswith(("+", "-")) else f"+{num}"
                    break
        if total_odds:
            break

    if not parlay_type:
        if SGP_RE.search(raw_text):
            parlay_type = "Same Game Parlay"
        elif m := PICK_PARLAY_RE.search(raw_text):
            parlay_type = f"{m.group(1)} Pick Parlay"
        elif m := LEG_PARLAY_RE.search(raw_text):
            parlay_type = f"{m.group(1)} Leg Parlay"

    return parlay_type or "Parlay", total_odds


def odds_american_int(display: str) -> int | None:
    if not display:
        return None
    try:
        val = int(display.replace("+", "").replace("-", ""))
        if display.strip().startswith("-"):
            return -val
        return val
    except ValueError:
        return None
