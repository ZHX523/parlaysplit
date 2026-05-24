"""DraftKings mobile bet slip parser."""

from __future__ import annotations

import re

from parlays.services.ocr.extract import OCRLine
from parlays.services.ocr.normalize import clean_text
from parlays.services.ocr.segmentation import HeaderRegion, LegBlock, SGP_HEADER_RE

from .base import BaseSlipParser, ParsedLeg, ParsedSlip
from .open_slip import (
    extract_header_odds_open,
    extract_wager_and_payout_open,
    merge_legs_with_summary,
    parse_comma_summary_legs,
    parse_open_slip_lines,
)
from .parser_common import (
    build_description,
    extract_parlay_header,
    extract_shared_event,
    extract_wager_and_payout,
    map_leg_type,
    odds_american_int,
)

_DK_MARKER = re.compile(r"draft\s*kings|draftkings|crown\s*club", re.I)
_TO_PAY_RE = re.compile(r"to\s*pay\s*:", re.I)
_MATCHUP_HINT_RE = re.compile(r"\s+v\s+.+-\s+.+moneyline", re.I)
_THRESHOLD_RE = re.compile(r"(?:^|[^\d])(\d{1,4})\+\s*$")
_MONEYLINE_RE = re.compile(r"^moneyline\b", re.I)
_STAT_LINE_RE = re.compile(
    r"(passing|rushing|receiving|touchdown|yards|assists|rebounds|points|spread|total)",
    re.I,
)
_SKIP_RE = re.compile(
    r"^(same game parlay|\d+\s*pick\s+parlay|bet\s*slip|clear\s*all|payout:|"
    r"place\s*bet|total\s*payout|reward|view\s*all|crown\s*club|add\s*picks|"
    r"turn\s*to|more\s*info|game\s*will\s*be|cash\s*out|sgpx|ot\.)",
    re.I,
)
_TEAM_LINE_RE = re.compile(
    r"^([A-Z]{2,4}\s+[A-Za-z][A-Za-z\s\.'\-]+|[A-Za-z][A-Za-z\s\.'\-]+\s+"
    r"(Colts|Falcons|Thunder|Spurs|Lakers|Celtics|Chiefs|Eagles))",
    re.I,
)
_OCR_NOISE = re.compile(r"^[atl\]>@\-•\s]+$", re.I)
_INCOMPLETE_STAT_END = re.compile(
    r"(passing|rushing|receiving|touchdown)\s*$",
    re.I,
)


def _clean_line(text: str) -> str:
    t = clean_text(text)
    t = re.sub(r"^[^\w$+]+", "", t).strip()
    t = t.replace("!", "l")
    t = re.sub(r"(?i)payout:\s*\$?[\d,.]+", "", t).strip()
    return t


def _is_skip(text: str) -> bool:
    if not text or len(text) < 2:
        return True
    if _THRESHOLD_RE.search(text):
        return False
    if _SKIP_RE.search(text):
        return True
    if _OCR_NOISE.match(text):
        return True
    if re.search(r"^\d+:\d+\s", text):
        return True
    if "@" in text and re.search(r"falcons|colts|@\s", text, re.I):
        return True
    return False


def _parse_threshold_leg(threshold: str, stat_parts: list[str]) -> ParsedLeg | None:
    stat = " ".join(stat_parts).strip()
    if not stat:
        return None
    leg = ParsedLeg(confidence=0.72)
    leg.line = threshold

    m = re.match(
        r"^(.+?)\s+(passing\s+yards|rushing\s*\+\s*receiving\s+yards|"
        r"receiving\s+yards|passing\s+touchdowns|"
        r"rushing\s+yards|three\s+pointers\s+made|double-double|points\s*\+\s*rebounds)",
        stat,
        re.I,
    )
    if m:
        leg.selection = m.group(1).strip()
        leg.bet_type = re.sub(r"\s+", " ", m.group(2)).upper()
    else:
        parts = stat.rsplit(" ", 3)
        if len(parts) >= 2 and _STAT_LINE_RE.search(stat):
            leg.selection = " ".join(parts[:-2]).strip() if len(parts) > 3 else parts[0]
            leg.bet_type = " ".join(parts[-2:]).upper()
        else:
            leg.selection = stat
            leg.bet_type = "PLAYER PROP"

    leg.leg_type = map_leg_type(leg.bet_type, leg.selection)
    leg.description = build_description(leg)
    return leg


