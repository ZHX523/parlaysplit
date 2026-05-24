"""Tests for DraftKings bet slip OCR parsing (no Tesseract required)."""

from django.test import SimpleTestCase

from parlays.services.ocr.extract import OCRLine
from parlays.services.parsers.draftkings import DraftKingsParser, parse_draftkings_mobile_lines
from parlays.services.parsers.registry import detect_sportsbook, parse_slip


def _line(text: str, top: int) -> OCRLine:
    return OCRLine(text=text, words=(), top=top, left=0, conf=0.9)


class DraftKingsParserTests(SimpleTestCase):
    def _dk_sample_lines(self) -> list[OCRLine]:
        raw = [
            ("SAME GAME PARLAY", 0),
            ("7 Pick Parlay +335", 40),
            ("ATL Falcons @ IND Colts Sun 8:30 AM", 80),
            ("IND Colts", 120),
            ("Moneyline", 140),
            ("200+", 200),
            ("Daniel Jones Passing Yards", 220),
            ("100+", 260),
            ("Jonathan Taylor Rushing + Receiving", 280),
            ("Yards", 300),
            ("25+", 320),
            ("Michael Pittman Jr. Receiving Yards", 340),
            ("Michael Penix Jr. Passing", 380),
            ("Touchdowns", 400),
            ("15+", 420),
            ("Alec Pierce Receiving Yards", 440),
            ("80+", 480),
            ("Bijan Robinson Rushing + Receiving", 500),
            ("Yards", 520),
            ("Place Bet $10.00", 600),
            ("Total Payout: $43.50", 620),
        ]
        return [_line(t, y) for t, y in raw]

    def test_detect_draftkings(self):
        lines = self._dk_sample_lines()
        raw = "\n".join(ln.text for ln in lines)
        self.assertTrue(DraftKingsParser.detect(lines, raw))
        self.assertEqual(detect_sportsbook(lines, raw), "DraftKings")

    def test_parse_seven_legs(self):
        lines = self._dk_sample_lines()
        raw = "\n".join(ln.text for ln in lines)
        slip = parse_slip(lines, raw)
        data = slip.to_legacy_dict()
        self.assertEqual(data["sportsbook"], "DraftKings")
        self.assertEqual(data["total_odds"], "+335")
        self.assertEqual(data["odds_american"], 335)
        self.assertEqual(data["wager_amount"], "10.00")
        self.assertEqual(data["potential_payout"], "43.50")
        self.assertGreaterEqual(len(data["legs"]), 6)
        selections = [leg["selection"] for leg in data["legs"]]
        self.assertIn("IND Colts", selections)
        self.assertTrue(
            any("Daniel Jones" in s for s in selections),
        )
        self.assertTrue(
            any("Bijan Robinson" in s for s in selections),
        )

    def test_parse_draftkings_lines_moneyline_and_prop(self):
        lines = self._dk_sample_lines()
        legs = parse_draftkings_mobile_lines(lines)
        self.assertGreaterEqual(len(legs), 6)
        self.assertEqual(legs[0].bet_type, "MONEYLINE")
        self.assertIn("200+", legs[1].line)
