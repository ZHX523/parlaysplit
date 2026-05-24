"""Tesseract text extraction with line grouping."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytesseract
from PIL import Image

try:
    from pytesseract import TesseractNotFoundError
except ImportError:
    TesseractNotFoundError = RuntimeError  # type: ignore[misc, assignment]


def _configure_tesseract() -> None:
    import os
    import shutil
    from pathlib import Path

    candidates: list[str] = []
    try:
        from django.conf import settings

        cmd = getattr(settings, "TESSERACT_CMD", "") or ""
        if cmd:
            candidates.append(cmd)
    except Exception:
        pass

    on_path = shutil.which("tesseract")
    if on_path:
        candidates.append(on_path)

    if os.name == "nt":
        candidates.extend(
            [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
        )

    for path in candidates:
        if path and Path(path).is_file():
            pytesseract.pytesseract.tesseract_cmd = path
            return


_configure_tesseract()


@dataclass(frozen=True)
class OCRWord:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass(frozen=True)
class OCRLine:
    text: str
    words: tuple[OCRWord, ...]
    top: int
    left: int
    conf: float

    @property
    def right(self) -> int:
        if not self.words:
            return self.left
        return max(w.right for w in self.words)


def _line_confidence(words: list[OCRWord]) -> float:
    if not words:
        return 0.0
    return sum(w.conf for w in words) / len(words)


def extract_words(processed: np.ndarray) -> list[OCRWord]:
    pil = Image.fromarray(processed)
    data = pytesseract.image_to_data(pil, output_type=pytesseract.Output.DICT, config="--psm 6")
    words: list[OCRWord] = []
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue
        words.append(
            OCRWord(
                text=text,
                left=int(data["left"][i]),
                top=int(data["top"][i]),
                width=int(data["width"][i]),
                height=int(data["height"][i]),
                conf=conf / 100.0,
            )
        )
    return words


def group_words_into_lines(words: list[OCRWord], y_tolerance: int = 14) -> list[OCRLine]:
    if not words:
        return []

    sorted_words = sorted(words, key=lambda w: (w.top, w.left))
    lines: list[list[OCRWord]] = []
    current: list[OCRWord] = []
    current_top: int | None = None

    for word in sorted_words:
        if current_top is None or abs(word.top - current_top) <= y_tolerance:
            current.append(word)
            if current_top is None:
                current_top = word.top
            else:
                current_top = int(sum(w.top for w in current) / len(current))
        else:
            lines.append(sorted(current, key=lambda w: w.left))
            current = [word]
            current_top = word.top
    if current:
        lines.append(sorted(current, key=lambda w: w.left))

    result: list[OCRLine] = []
    for group in lines:
        text = " ".join(w.text for w in group).strip()
        if len(text) < 2:
            continue
        result.append(
            OCRLine(
                text=text,
                words=tuple(group),
                top=min(w.top for w in group),
                left=min(w.left for w in group),
                conf=_line_confidence(group),
            )
        )
    return sorted(result, key=lambda ln: ln.top)


def extract_lines_from_image(processed) -> list[OCRLine]:
    """Full pipeline: numpy image -> grouped OCR lines."""
    words = extract_words(processed)
    return group_words_into_lines(words)


def extract_lines_from_bytes(image_bytes: bytes) -> list[OCRLine]:
    """Run OCR on grayscale and color-preserving passes; keep richer result."""
    from .line_merge import pick_best_lines
    from .preprocess import preprocess_color_preserve, preprocess_for_ocr

    gray = preprocess_for_ocr(image_bytes)
    color = preprocess_color_preserve(image_bytes)
    return pick_best_lines(
        extract_lines_from_image(gray),
        extract_lines_from_image(color),
    )


def extract_plain_text(processed) -> str:
    pil = Image.fromarray(processed)
    return pytesseract.image_to_string(pil, config="--psm 6 -c preserve_interword_spaces=1").strip()
