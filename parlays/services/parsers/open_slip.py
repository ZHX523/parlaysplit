"""
Parse open/active bet slip screenshots (FanDuel, DraftKings, similar layouts).

Handles:
- Wager / To Pay headers
- Pick parlay summary lines (comma-separated names)
- Player v player matchup markets
- Short selection + market line pairs (Yes, 20+, team + Moneyline)
"""

from __future__ import annotations

import re

from parlays.services.ocr.extract import OCRLine
from parlays.services.ocr.normalize import clean_text
from parlays.services.ocr.segmentation import AMERICAN_ODDS_RE

from .base import ParsedLeg
from .parser_common import MONEY_RE, build_description, map_leg_type

TO_PAY_RE = re.compile(r"to\s*pay", re.I)
WAGER_LABEL_RE = re.compile(r"wager\s*:", re.I)
MATCHUP_MARKET_RE = re.compile(
    r"(.+?)\s+v\s+(.+?)\s*[-–]\s*(.+?)(?:\s*moneyline)?\s*$",
    re.I,
)
_MONEYLINE_ONLY_RE = re.compile(r"^moneyline\s*$", re.I)
_SHORT_SEL_RE = re.compile(r"^(yes|no|under|over|\d{1,4}\+)$", re.I)
_THRESHOLD_IN_LINE_RE = re.compile(r"\b(\d{1,4})\+\b")
_STAT_MARKET_RE = re.compile(
    r"(double-double|triple-double|points|rebounds|assists|yards|touchdown|"
    r"three\s+pointers|moneyline|run\s+line|spread|goalscorer|anytime)",
    re.I,
)
_SKIP_OPEN_RE = re.compile(
    r"(pick\s+parlay|leg\s+parlay|sgpx?|wager\s*:|to\s*pay\s*:|boost|"
    r"cashed\s+out|voided|pushed|placed\s*:|final|quarter|parlay\s+boost|"
    r"ineligible|clear\s+all|view\s+all|reward|scoreboard|^\d+\s+\d+\s+\d+|"
    r"^q[1-4]\b|open\s*$|won\s*$|live\s+run)",
    re.I,
)
_COMMA_SUMMARY_RE = re.compile(
    r"^[A-Za-z][A-Za-z\s\.'\-]+(?:,\s*[A-Za-z][A-Za-z\s\.'\-]+){2,}$"
)
def _clean_name(name: str) -> str:
    name = re.sub(r"^[^\w$+]+", "", name).strip()
    name = re.sub(r"^[\w]{1,3}\s+", "", name)
    return name.strip()


def clean_open_line(text: str) -> str:
    t = clean_text(text)
    t = re.sub(r"^[^\w$+YesNO]+", "", t, flags=re.I).strip()
    t = t.replace("!", "l")
    t = re.sub(r"\s+", " ", t)
    return t


def is_skip_open_line(text: str) -> bool:
    if not text or len(text) < 2:
        return True
    if _SKIP_OPEN_RE.search(text):
        return True
    if re.search(r"has been voided|@\s+[A-Z]{2,4}\s+Today", text, re.I):
        return True
    if re.match(r"^[\W\d\s]{0,4}$", text):
        return True
    return False


def extract_wager_and_payout_open(lines: list[OCRLine], raw_text: str) -> tuple[str, str]:
    wager = ""
    payout = ""
    for ln in lines:
        t = ln.text
        if WAGER_LABEL_RE.search(t) or TO_PAY_RE.search(t):
            amounts = MONEY_RE.findall(t)
            if len(amounts) >= 2:
                wager, payout = amounts[0].replace(",", ""), amounts[1].replace(",", "")
            elif len(amounts) == 1:
                if WAGER_LABEL_RE.search(t):
                    wager = amounts[0].replace(",", "")
                elif TO_PAY_RE.search(t):
                    payout = amounts[0].replace(",", "")
            if wager and payout:
                break

    if not wager:
        m = re.search(r"wager\s*:\s*\$?\s*([\d,]+\.?\d*)", raw_text, re.I)
        if m:
            wager = m.group(1).replace(",", "")
    if not payout:
        m = re.search(r"to\s*pay\s*:\s*\$?\s*([\d,]+\.?\d*)", raw_text, re.I)
        if m:
            payout = m.group(1).replace(",", "")
    return wager, payout


def extract_header_odds_open(lines: list[OCRLine], raw_text: str) -> str:
    """Best-effort total odds (prefer boosted / last valid +odds in header)."""
    candidates: list[int] = []
    scan = "\n".join(ln.text for ln in lines[:8]) + raw_text[:400]
    scan = scan.replace("%", "1")
    for m in re.finditer(r"(?<!\d)(\+?\d{3,5})(?!\d)", scan):
        token = m.group(1)
        try:
            val = int(token.replace("+", "").replace("-", ""))
        except ValueError:
            continue
        if val >= 100:
            candidates.append(val)
    if not candidates:
        return ""
    best = max(candidates)
    return f"+{best}"


def _parse_matchup_line(text: str) -> ParsedLeg | None:
    m = MATCHUP_MARKET_RE.search(text)
    if not m:
        return None
    leg = ParsedLeg(confidence=0.8)
    leg.selection = _clean_name(m.group(2))
    leg.bet_type = re.sub(r"\s+", " ", m.group(3)).strip().upper()
    if "MONEYLINE" not in leg.bet_type.upper():
        leg.bet_type = f"{leg.bet_type} MONEYLINE"
    leg.leg_type = map_leg_type(leg.bet_type, leg.selection)
    leg.description = build_description(leg)
    return leg


