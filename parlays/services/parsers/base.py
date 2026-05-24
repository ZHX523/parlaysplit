"""Parser abstraction for sportsbook bet slip OCR."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from parlays.services.ocr.extract import OCRLine
from parlays.services.ocr.segmentation import HeaderRegion, LegBlock


@dataclass
class ParsedLeg:
    selection: str = ""
    bet_type: str = ""
    line: str = ""
    odds: str = ""
    event: str = ""
    game_time: str = ""
    leg_type: str = "moneyline"
    description: str = ""
    confidence: float = 0.0
    uncertain_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection": self.selection,
            "bet_type": self.bet_type,
            "line": self.line,
            "odds": self.odds,
            "event": self.event,
            "game_time": self.game_time,
            "leg_type": self.leg_type,
            "description": self.description,
            "confidence": round(self.confidence, 3),
            "uncertain_fields": list(self.uncertain_fields),
        }


@dataclass
class ParsedSlip:
    sportsbook: str
    parlay_type: str = ""
    total_odds: str = ""
    total_odds_american: int | None = None
    wager_amount: str = ""
    potential_payout: str = ""
    legs: list[ParsedLeg] = field(default_factory=list)
    confidence: float = 0.0
    uncertain_fields: list[str] = field(default_factory=list)
    raw_text: str = ""

    def to_legacy_dict(self) -> dict[str, Any]:
        """Shape compatible with existing form prefill and OCRUpload.parsed_data."""
        leg_lines = [leg.description for leg in self.legs if leg.description]
        return {
            "schema_version": 2,
            "sportsbook": self.sportsbook,
            "parlay_type": self.parlay_type,
            "total_odds": self.total_odds,
            "odds_american": self.total_odds_american,
            "wager_amount": self.wager_amount,
            "potential_payout": self.potential_payout,
            "leg_descriptions": "\n".join(leg_lines),
            "legs": [leg.to_dict() for leg in self.legs],
            "confidence": round(self.confidence, 3),
            "uncertain_fields": list(self.uncertain_fields),
            "raw_line_count": len(self.raw_text.splitlines()) if self.raw_text else 0,
        }


class BaseSlipParser(ABC):
    sportsbook_name: str = "Unknown"

    @abstractmethod
    def parse(
        self,
        lines: list[OCRLine],
        header: HeaderRegion | None,
        leg_blocks: list[LegBlock],
        raw_text: str,
    ) -> ParsedSlip:
        raise NotImplementedError