def _stat_parts_complete(stat_parts: list[str]) -> bool:
    stat = " ".join(stat_parts).strip()
    if not stat or not _STAT_LINE_RE.search(stat):
        return False
    if _INCOMPLETE_STAT_END.search(stat):
        return False
    return bool(
        re.search(
            r"yards|touchdowns|moneyline|spread|total|points|assists|rebounds|"
            r"double-double|three\s+pointers",
            stat,
            re.I,
        )
    )


def _parse_moneyline_leg(team_line: str) -> ParsedLeg:
    team = re.sub(r"(?i)\s*payout:.*$", "", team_line).strip()
    team = re.sub(r"^[^\w]+", "", team).strip()
    leg = ParsedLeg(confidence=0.78)
    leg.selection = team
    leg.bet_type = "MONEYLINE"
    leg.leg_type = "moneyline"
    leg.description = build_description(leg)
    return leg


def parse_draftkings_mobile_lines(lines: list[OCRLine]) -> list[ParsedLeg]:
    """Parse DK bet-slip upload layout (threshold + stat, team moneyline)."""
    legs: list[ParsedLeg] = []
    i = 0
    n = len(lines)

    while i < n:
        text = _clean_line(lines[i].text)
        if _is_skip(text):
            i += 1
            continue

        th = _THRESHOLD_RE.search(text)
        if th:
            threshold = f"{th.group(1)}+"
            stat_parts: list[str] = []
            i += 1
            while i < n:
                nxt = _clean_line(lines[i].text)
                if _is_skip(nxt):
                    i += 1
                    continue
                if _THRESHOLD_RE.search(nxt):
                    break
                if _MONEYLINE_RE.match(nxt):
                    break
                if (
                    _TEAM_LINE_RE.match(nxt)
                    and not _STAT_LINE_RE.search(nxt)
                    and not stat_parts
                ):
                    break
                stat_parts.append(nxt)
                i += 1
                if _stat_parts_complete(stat_parts):
                    break
            leg = _parse_threshold_leg(threshold, stat_parts)
            if leg:
                legs.append(leg)
            continue

        if _MONEYLINE_RE.match(text) and legs:
            i += 1
            continue

        if re.search(r"[A-Za-z]{2,}.*(passing|receiving|rushing)", text, re.I):
            stat_parts = [text]
            i += 1
            while i < n:
                nxt = _clean_line(lines[i].text)
                if _THRESHOLD_RE.search(nxt) or _is_skip(nxt):
                    break
                if _MONEYLINE_RE.match(nxt):
                    break
                stat_parts.append(nxt)
                i += 1
                if _stat_parts_complete(stat_parts):
                    break
            if _stat_parts_complete(stat_parts):
                leg = _parse_threshold_leg("1+", stat_parts)
                if leg:
                    legs.append(leg)
            continue

        if i + 1 < n:
            nxt = _clean_line(lines[i + 1].text)
            if _MONEYLINE_RE.match(nxt) and not _STAT_LINE_RE.search(text):
                legs.append(_parse_moneyline_leg(text))
                i += 2
                continue

        i += 1

    return legs


def _is_open_slip(raw_text: str) -> bool:
    return bool(_TO_PAY_RE.search(raw_text) or _MATCHUP_HINT_RE.search(raw_text))


