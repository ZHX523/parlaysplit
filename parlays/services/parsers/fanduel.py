"""FanDuel mobile parlay screenshot parser."""

from __future__ import annotations

import re

from parlays.services.ocr.extract import OCRLine
from parlays.services.ocr.normalize import clean_text, normalize_odds_display, normalize_time
from parlays.services.ocr.segmentation import (
    AMERICAN_ODDS_RE,
    BET_TYPE_LINE_RE,
    EVENT_RE,
    HeaderRegion,
    LegBlock,
    PARLAY_HEADER_RE,
    SGP_HEADER_RE,
    SELECTION_START_RE,
)

from .base import BaseSlipParser, ParsedLeg, ParsedSlip

FANDUEL_MARKERS = re.compile(r"fanduel|fan\s*duel|sportsbook", re.I)
ODDS_TRAILING_RE = re.compile(r"\s([+-]\d{2,5})\s*$")
BET_TYPE_RE = re.compile(
    r"(\d+(?:ST|ND|RD|TH)\s+INNING\s+OVER/UNDER|"
    r"OVER/UNDER|"
    r"MONEYLINE|"
    r"SPREAD|"
    r"TO\s+SCORE\s+\d+\+?\s*POINTS|"
    r"TO\s+SCORE|"
    r"PLAYER\s+POINTS|"
    r"PLAYER\s+REBOUNDS|"
    r"REBOUNDS|"
    r"PLAYER\s+ASSISTS|"
    r"TOTAL\s+POINTS|"
    r"TOTAL\s+RUNS|"
    r"RUN\s+LINE|"
    r"PUCK\s+LINE)",
    re.I,
)
LINE_VALUE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(RUNS|POINTS|GOALS|REBOUNDS|ASSISTS)?",
    re.I,
)
TIME_RE = re.compile(r"(\d{1,2}:?\d{2}\s*[AP]M\s*ET)", re.I)
BARE_ODDS_TAIL_RE = re.compile(r"\s(\d{3,4})\s*$")
WAGER_RE = re.compile(r"(wager|risk|bet amount|total wager)", re.I)
PAYOUT_RE = re.compile(r"(payout|to win|potential|total payout)", re.I)
MONEY_RE = re.compile(r"\$?\s*([\d,]+\.\d{2})")
SELECTION_PREFIX_RE = re.compile(
    r"^[\(\[]\s*\w{0,3}\s+|^[YSJ]\s+|^Sp\s+|^\(S>\s*|^\(S>\s*|^LG\s+",
    re.I,
)
PLAYER_UNDER_RE = re.compile(r"^(.+?)\s+Under\s+([\d.,]+)\s*$", re.I)


def _map_leg_type(bet_type: str, selection: str) -> str:
    bt = bet_type.upper()
    sel = selection.lower()
    if "MONEYLINE" in bt:
        return "moneyline"
    if "SPREAD" in bt or "RUN LINE" in bt or "PUCK LINE" in bt:
        return "spread"
    if "REBOUND" in bt or ("under" in sel and "rebound" in bt):
        return "player_prop"
    if "TO SCORE" in bt or "PLAYER" in bt or "ASSIST" in bt:
        return "player_prop"
    if "OVER/UNDER" in bt or "TOTAL" in bt or sel in ("over", "under"):
        return "total_points"
    return "moneyline"


def _default_odds_sign(selection: str) -> str:
    return "-" if selection.lower() == "under" else "+"


def _clean_selection_name(value: str) -> str:
    text = clean_text(value)
    text = SELECTION_PREFIX_RE.sub("", text)
    text = re.sub(r"^[\(\[]|[\)\]]\s*$", "", text).strip()
    return text


def _parse_bet_type_line(text: str) -> tuple[str, str]:
    raw = clean_text(text).upper()
    raw = raw.replace("#", "+")
    if "MONEYLINE" in raw:
        return "MONEYLINE", ""
    score_m = re.search(r"TO\s+SCORE\s+(\d+\+?)\s*POINTS", raw, re.I)
    if score_m:
        return "TO SCORE POINTS", score_m.group(1)
    if "REBOUND" in raw:
        return "PLAYER REBOUNDS", ""
    if "ASSIST" in raw:
        return "PLAYER ASSISTS", ""
    bt_match = BET_TYPE_RE.search(raw)
    if bt_match:
        label = bt_match.group(1).upper()
        remainder = raw[bt_match.end() :].strip()
        lv = LINE_VALUE_RE.search(remainder)
        line = lv.group(1) if lv else ""
        return label, line
    return raw[:60], ""


