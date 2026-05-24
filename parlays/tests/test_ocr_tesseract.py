"""Live Tesseract integration tests (skipped when OCR binary unavailable)."""

from io import BytesIO

from django.test import SimpleTestCase
from PIL import Image, ImageDraw, ImageFont
from pytesseract import TesseractNotFoundError

from parlays.services.ocr import process_image_bytes
from parlays.services.ocr.extract import _configure_tesseract


def _tesseract_available() -> bool:
    try:
        _configure_tesseract()
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except TesseractNotFoundError:
        return False


def _synthetic_fanduel_png() -> bytes:
    w, h = 400, 520
    img = Image.new("RGB", (w, h), (15, 35, 80))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, w - 20, 70], fill=(20, 100, 200))
    try:
        font_lg = ImageFont.truetype("arial.ttf", 22)
        font_sm = ImageFont.truetype("arial.ttf", 14)
        font_md = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font_lg = font_sm = font_md = ImageFont.load_default()
    draw.text((30, 32), "7 Leg Parlay", fill="white", font=font_lg)
    draw.text((280, 32), "+4155", fill="white", font=font_lg)
    draw.rectangle([20, 80, w - 20, h - 20], fill="white")
    y = 95
    legs = [
        ("Under", "-160", "2ND INNING OVER/UNDER 0.5 RUNS", "Pittsburgh Pirates @ Toronto Blue Jays", "12:16PM ET"),
        ("Under", "-144", "2ND INNING OVER/UNDER 0.5 RUNS", "Detroit Tigers @ Baltimore Orioles", "12:36PM ET"),
    ]
    for sel, odds, bt, ev, tm in legs:
        draw.text((35, y), sel, fill=(20, 100, 200), font=font_md)
        draw.text((300, y), odds, fill="black", font=font_md)
        y += 28
        draw.text((35, y), bt, fill=(120, 120, 120), font=font_sm)
        y += 22
        draw.text((35, y), ev, fill=(60, 60, 60), font=font_sm)
        draw.text((250, y), tm, fill=(150, 150, 150), font=font_sm)
        y += 40
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TesseractIntegrationTests(SimpleTestCase):
    def setUp(self):
        if not _tesseract_available():
            self.skipTest("Tesseract not installed")

    def test_process_synthetic_slip(self):
        result = process_image_bytes(_synthetic_fanduel_png())
        self.assertIsNone(result.get("error"))
        self.assertEqual(result.get("sportsbook"), "FanDuel")
        self.assertIn("7", result.get("parlay_type", ""))
        self.assertIn("leg", result.get("parlay_type", "").lower())
        self.assertGreaterEqual(len(result.get("legs") or []), 1)
        leg0 = result["legs"][0]
        self.assertEqual(leg0.get("selection"), "Under")
        self.assertTrue(leg0.get("odds"))
