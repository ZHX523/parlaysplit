"""Tests for FanDuel parlay OCR parsing (no Tesseract required)."""

from django.test import SimpleTestCase

from parlays.services.ocr.extract import OCRLine
from parlays.services.ocr.segmentation import extract_header, segment_leg_blocks
from parlays.services.parsers.fanduel import FanDuelParser
from parlays.services.parsers.registry import parse_slip


def _line(text: str, top: int) -> OCRLine:
    return OCRLine(text=text, words=(), top=top, left=0, conf=0.9)


class FanDuelParserTests(SimpleTestCase):
    def _sample_lines(self) -> list[OCRLine]:
        raw = [
            ("7 Leg Parlay +4155", 0),
            ("Under -160", 40),
            ("2ND INNING OVER/UNDER 0.5 RUNS", 60),
            ("Pittsburgh Pirates @ Toronto Blue Jays 12:16PM ET", 80),
            ("Under -144", 120),
            ("2ND INNING OVER/UNDER 0.5 RUNS", 140),
            ("Detroit Tigers @ Baltimore Orioles 12:36PM ET", 160),
            ("Under -170", 200),
            ("2ND INNING OVER/UNDER 0.5 RUNS", 220),
            ("Minnesota Twins @ Boston Red Sox 1:36PM ET", 240),
        ]
        return [_line(t, y) for t, y in raw]

    def _sgp_sample_lines(self) -> list[OCRLine]:
        """Lines from a FanDuel Same Game Parlay slip (OCR-shaped)."""
        raw = [
            ("Same Game Parlay +860", 42),
            (
                "San Antonio Spurs Moneyline, Victor Wembanyama To Score 20+ Points, "
                "De'Aaron Fox To Score 20+ Points, Chet Holmgren Under...",
                100,
            ),
            ("Oklahoma City Thunder @ San Antonio Spurs 8:10PM ET", 182),
            ("San Antonio Spurs", 250),
            ("MONEYLINE", 299),
            ("Victor Wembanyama", 356),
            ("TO SCORE 20+ POINTS", 395),
            ("De'Aaron Fox", 467),
            ("TO SCORE 20+ POINTS", 514),
            ("Chet Holmgren Under 7.5", 573),
            ("CHET HOLMGREN REBOUNDS", 624),
            ("$1.00 $9.60", 687),
            ("TOTAL WAGER TOTAL PAYOUT", 722),
        ]
        return [_line(t, y) for t, y in raw]

    def test_detect_fanduel_parlay(self):
        lines = self._sample_lines()
        raw = "\n".join(ln.text for ln in lines)
        self.assertTrue(FanDuelParser.detect(lines, raw))

    def test_parse_header_and_first_leg(self):
        lines = self._sample_lines()
        raw = "\n".join(ln.text for ln in lines)
        slip = parse_slip(lines, raw)
        data = slip.to_legacy_dict()
        self.assertEqual(data["sportsbook"], "FanDuel")
        self.assertEqual(data["parlay_type"], "7 Leg Parlay")
        self.assertEqual(data["total_odds"], "+4155")
        self.assertEqual(data["odds_american"], 4155)
        self.assertGreaterEqual(len(data["legs"]), 1)
        leg0 = data["legs"][0]
        self.assertEqual(leg0["selection"], "Under")
        self.assertIn("2ND INNING", leg0["bet_type"])
        self.assertEqual(leg0["line"], "0.5")
        self.assertEqual(leg0["odds"], "-160")
        self.assertIn("@", leg0["event"])

    def test_segment_leg_blocks(self):
        lines = self._sample_lines()
        header = extract_header(lines)
        blocks = segment_leg_blocks(lines, header)
        self.assertGreaterEqual(len(blocks), 3)

    def test_sgp_summary_garbled_ocr(self):
        """Comma summary with OCR typos (Scor, Under...) still yields 4 legs."""
        lines = [
            _line("Same Game Parlay +860", 42),
            _line(
                "San Antonio Spurs Moneyline, Victor Wembanyama Ta Score 20%",
                100,
            ),
            _line(
                "Points, De'Aaron Fox To Scor 20+ Points, Chet Holmgren Under... A",
                123,
            ),
            _line("Oklahoma City Thunder @ San Antonio Spurs 8:10PM ET", 182),
            _line("San Antonio Spurs", 250),
            _line("MONEYLINE", 299),
            _line("De'Aaron Fox", 467),
            _line("TO SCORE 20+ POINTS", 514),
            _line("Chet Holmgren Under 7.5", 573),
            _line("REBOUNDS", 624),
        ]
        raw = "\n".join(ln.text for ln in lines)
        slip = parse_slip(lines, raw)
        data = slip.to_legacy_dict()
        self.assertEqual(len(data["legs"]), 4)
        self.assertIn("4 Leg", data["parlay_type"])
        names = [leg["selection"] for leg in data["legs"]]
        self.assertIn("Victor Wembanyama", names)
        self.assertTrue(any("Chet Holmgren" in n for n in names))

    def test_sgp_four_legs(self):
        lines = self._sgp_sample_lines()
        raw = "\n".join(ln.text for ln in lines)
        slip = parse_slip(lines, raw)
        data = slip.to_legacy_dict()
        self.assertEqual(data["total_odds"], "+860")
        self.assertEqual(data["odds_american"], 860)
        self.assertEqual(data["wager_amount"], "1.00")
        self.assertEqual(data["potential_payout"], "9.60")
        self.assertEqual(len(data["legs"]), 4)
        self.assertEqual(data["legs"][0]["selection"], "San Antonio Spurs")
        self.assertEqual(data["legs"][0]["bet_type"], "MONEYLINE")
        self.assertEqual(data["legs"][1]["selection"], "Victor Wembanyama")
        from parlays.forms import legs_initial_from_ocr

        rows = legs_initial_from_ocr(data)
        self.assertEqual(len(rows), 4)
        self.assertIn("Victor Wembanyama", rows[1]["description"])
        self.assertIn("SCORE", data["legs"][1]["bet_type"])
        self.assertEqual(data["legs"][2]["selection"], "De'Aaron Fox")
        self.assertIn("Under 7.5", data["legs"][3]["selection"])
        self.assertIn("REBOUND", data["legs"][3]["bet_type"])