def _odds_from_selection_line(line: OCRLine, selection: str) -> str:
    text = clean_text(line.text)
    m_odds = ODDS_TRAILING_RE.search(text)
    if m_odds:
        return normalize_odds_display(m_odds.group(1))
    for odds in AMERICAN_ODDS_RE.findall(text):
        if abs(int(odds)) >= 100:
            return normalize_odds_display(odds)
    if line.words:
        right_edge = max(w.right for w in line.words)
        cutoff = right_edge * 0.52
        for word in reversed(line.words):
            if word.left < cutoff:
                continue
            token = re.sub(r"[^\d+-]", "", word.text)
            if re.fullmatch(r"[+-]\d{2,5}", token):
                return normalize_odds_display(token)
            if re.fullmatch(r"\d{3,4}", token):
                return f"{_default_odds_sign(selection)}{token}"
    m_tail = BARE_ODDS_TAIL_RE.search(text)
    if m_tail:
        return f"{_default_odds_sign(selection)}{m_tail.group(1)}"
    return ""


def _build_description(leg: ParsedLeg) -> str:
    parts = []
    if leg.selection:
        parts.append(leg.selection)
    if leg.bet_type:
        bt = leg.bet_type
        if leg.line:
            bt = f"{bt} {leg.line}"
        parts.append(bt)
    elif leg.line:
        parts.append(leg.line)
    if leg.event:
        parts.append(leg.event)
    if leg.game_time:
        parts.append(leg.game_time)
    return " · ".join(parts)[:500]


def _parse_leg_block(block: LegBlock) -> ParsedLeg:
    texts = [clean_text(ln.text) for ln in block.lines if clean_text(ln.text)]
    leg = ParsedLeg(confidence=block.avg_conf)
    uncertain: list[str] = []

    if not texts:
        uncertain.extend(["selection", "bet_type"])
        leg.uncertain_fields = uncertain
        return leg

    line0 = texts[0]
    line1 = texts[1] if len(texts) > 1 else ""
    idx = 0

    player_under = PLAYER_UNDER_RE.match(line0)
    if player_under:
        name = _clean_selection_name(player_under.group(1))
        line_val = player_under.group(2).replace(",", ".")
        leg.selection = f"{name} Under {line_val}"
        leg.line = line_val
        leg.bet_type = "PLAYER REBOUNDS"
        if line1:
            if "REBOUND" in line1.upper():
                leg.bet_type = "PLAYER REBOUNDS"
            idx = 2
        else:
            idx = 1
    elif SELECTION_START_RE.match(line0):
        m_sel = SELECTION_START_RE.match(line0)
        leg.selection = m_sel.group(1).title() if m_sel else ""
        leg.odds = _odds_from_selection_line(block.lines[0], leg.selection)
        if not leg.odds:
            uncertain.append("odds")
        idx = 1
        if idx < len(texts):
            bt_match = BET_TYPE_RE.search(texts[idx])
            if bt_match:
                leg.bet_type = bt_match.group(1).upper()
                remainder = texts[idx][bt_match.end() :].strip()
                lv = LINE_VALUE_RE.search(remainder)
                if lv:
                    leg.line = lv.group(1)
                idx += 1
    elif line1 and _is_bet_type_line(line1):
        leg.selection = _clean_selection_name(line0)
        leg.bet_type, leg.line = _parse_bet_type_line(line1)
        idx = 2
    else:
        leg.selection = _clean_selection_name(line0)
        if line1:
            leg.bet_type, extra_line = _parse_bet_type_line(line1)
            if extra_line and not leg.line:
                leg.line = extra_line
            idx = 2
        else:
            uncertain.append("bet_type")

    for rest in texts[idx:]:
        if EVENT_RE.search(rest) or "@" in rest:
            continue
        if re.search(r"bet\s*id|/\d{4}|location\s*verified", rest, re.I):
            continue
        tm = TIME_RE.search(rest)
        if tm:
            leg.game_time = normalize_time(tm.group(1))

    if not leg.selection:
        uncertain.append("selection")
    if not leg.bet_type:
        uncertain.append("bet_type")

    leg.leg_type = _map_leg_type(leg.bet_type, leg.selection)
    leg.description = _build_description(leg)
    leg.uncertain_fields = uncertain
    if uncertain:
        leg.confidence = max(0.0, leg.confidence - 0.12 * len(uncertain))
    return leg


