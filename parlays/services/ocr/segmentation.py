"""Segment OCR lines into header and parlay leg blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .extract import OCRLine
from .normalize import clean_text

PARLAY_HEADER_RE = re.compile(
    r"(\d+)\s*[- ]?\s*(?:leg|pick)\s+parlay",
    re.IGNORECASE,
)
SGP_HEADER_RE = re.compile(r"same\s*game\s*parlay", re.IGNORECASE)
AMERICAN_ODDS_RE = re.compile(r"(?<!\d)([+-]\d{2,5})(?!\d)")
SELECTION_START_RE = re.compile(r"^(over|under)\b", re.IGNORECASE)
EVENT_RE = re.compile(
    r"([A-Za-z0-9][A-Za-z0-9\s\.'\-]+?)\s+@\s+([A-Za-z0-9][A-Za-z0-9\s\.'\-]+)",
)
BET_TYPE_LINE_RE = re.compile(
    r"(MONEYLINE|TO\s+SCORE|REBOUND|ASSIST|POINTS|SPREAD|OVER/UNDER|RUN\s+LINE|"
    r"PASSING\s+YARDS|RUSHING|RECEIVING|TOUCHDOWN)",
    re.IGNORECASE,
)
SUMMARY_LINE_RE = re.compile(
    r"(moneyline).*,.*(points|rebound|score)",
    re.IGNORECASE,
)
SKIP_LINE_RE = re.compile(
    r"^(bet slip|receipt|total payout|to win|wager|risk|fanduel|draftkings|"
    r"betmgm|caesars|kalshi|placed|cash out|reuse|share|location|verified|bet\s*id)",
    re.IGNORECASE,
)
FOOTER_RE = re.compile(
    r"(cash out|reuse selections|share bet|total wager|total payout|bet\s*id|^\$[\d.])",
    re.IGNORECASE,
)
FOOTER_LINE_RE = re.compile(
    r"(bet\s*id|location\s*verified|reuse\s+selection|^ponl$|^ss$|^qte\s*\)|^-\s*ra$)",
    re.IGNORECASE,
)


@dataclass
class HeaderRegion:
    parlay_type: str
    total_odds_display: str
    lines: tuple[OCRLine, ...]


@dataclass
class LegBlock:
    lines: tuple[OCRLine, ...]
    avg_conf: float


def _avg_conf(lines: list[OCRLine]) -> float:
    if not lines:
        return 0.0
    return sum(ln.conf for ln in lines) / len(lines)


def extract_header(lines: list[OCRLine]) -> HeaderRegion | None:
    """Find parlay title and total odds from top section."""
    parlay_type = ""
    total_odds_display = ""
    header_lines: list[OCRLine] = []

    scan = lines[: min(10, len(lines))]
    header_bottom = (scan[0].top + 80) if scan else 0

    for ln in scan:
        if SGP_HEADER_RE.search(ln.text):
            parlay_type = "Same Game Parlay"
            header_lines.append(ln)
            header_bottom = max(header_bottom, ln.top + 48)
            for odds in AMERICAN_ODDS_RE.findall(ln.text):
                val = int(odds)
                if abs(val) >= 100:
                    total_odds_display = odds if odds.startswith(("+", "-")) else f"+{odds}"
                    break
            if not total_odds_display:
                for num in re.findall(r"(?<!\d)(\d{3,5})(?!\d)", ln.text):
                    if int(num) >= 200:
                        total_odds_display = f"+{num}" if not num.startswith("-") else num
                        break

        m = PARLAY_HEADER_RE.search(ln.text)
        if m:
            count = m.group(1)
            kind = "Pick" if re.search(r"pick\s+parlay", ln.text, re.I) else "Leg"
            parlay_type = f"{count} {kind} Parlay"
            header_lines.append(ln)
            header_bottom = max(header_bottom, ln.top + 48)
            for odds in AMERICAN_ODDS_RE.findall(ln.text):
                val = int(odds)
                if abs(val) >= 100:
                    total_odds_display = odds if odds.startswith(("+", "-")) else f"+{odds}"
                    break
            if not total_odds_display:
                for num in re.findall(r"(?<!\d)(\d{4,5})(?!\d)", ln.text):
                    if int(num) >= 1000:
                        total_odds_display = f"+{num}"
                        break

    if not parlay_type and scan:
        joined = " ".join(ln.text for ln in scan[:4])
        if SGP_HEADER_RE.search(joined):
            parlay_type = "Same Game Parlay"
        else:
            m = PARLAY_HEADER_RE.search(joined)
            if m:
                parlay_type = f"{m.group(1)} Leg Parlay"

    if not total_odds_display:
        for ln in scan:
            if ln.top > header_bottom:
                continue
            for odds in AMERICAN_ODDS_RE.findall(ln.text):
                val = int(odds)
                if val >= 200 or (odds.startswith("+") and val >= 100):
                    total_odds_display = odds if odds.startswith(("+", "-")) else f"+{odds}"
                    if ln not in header_lines:
                        header_lines.append(ln)
                    break
            if total_odds_display:
                break

    if not parlay_type and not total_odds_display:
        return None
    return HeaderRegion(
        parlay_type=parlay_type or "Parlay",
        total_odds_display=total_odds_display,
        lines=tuple(header_lines),
    )


def _is_bet_type_line(text: str) -> bool:
    t = clean_text(text).upper()
    return bool(BET_TYPE_LINE_RE.search(t)) and len(t) < 80


def _is_leg_start(line: OCRLine, next_line: OCRLine | None = None) -> bool:
    t = clean_text(line.text)
    if not t or FOOTER_RE.search(t):
        return False
    if re.search(r"over/under", t, re.I):
        return False
    if SELECTION_START_RE.match(t):
        return True
    if re.match(r"^under\s+", t, re.I):
        return True
    if re.search(r"\s+under\s+[\d.,]+", t, re.I):
        return True
    if next_line and _is_bet_type_line(next_line.text):
        if EVENT_RE.search(t) or "@" in t:
            return False
        if SUMMARY_LINE_RE.search(t) or t.count(",") >= 2:
            return False
        if len(t) > 3 and not re.match(r"^(total|oklahoma|same game)", t, re.I):
            return True
    return False


def _body_start_index(lines: list[OCRLine], *, same_game: bool) -> int:
    """Skip header/summary; for SGP skip the single matchup line before leg list."""
    if same_game:
        for i, ln in enumerate(lines):
            if EVENT_RE.search(ln.text) and "@" in ln.text:
                return i + 1
        return 0

    for i, ln in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if _is_leg_start(ln, nxt):
            return i
    for i, ln in enumerate(lines):
        if PARLAY_HEADER_RE.search(ln.text) or SGP_HEADER_RE.search(ln.text):
            return i + 1
    return 0


def _include_in_body(line: OCRLine, *, same_game: bool) -> bool:
    t = clean_text(line.text)
    if not t or len(t) < 2:
        return False
    if SKIP_LINE_RE.match(t):
        return False
    if FOOTER_RE.search(t):
        return False
    if SUMMARY_LINE_RE.search(t):
        return False
    if SGP_HEADER_RE.search(t) and AMERICAN_ODDS_RE.search(t):
        return False
    if PARLAY_HEADER_RE.search(t) and not _is_leg_start(line):
        return False
    if same_game and EVENT_RE.search(t) and "@" in t:
        return False
    return True


def _is_footer_line(text: str) -> bool:
    t = clean_text(text)
    if not t:
        return True
    if FOOTER_RE.search(t) or FOOTER_LINE_RE.search(t):
        return True
    if re.search(r"^\d+/\d{6}", t):
        return True
    return False


def segment_sgp_leg_blocks(body: list[OCRLine]) -> list[list[OCRLine]]:
    """
    Same Game Parlay: each leg ends with a bet-type line (MONEYLINE, TO SCORE, REBOUNDS).
    More reliable than selection-start heuristics on noisy mobile OCR.
    """
    blocks: list[list[OCRLine]] = []
    current: list[OCRLine] = []

    for ln in body:
        if _is_footer_line(ln.text):
            break
        t = clean_text(ln.text)
        if not t:
            continue
        current.append(ln)
        if _is_bet_type_line(t):
            blocks.append(current)
            current = []

    if current:
        cleaned = [l for l in current if not _is_footer_line(l.text)]
        if cleaned and any(_is_bet_type_line(clean_text(l.text)) for l in cleaned):
            blocks.append(cleaned)

    return blocks


def segment_leg_blocks(lines: list[OCRLine], header: HeaderRegion | None) -> list[LegBlock]:
    """Split lines into vertical leg sections."""
    same_game = bool(header and "same game" in header.parlay_type.lower())
    if not same_game:
        joined = " ".join(ln.text for ln in lines[:6])
        same_game = bool(SGP_HEADER_RE.search(joined))
    start = _body_start_index(lines, same_game=same_game)

    body: list[OCRLine] = []
    for ln in lines[start:]:
        if _include_in_body(ln, same_game=same_game):
            body.append(ln)

    if not body:
        return []

    if same_game:
        blocks = segment_sgp_leg_blocks(body)
    else:
        blocks: list[list[OCRLine]] = []
        current: list[OCRLine] = []

        for i, ln in enumerate(body):
            nxt = body[i + 1] if i + 1 < len(body) else None
            if _is_leg_start(ln, nxt) and current:
                blocks.append(current)
                current = [ln]
            elif _is_leg_start(ln, nxt) and not current:
                current = [ln]
            else:
                if current:
                    current.append(ln)
                elif _is_bet_type_line(ln.text):
                    continue
                else:
                    current = [ln]

        if current:
            blocks.append(current)

        if not blocks:
            blocks = _fallback_segment_by_selection(body)

    return [LegBlock(lines=tuple(b), avg_conf=_avg_conf(b)) for b in blocks if b]


def _fallback_segment_by_selection(lines: list[OCRLine]) -> list[list[OCRLine]]:
    blocks: list[list[OCRLine]] = []
    current: list[OCRLine] = []
    for i, ln in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if _is_leg_start(ln, nxt) and current:
            blocks.append(current)
            current = [ln]
        elif _is_leg_start(ln, nxt):
            current = [ln]
        else:
            current.append(ln)
    if current:
        blocks.append(current)
    return blocks