class DraftKingsParser(BaseSlipParser):
    sportsbook_name = "DraftKings"

    @classmethod
    def detect(cls, lines: list[OCRLine], raw_text: str) -> bool:
        joined = raw_text.lower()
        if _DK_MARKER.search(joined):
            if "fanduel" in joined or "fan duel" in joined:
                return False
            return True
        pick = bool(re.search(r"\d+\s*pick\s+parlay", joined, re.I))
        matchup_hits = sum(1 for ln in lines if _MATCHUP_HINT_RE.search(ln.text))
        stat_hits = sum(
            1
            for ln in lines
            if re.search(r"(passing|rushing|receiving)\s+yards", ln.text, re.I)
        )
        if pick and _TO_PAY_RE.search(joined):
            if _DK_MARKER.search(joined) or matchup_hits >= 2:
                return True
        return pick and (stat_hits >= 2 or matchup_hits >= 2)

    def parse(
        self,
        lines: list[OCRLine],
        header: HeaderRegion | None,
        leg_blocks: list[LegBlock],
        raw_text: str,
    ) -> ParsedSlip:
        slip = ParsedSlip(sportsbook=self.sportsbook_name, raw_text=raw_text)
        uncertain: list[str] = []

        parlay_type, total_odds = extract_parlay_header(raw_text, lines)
        if header and header.parlay_type:
            parlay_type = header.parlay_type or parlay_type
        if header and header.total_odds_display:
            total_odds = header.total_odds_display or total_odds
        if not total_odds:
            total_odds = extract_header_odds_open(lines, raw_text)

        slip.parlay_type = parlay_type
        slip.total_odds = total_odds
        slip.total_odds_american = odds_american_int(total_odds)
        if not slip.total_odds:
            uncertain.append("total_odds")

        slip.wager_amount, slip.potential_payout = extract_wager_and_payout(lines, raw_text)
        if not slip.wager_amount:
            uncertain.append("wager_amount")
        if not slip.potential_payout:
            uncertain.append("potential_payout")

        shared_event, shared_time = extract_shared_event(lines)

        if _is_open_slip(raw_text):
            open_legs = parse_open_slip_lines(lines)
            summary_legs = parse_comma_summary_legs(lines)
            parsed_legs = merge_legs_with_summary(open_legs, summary_legs)
        else:
            parsed_legs = parse_draftkings_mobile_lines(lines)
            open_legs = parse_open_slip_lines(lines)
            if len(open_legs) > len(parsed_legs):
                parsed_legs = open_legs

        if len(parsed_legs) < 3 and leg_blocks:
            from .fanduel import _parse_leg_block

            block_legs = [_parse_leg_block(b) for b in leg_blocks]
            block_legs = [lg for lg in block_legs if lg.selection or lg.bet_type]
            if len(block_legs) > len(parsed_legs):
                parsed_legs = block_legs

        slip.legs = []
        for lg in parsed_legs:
            if not (lg.selection or lg.bet_type):
                continue
            if shared_event and not lg.event:
                lg.event = shared_event
            if shared_time and not lg.game_time:
                lg.game_time = shared_time
            lg.description = build_description(lg)
            slip.legs.append(lg)

        if SGP_HEADER_RE.search(raw_text) and slip.legs:
            slip.parlay_type = f"{len(slip.legs)} Leg Same Game Parlay"

        m_pick = re.search(r"(\d+)\s*pick\s+parlay", raw_text, re.I)
        if m_pick and slip.legs:
            count = int(m_pick.group(1))
            if "same game" in slip.parlay_type.lower():
                slip.parlay_type = f"{count} Leg Same Game Parlay"
            else:
                slip.parlay_type = f"{count} Pick Parlay"

        if not slip.legs:
            uncertain.append("legs")

        leg_confs = [lg.confidence for lg in slip.legs] or [0.0]
        field_penalty = 0.05 * len(uncertain)
        slip.confidence = max(0.0, min(1.0, sum(leg_confs) / len(leg_confs) - field_penalty))
        slip.uncertain_fields = uncertain
        return slip
