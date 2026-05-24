"""Tests for open bet slip parsing (DraftKings / FanDuel active slips)."""

from django.test import SimpleTestCase

from parlays.services.ocr.extract import OCRLine
from parlays.services.parsers.draftkings import DraftKingsParser
from parlays.services.parsers.fanduel import FanDuelParser
from parlays.services.parsers.registry import parse_slip


def _line(text: str, top: int) -> OCRLine:
    return OCRLine(text=text, words=(), top=top, left=0, conf=0.9)


class OpenSlipParserTests(SimpleTestCase):
    def _dk_open_six_pick_lines(self) -> list[OCRLine]:
        raw = [
            ("6 Pick Parlay | +1300                             Open", 0),
            (
                "De'Aaron Fox, Victor Wembanyama, De'Aaron Fox, Stephon Castle, Julian "
                "Champagnie, OKC Thunder",
                40,
            ),
            ("Wager: $100.00 | To Pay: $1,400.00", 80),
            ("De'Aaron Fox", 120),
            ("Chet Holmgren v De'Aaron Fox - Points Moneyline", 140),
            ("Victor Wembanyama", 180),
            ("Jalen Williams v Victor Wembanyama - Points Moneyline", 200),
            ("De'Aaron Fox", 240),
            ("Jalen Williams v De'Aaron Fox - Points Moneyline", 260),
            ("Stephon Castle", 300),
            ("Jalen Williams v Stephon Castle - Rebounds Moneyline", 320),
            ("Julian Champagnie", 360),
            ("Jalen Williams v Julian Champagnie - Rebounds Moneyline", 380),
            ("OKC Thunder", 420),
            ("Moneyline", 440),
        ]
        return [_line(t, y) for t, y in raw]

    def _fanduel_five_pick_sgp_lines(self) -> list[OCRLine]:
        raw = [
            ("5 Pick Parlay | +2100 (#2625)                           Open", 0),
            ("Yes, 20+, 2+, 25+, 25+", 40),
            ("Yes", 100),
            ("Josh Hart Double-Double", 120),
            ("20+", 140),
            ("Evan Mobley Points + Rebounds", 160),
            ("2+", 200),
            ("Mikal Bridges Three Pointers Made", 220),
            ("25+", 260),
            ("Donovan Mitchell Points", 280),
            ("25+", 300),
            ("Jalen Brunson Points", 320),
            ("Wager: $5.00", 400),
            ("To Pay: $1,961.90", 420),
        ]
        return [_line(t, y) for t, y in raw]

    def test_dk_open_six_pick(self):
        lines = self._dk_open_six_pick_lines()
        raw = "\n".join(ln.text for ln in lines)
        self.assertTrue(DraftKingsParser.detect(lines, raw))
        data = parse_slip(lines, raw).to_legacy_dict()
        self.assertEqual(data["sportsbook"], "DraftKings")
        self.assertEqual(data["total_odds"], "+1300")
        self.assertEqual(data["wager_amount"], "100.00")
        self.assertEqual(data["potential_payout"], "1400.00")
        self.assertEqual(len(data["legs"]), 6)
        self.assertIn("POINTS", data["legs"][0]["bet_type"].upper())

    def test_fanduel_five_pick_sgp_open(self):
        lines = self._fanduel_five_pick_sgp_lines()
        raw = "\n".join(ln.text for ln in lines)
        self.assertTrue(FanDuelParser.detect(lines, raw))
        data = parse_slip(lines, raw).to_legacy_dict()
        self.assertEqual(data["sportsbook"], "FanDuel")
        self.assertGreaterEqual(len(data["legs"]), 5)
        self.assertEqual(data["wager_amount"], "5.00")
        self.assertEqual(data["potential_payout"], "1961.90")
