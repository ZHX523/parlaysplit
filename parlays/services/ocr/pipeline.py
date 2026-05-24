"""End-to-end OCR pipeline for bet slip screenshots."""

from __future__ import annotations

import logging

from pytesseract import TesseractNotFoundError

from parlays.services.parsers.registry import parse_slip

from .extract import extract_lines_from_bytes, extract_plain_text
from .normalize import sanitize_parsed_result
from .preprocess import preprocess_color_preserve, preprocess_for_ocr

logger = logging.getLogger(__name__)


class OCRPipeline:
    """Run preprocessing, Tesseract, segmentation, and sportsbook parsing."""

    @staticmethod
    def run(image_bytes: bytes) -> dict:
        if not image_bytes:
            return {"error": "Empty image", "confidence": 0.0, "uncertain_fields": ["image"]}

        try:
            processed = preprocess_for_ocr(image_bytes)
            lines = extract_lines_from_bytes(image_bytes)
        except TesseractNotFoundError:
            return {
                "error": (
                    "Tesseract OCR is not installed or not on PATH. "
                    "Install Tesseract and set TESSERACT_CMD if needed."
                ),
                "confidence": 0.0,
                "uncertain_fields": ["tesseract"],
                "schema_version": 2,
            }

        raw_primary = extract_plain_text(processed)
        raw_color = extract_plain_text(preprocess_color_preserve(image_bytes))
        raw_text = raw_primary if len(raw_primary) >= len(raw_color) else raw_color

        if not raw_text and not lines:
            return {
                "error": "No text detected in image.",
                "confidence": 0.0,
                "uncertain_fields": ["image"],
                "schema_version": 2,
            }

        if not lines and raw_text:
            from .extract import group_words_into_lines, extract_words

            words = extract_words(processed)
            lines = group_words_into_lines(words)
            if not lines:
                from .extract import OCRLine

                lines = [
                    OCRLine(text=ln.strip(), words=(), top=i * 20, left=0, conf=0.5)
                    for i, ln in enumerate(raw_text.splitlines())
                    if ln.strip()
                ]

        try:
            parsed_slip = parse_slip(lines, raw_text)
            result = sanitize_parsed_result(parsed_slip.to_legacy_dict())
            result["raw_text"] = raw_text
            if parsed_slip.confidence < 0.35:
                result.setdefault("uncertain_fields", []).append("low_confidence")
            return result
        except Exception as exc:
            logger.exception("OCR parse failed")
            return {
                "error": str(exc),
                "confidence": 0.0,
                "uncertain_fields": ["parse"],
                "raw_text": raw_text,
                "schema_version": 2,
            }


def process_image_bytes(image_bytes: bytes) -> dict:
    return OCRPipeline.run(image_bytes)