def _is_bet_type_line(text: str) -> bool:
    t = clean_text(text).upper()
    return bool(BET_TYPE_LINE_RE.search(t)) and len(t) < 80


def _extract_shared_event(lines: list[OCRLine]) -> tuple[str, str]:
    event = ""
    game_time = ""
    for ln in lines:
        em = EVENT_RE.search(ln.text)
        tm = TIME_RE.search(ln.text)
        if em:
            away = clean_text(em.group(1).strip())
            home = clean_text(em.group(2).strip())
            event = f"{away} @ {home}"
        if tm and not game_time and not re.search(
            r"bet\s*id|/\d{4}|location\s*verified", ln.text, re.I
        ):
            game_time = normalize_time(tm.group(1))
    return event, game_time


def _extract_wager_and_payout(lines: list[OCRLine]) -> tuple[str, str]:
    wager = ""
    payout = ""
    for ln in lines:
        amounts = MONEY_RE.findall(ln.text)
        if len(amounts) >= 2:
            wager, payout = amounts[0].replace(",", ""), amounts[1].replace(",", "")
            return wager, payout
    wager = _extract_money_from_lines(lines, WAGER_RE)
    payout = _extract_money_from_lines(lines, PAYOUT_RE)
    return wager, payout


def _extract_money_from_lines(lines: list[OCRLine], keyword_re: re.Pattern) -> str:
    for i, ln in enumerate(lines):
        if keyword_re.search(ln.text):
            for check in [ln.text] + [l.text for l in lines[i + 1 : i + 3]]:
                m = MONEY_RE.search(check)
                if m:
                    return m.group(1).replace(",", "")
    return ""


def _sgp_summary_text(lines: list[OCRLine]) -> str:
    parts: list[str] = []
    for ln in lines[:20]:
        t = clean_text(ln.text)
        if EVENT_RE.search(t) and "@" in t:
            break
        if SGP_HEADER_RE.search(t) and re.search(r"\d{3,5}", t):
            continue
        if "," in t or re.search(r"moneyline|score|under", t, re.I):
            parts.append(t)
    return " ".join(parts)


def _parse_sgp_summary_legs(lines: list[OCRLine]) -> list[ParsedLeg]:
    """Parse legs from the comma-separated SGP summary under the header."""
    full = _sgp_summary_text(lines)
    if not full or not re.search(r"moneyline|score|under", full, re.I):
        return []

    legs: list[ParsedLeg] = []
    for chunk in re.split(r"\s*,\s*", full):
        chunk = clean_text(chunk)
        if len(chunk) < 4:
            continue
        if chunk.lower() in ("points", "point", "a"):
            continue
        leg = ParsedLeg(confidence=0.55)

        if re.search(r"moneyline", chunk, re.I):
            team = re.sub(r"moneyline.*", "", chunk, flags=re.I).strip(" .")
            leg.selection = _clean_selection_name(team)
            leg.bet_type = "MONEYLINE"
            leg.leg_type = "moneyline"
        elif re.search(r"(?:ta\s+scor|to\s+scor|scor\w*\s*\d)", chunk, re.I):
            m = re.match(r"^(.+?)\s+(?:ta\s+scor|to\s+scor)", chunk, re.I)
            leg.selection = _clean_selection_name(m.group(1) if m else chunk)
            m_line = re.search(r"(\d+\+?)", chunk)
            leg.line = m_line.group(1).replace("#", "+") if m_line else ""
            leg.bet_type = "TO SCORE POINTS"
            leg.leg_type = "player_prop"
        elif re.search(r"\bunder\b", chunk, re.I):
            m = re.search(r"^(.+?)\s+under(?:\s+([\d.,]+))?", chunk, re.I)
            if m:
                name = _clean_selection_name(m.group(1))
                line_val = (m.group(2) or "").replace(",", ".")
                if not line_val or not re.search(r"\d", line_val):
                    tail = re.search(r"under\D*([\d.,]+\d|\d[\d.,]*)", chunk, re.I)
                    line_val = (tail.group(1) if tail else "").replace(",", ".")
                if line_val and re.search(r"\d", line_val):
                    leg.selection = f"{name} Under {line_val}"
                    leg.line = line_val
                else:
                    leg.selection = name
                leg.bet_type = "PLAYER REBOUNDS"
                leg.leg_type = "player_prop"
        else:
            continue

        if leg.selection or leg.bet_type:
            leg.description = _build_description(leg)
            legs.append(leg)

    return legs


