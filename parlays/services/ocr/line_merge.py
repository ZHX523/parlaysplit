"""Merge and select OCR line results from multiple passes."""

from __future__ import annotations

from .extract import OCRLine


def _line_score(lines: list[OCRLine]) -> int:
    return sum(len(ln.text) for ln in lines) + 15 * len(lines)


def pick_best_lines(*candidates: list[OCRLine]) -> list[OCRLine]:
    if not candidates:
        return []
    return max(candidates, key=_line_score)
