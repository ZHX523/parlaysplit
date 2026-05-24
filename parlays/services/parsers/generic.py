"""Generic bet slip parser for unknown or mixed sportsbook layouts."""

from __future__ import annotations

import re

from parlays.services.ocr.extract import OCRLine
from parlays.services.ocr.normalize import clean_text
from parlays.services.ocr.segmentation import (
    HeaderRegion,
    LegBlock,
    SELECTION_START_RE,
    SGP_HEADER_RE,
)

from .base import BaseSlipParser, ParsedLeg, ParsedSlip
from .parser_common import (
    build_description,
    extract_parlay_header,
    extract_shared_event,
    extract_wager_and_payout,
    map_leg_type,
    odds_american_int,
)

_THRESHOLD_RE = re.compile(r"(?:^|[^\d])(\d{1,4})\+\s*$")
_MONEYLINE_RE = re.compile(r"^moneyline\b", re.I)
_PROP_RE = re.compile(
    r"(passing|rushing|receiving|touchdown|yards|points|rebounds|assists|"
    r"over/under|spread|total|moneyline)",
    re.I,
)
_SKIP_RE = re.compile(
    r"^(place\s*bet|total\s*payout|payout:|clear\s*all|reward|view\s*all|"
    r"cash\s*out|share\s*bet|reuse)",
    re.I,
)


def _clean(text: str) -> str:
    return clean_text(text)


def _parse_threshold_lines(lines: list[OCRLine]) -> list[ParsedLeg]:
    legs: list[ParsedLeg] = []
    i = 0
    while i < len(lines):
        t = _clean(lines[i].text)
        if _SKIP_RE.search(t) or not t:
            i += 1
            continue
        th = _THRESHOLD_RE.search(t)
        if not th:
            i += 1
            continue
        line_val = f"{th.group(1)}+"
        stat_parts: list[str] = []
        i += 1
        while i < len(lines):
            nxt = _clean(lines[i].text)
            if _THRESHOLD_RE.search(nxt) or _SKIP_RE.search(nxt):
                break
            if _MONEYLINE_RE.match(nxt):
                break
            stat_parts.append(nxt)
            i += 1
            if stat_parts and _PROP_RE.search(" ".join(stat_parts)):
                break
        stat = " ".join(stat_parts).strip()
        if stat:
            leg = ParsedLeg(confidence=0.6)
            leg.line = line_val
            m = re.match(r"^(.+?)\s+(.+)$", stat)
            if m and _PROP_RE.search(m.group(2)):
                leg.selection = m.group(1).strip()
                leg.bet_type = m.group(2).upper()
            else:
                leg.selection = stat
                leg.bet_type = "PROP"
            leg.leg_type = map_leg_type(leg.bet_type, leg.selection)
            leg.description = build_description(leg)
            legs.append(leg)
    return legs


class GenericParser(BaseSlipParser):
    sportsbook_name = "Sportsbook"

    @classmethod
    def detect(cls, lines: list[OCRLine], raw_text: str) -> bool:
        return False

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
        if header:
            parlay_type = header.parlay_type or parlay_type
            total_odds = header.total_odds_display or total_odds

        slip.parlay_type = parlay_type
        slip.total_odds = total_odds
        slip.total_odds_american = odds_american_int(total_odds)
        if not slip.total_odds:
            uncertain.append("total_odds")

        slip.wager_amount, slip.potential_payout = extract_wager_and_payout(lines, raw_text)
        shared_event, shared_time = extract_shared_event(lines)

        from .open_slip import (
            merge_legs_with_summary,
            parse_comma_summary_legs,
            parse_open_slip_lines,
        )

        parsed_legs = parse_open_slip_lines(lines)
        if len(parsed_legs) < 2:
            parsed_legs = _parse_threshold_lines(lines)
        summary_legs = parse_comma_summary_legs(lines)
        if summary_legs:
            parsed_legs = merge_legs_with_summary(parsed_legs, summary_legs)

        if len(parsed_legs) < 2:
            from .fanduel import _parse_leg_block

            block_legs = [_parse_leg_block(b) for b in leg_blocks]
            block_legs = [lg for lg in block_legs if lg.selection or lg.bet_type]
            if len(block_legs) >= len(parsed_legs):
                parsed_legs = block_legs

        if len(parsed_legs) < 2:
            for ln in lines:
                if SELECTION_START_RE.match(ln.text):
                    sel = SELECTION_START_RE.match(ln.text)
                    leg = ParsedLeg(confidence=0.5)
                    leg.selection = sel.group(1).title() if sel else ""
                    leg.bet_type = "OVER/UNDER"
                    leg.leg_type = "total_points"
                    leg.description = build_description(leg)
                    parsed_legs.append(leg)

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

        if not slip.legs:
            uncertain.append("legs")

        leg_confs = [lg.confidence for lg in slip.legs] or [0.0]
        slip.confidence = max(0.0, min(1.0, sum(leg_confs) / len(leg_confs) - 0.05 * len(uncertain)))
        slip.uncertain_fields = uncertain
        return slip