class FanDuelParser(BaseSlipParser):
    sportsbook_name = "FanDuel"

    @classmethod
    def detect(cls, lines: list[OCRLine], raw_text: str) -> bool:
        from .draftkings import DraftKingsParser

        if DraftKingsParser.detect(lines, raw_text):
            return False
        joined = raw_text.lower()
        if FANDUEL_MARKERS.search(joined):
            return True
        if re.search(r"\d+\s*pick\s+parlay", joined, re.I) and re.search(
            r"to\s*pay\s*:|wager\s*:|double-double|three\s+pointers",
            joined,
            re.I,
        ):
            return True
        if re.search(r"sgpx?\b", joined, re.I):
            return True
        if re.search(r"\d+\s*pick\s+parlay", joined, re.I):
            return False
        if SGP_HEADER_RE.search(joined):
            return True
        if PARLAY_HEADER_RE.search(joined) and "@" in joined:
            return True
        over_under_count = sum(1 for ln in lines if SELECTION_START_RE.match(ln.text))
        return over_under_count >= 2

    def parse(
        self,
        lines: list[OCRLine],
        header: HeaderRegion | None,
        leg_blocks: list[LegBlock],
        raw_text: str,
    ) -> ParsedSlip:
        slip = ParsedSlip(sportsbook=self.sportsbook_name, raw_text=raw_text)
        uncertain: list[str] = []

        if header:
            slip.parlay_type = header.parlay_type
            slip.total_odds = header.total_odds_display
            if header.total_odds_display:
                try:
                    slip.total_odds_american = int(
                        header.total_odds_display.replace("+", "").replace("-", "")
                    )
                    if header.total_odds_display.startswith("-"):
                        slip.total_odds_american = -slip.total_odds_american
                except ValueError:
                    uncertain.append("total_odds")
            else:
                uncertain.append("total_odds")
        else:
            uncertain.extend(["parlay_type", "total_odds"])

        from .parser_common import extract_wager_and_payout as _extract_wager_payout_common

        slip.wager_amount, slip.potential_payout = _extract_wager_payout_common(
            lines, raw_text
        )
        shared_event, shared_time = _extract_shared_event(lines)

        parsed_legs = [_parse_leg_block(block) for block in leg_blocks]
        use_open = bool(
            re.search(r"to\s*pay\s*:|wager\s*:", raw_text, re.I)
            or re.search(r"sgpx?\b", raw_text, re.I)
        )
        if use_open:
            from .open_slip import (
                merge_legs_with_summary,
                parse_comma_summary_legs,
                parse_open_slip_lines,
            )

            open_legs = parse_open_slip_lines(lines)
            if len(open_legs) > len(parsed_legs):
                parsed_legs = open_legs
            summary_legs = parse_comma_summary_legs(lines)
            if summary_legs:
                parsed_legs = merge_legs_with_summary(parsed_legs, summary_legs)
        if SGP_HEADER_RE.search(raw_text):
            summary_legs = _parse_sgp_summary_legs(lines)
            if len(summary_legs) > len(parsed_legs):
                parsed_legs = summary_legs

        slip.legs = []
        for lg in parsed_legs:
            if not (lg.selection or lg.bet_type):
                continue
            if shared_event and not lg.event:
                lg.event = shared_event
            if shared_time and not lg.game_time:
                lg.game_time = shared_time
            lg.description = _build_description(lg)
            slip.legs.append(lg)

        if header and SGP_HEADER_RE.search(raw_text) and slip.legs:
            base = header.parlay_type or "Same Game Parlay"
            if "same game" not in base.lower():
                base = "Same Game Parlay"
            slip.parlay_type = f"{len(slip.legs)} Leg {base}"

        if not slip.legs:
            uncertain.append("legs")

        leg_confs = [lg.confidence for lg in slip.legs] or [0.0]
        field_penalty = 0.05 * len(uncertain)
        slip.confidence = max(0.0, min(1.0, sum(leg_confs) / len(leg_confs) - field_penalty))
        slip.uncertain_fields = uncertain

        if slip.total_odds and not slip.total_odds_american:
            m = AMERICAN_ODDS_RE.search(slip.total_odds)
            if m:
                try:
                    slip.total_odds_american = int(m.group(1).replace("+", ""))
                except ValueError:
                    pass

        return slip
