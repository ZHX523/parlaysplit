"""Tests for lightweight OCR correction logging."""

from decimal import Decimal

from django.http import QueryDict
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from parlays.models import OCRScanFeedback, OCRUpload, OCRUploadStatus, Parlay, ParlayLeg
from parlays.services.ocr.feedback import (
    build_compact_corrections,
    record_ocr_scan_feedback,
    schedule_ocr_scan_feedback,
)


class OCRFeedbackCompactTests(SimpleTestCase):
    def test_compact_corrections_only_deltas(self):
        predicted = {
            "odds_american": "335",
            "wager_amount": "10.00",
            "legs": [{"t": "moneyline", "d": "IND Colts - MONEYLINE"}],
        }
        submitted = {
            "odds_american": "750",
            "wager_amount": "10.00",
            "legs": [
                {"t": "moneyline", "d": "IND Colts - MONEYLINE"},
                {"t": "player_prop", "d": "Fox - 20+ POINTS"},
            ],
        }
        corrections, was_edited = build_compact_corrections(predicted, submitted)
        self.assertTrue(was_edited)
        self.assertEqual(corrections["f"]["odds_american"], ["335", "750"])
        self.assertEqual(corrections["f"]["leg_count"], [1, 2])
        self.assertEqual(len(corrections["legs"]), 1)

    def test_no_corrections_when_unchanged(self):
        legs = [{"t": "moneyline", "d": "Team A"}]
        predicted = {"odds_american": "500", "wager_amount": "25.00", "legs": legs}
        submitted = {"odds_american": "500", "wager_amount": "25.00", "legs": legs}
        corrections, was_edited = build_compact_corrections(predicted, submitted)
        self.assertFalse(was_edited)
        self.assertEqual(corrections, {})


class OCRFeedbackModelTests(TestCase):
    @override_settings(OCR_FEEDBACK_STORE_UNCHANGED=False)
    def test_skips_row_when_unchanged(self):
        upload = OCRUpload.objects.create(
            image="ocr/test.png",
            status=OCRUploadStatus.COMPLETED,
            parsed_data={
                "sportsbook": "FanDuel",
                "odds_american": 500,
                "wager_amount": "25.00",
                "legs": [
                    {
                        "leg_type": "moneyline",
                        "description": "Team A",
                        "selection": "Team A",
                        "bet_type": "MONEYLINE",
                    }
                ],
            },
        )
        parlay = Parlay.objects.create(
            creator_nickname="Host",
            odds_american=500,
            wager_amount=Decimal("25.00"),
            potential_payout=Decimal("100.00"),
            split_offered_percent=Decimal("100"),
        )
        ParlayLeg.objects.create(
            parlay=parlay,
            leg_type="moneyline",
            description="Team A",
            sort_order=0,
        )
        post = {
            "odds_american": "500",
            "wager_amount": "25.00",
            "leg_type": ["moneyline"],
            "leg_description": ["Team A - MONEYLINE"],
        }
        record_ocr_scan_feedback(str(upload.id), str(parlay.id), post)
        self.assertFalse(OCRScanFeedback.objects.filter(ocr_upload=upload).exists())

    def test_records_compact_row_when_edited(self):
        upload = OCRUpload.objects.create(
            image="ocr/test.png",
            status=OCRUploadStatus.COMPLETED,
            parsed_data={
                "sportsbook": "DraftKings",
                "odds_american": 335,
                "wager_amount": "10.00",
                "legs": [
                    {
                        "leg_type": "moneyline",
                        "description": "IND Colts - MONEYLINE",
                        "selection": "IND Colts",
                        "bet_type": "MONEYLINE",
                    }
                ],
            },
        )
        parlay = Parlay.objects.create(
            creator_nickname="Host",
            odds_american=750,
            wager_amount=Decimal("100.00"),
            potential_payout=Decimal("850.00"),
            split_offered_percent=Decimal("100"),
        )
        ParlayLeg.objects.create(
            parlay=parlay,
            leg_type="moneyline",
            description="IND Colts - MONEYLINE",
            sort_order=0,
        )
        post = {
            "odds_american": "750",
            "wager_amount": "100.00",
            "leg_type": ["moneyline"],
            "leg_description": ["IND Colts - MONEYLINE"],
        }
        record_ocr_scan_feedback(str(upload.id), str(parlay.id), post)
        fb = OCRScanFeedback.objects.get(ocr_upload=upload)
        self.assertTrue(fb.was_edited)
        self.assertEqual(fb.corrections["f"]["odds_american"], ["335", "750"])
        self.assertNotIn("predicted_snapshot", dir(fb))


class OCRFeedbackScheduleTests(TransactionTestCase):
    def test_schedule_on_commit(self):
        upload = OCRUpload.objects.create(
            image="ocr/test2.png",
            status=OCRUploadStatus.COMPLETED,
            parsed_data={"odds_american": 100, "legs": []},
        )
        parlay = Parlay.objects.create(
            creator_nickname="Host",
            odds_american=200,
            wager_amount=Decimal("10.00"),
            potential_payout=Decimal("20.00"),
            split_offered_percent=Decimal("100"),
        )
        post = QueryDict(mutable=True)
        post["odds_american"] = "200"
        post["wager_amount"] = "10.00"
        post.setlist("leg_type", ["moneyline"])
        post.setlist("leg_description", ["Team B"])
        schedule_ocr_scan_feedback(str(upload.id), str(parlay.id), post)
        fb = OCRScanFeedback.objects.filter(ocr_upload=upload).first()
        self.assertIsNotNone(fb)
        self.assertTrue(fb.was_edited)
