"""Tests for post-OCR readability sanitization."""

from django.test import SimpleTestCase

from parlays.services.ocr.normalize import sanitize_parsed_result, sanitize_readability


class OCRSanitizeTests(SimpleTestCase):
    def test_sanitize_readability(self):
        self.assertEqual(
            sanitize_readability("oO eo De'Aaron Fox - Points Moneyline!"),
            "oO eo DeAaron Fox - Points Moneyline",
        )
        self.assertEqual(sanitize_readability("  20+  @ CLE  "), "20+ CLE")
        self.assertEqual(sanitize_readability("Over/Under 0.5 +119"), "Over/Under 0.5 +119")

    def test_sanitize_parsed_result(self):
        result = {
            "sportsbook": "Draft@Kings",
            "parlay_type": "6 Pick Parlay!!!",
            "legs": [
                {
                    "selection": "(S> Chet Holmgren",
                    "bet_type": "PLAYER REBOUNDS~",
                    "description": "Chet Holmgren · REBOUNDS #7.5",
                    "line": "7.5",
                }
            ],
            "leg_descriptions": "Chet Holmgren · REBOUNDS #7.5",
        }
        out = sanitize_parsed_result(result)
        self.assertEqual(out["sportsbook"], "DraftKings")
        self.assertNotIn("@", out["legs"][0]["selection"])
        self.assertNotIn(">", out["legs"][0]["selection"])
        self.assertNotIn("~", out["legs"][0]["bet_type"])
        self.assertNotIn("#", out["legs"][0]["description"])