def _parse_short_market_pair(short: str, market: str) -> ParsedLeg | None:
    market = clean_open_line(market)
    if not market or not _STAT_MARKET_RE.search(market):
        return None
    leg = ParsedLeg(confidence=0.75)
    th = _THRESHOLD_IN_LINE_RE.search(short)
    if th:
        leg.line = f"{th.group(1)}+"
        short_val = leg.line
    elif _SHORT_SEL_RE.match(short):
        short_val = short
    else:
        short_val = ""

    m = re.match(r"^(.+?)\s+(.+)$", market)
    if m and _STAT_MARKET_RE.search(m.group(2)):
        leg.selection = m.group(1).strip()
        leg.bet_type = m.group(2).upper()
    else:
        leg.selection = market
        leg.bet_type = "PROP"
    if short_val.lower() == "yes":
        leg.line = "Yes"
    elif short_val and not leg.line:
        leg.line = short_val
    leg.leg_type = map_leg_type(leg.bet_type, leg.selection)
    leg.description = build_description(leg)
    return leg


def _parse_name_moneyline(name: str) -> ParsedLeg:
    leg = ParsedLeg(confidence=0.78)
    leg.selection = clean_open_line(name)
    leg.bet_type = "MONEYLINE"
    leg.leg_type = "moneyline"
    leg.description = build_description(leg)
    return leg


def parse_comma_summary_legs(lines: list[OCRLine]) -> list[ParsedLeg]:
    for ln in lines[:20]:
        t = clean_open_line(ln.text)
        if t.count(",") < 3:
            continue
        if not re.search(r"[A-Za-z]{3,}", t):
            continue
        if re.search(r"wager|to pay|voided|boost|moneyline|score|under", t, re.I):
            continue
        if re.search(r"\d{3,}", t):
            continue
        parts = [clean_open_line(p) for p in re.split(r",\s*", t)]
        legs: list[ParsedLeg] = []
        for part in parts:
            if len(part) < 2 or re.search(r"\d{3,}", part):
                continue
            leg = ParsedLeg(confidence=0.5)
            leg.selection = part
            leg.bet_type = ""
            leg.leg_type = "moneyline"
            leg.description = part
            legs.append(leg)
        if len(legs) >= 3:
            return legs
    return []


def parse_open_slip_lines(lines: list[OCRLine]) -> list[ParsedLeg]:
    legs: list[ParsedLeg] = []
    i = 0
    n = len(lines)

    while i < n:
        text = clean_open_line(lines[i].text)
        if is_skip_open_line(text):
            i += 1
            continue

        matchup = _parse_matchup_line(text)
        if matchup:
            legs.append(matchup)
            i += 1
            continue

        if _STAT_MARKET_RE.search(text) and len(text) > 12:
            leg = ParsedLeg(confidence=0.65)
            th = _THRESHOLD_IN_LINE_RE.search(text)
            m = re.match(r"^(.+?)\s+(.+)$", text)
            if m and _STAT_MARKET_RE.search(m.group(2)):
                leg.selection = m.group(1).strip()
                leg.bet_type = m.group(2).upper()
            else:
                leg.selection = text
                leg.bet_type = "PROP"
            if th:
                leg.line = f"{th.group(1)}+"
            leg.leg_type = map_leg_type(leg.bet_type, leg.selection)
            leg.description = build_description(leg)
            legs.append(leg)
            i += 1
            continue

        if i + 1 < n:
            nxt = clean_open_line(lines[i + 1].text)
            if _MONEYLINE_ONLY_RE.match(nxt) and len(text) > 2:
                if not _STAT_MARKET_RE.search(text) and not MATCHUP_MARKET_RE.search(text):
                    legs.append(_parse_name_moneyline(text))
                    i += 2
                    continue
            pair = _parse_short_market_pair(text, nxt)
            if pair:
                legs.append(pair)
                i += 2
                continue

        th = _THRESHOLD_IN_LINE_RE.search(text)
        if th and (len(text) <= 8 or _SHORT_SEL_RE.match(text)):
            line_val = f"{th.group(1)}+"
            stat_parts: list[str] = []
            i += 1
            while i < n:
                nxt = clean_open_line(lines[i].text)
                if is_skip_open_line(nxt) or _THRESHOLD_IN_LINE_RE.search(nxt):
                    break
                if MATCHUP_MARKET_RE.search(nxt) or _MONEYLINE_ONLY_RE.match(nxt):
                    break
                stat_parts.append(nxt)
                i += 1
                if stat_parts and _STAT_MARKET_RE.search(" ".join(stat_parts)):
                    break
            if stat_parts:
                pair = _parse_short_market_pair(line_val, " ".join(stat_parts))
                if pair:
                    legs.append(pair)
            continue

        if _SHORT_SEL_RE.match(text) or text.lower() == "yes":
            if i + 1 < n:
                nxt = clean_open_line(lines[i + 1].text)
                pair = _parse_short_market_pair(text, nxt)
                if pair:
                    legs.append(pair)
                    i += 2
                    continue

        i += 1

    return legs


def merge_legs_with_summary(detail: list[ParsedLeg], summary: list[ParsedLeg]) -> list[ParsedLeg]:
    if len(summary) <= len(detail):
        return detail
    if len(detail) >= 3:
        return detail
    merged: list[ParsedLeg] = []
    for i, s in enumerate(summary):
        if i < len(detail) and detail[i].bet_type:
            merged.append(detail[i])
        else:
            merged.append(s)
    if len(detail) > len(merged):
        merged.extend(detail[len(merged) :])
    return merged
