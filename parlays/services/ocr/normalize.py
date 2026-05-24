"""Text normalization for OCR artifacts."""

from __future__ import annotations

import re

OCR_FIXES = (
    (re.compile(r"\bl\s*eg\b", re.I), "leg"),
    (re.compile(r"\bO\s*ver\b", re.I), "Over"),
    (re.compile(r"\bUn\s*der\b", re.I), "Under"),
    (re.compile(r"(\d),(\d)"), r"\1.\2"),
    (re.compile(r"(\d)#(\s*points)", re.I), r"\1+\2"),
    (re.compile(r"San-Antonio", re.I), "San Antonio"),
    (re.compile(r"\s+"), " "),
)


def clean_text(value: str) -> str:
    text = (value or "").strip()
    for pattern, repl in OCR_FIXES:
        text = pattern.sub(repl, text)
    return text.strip()


def normalize_odds_display(value: str) -> str:
    text = clean_text(value)
    if not text:
        return ""
    m = re.search(r"([+-]?\d{2,5})", text)
    if not m:
        return text
    num = m.group(1)
    if not num.startswith(("+", "-")):
        return f"+{num}"
    return num


def normalize_time(value: str) -> str:
    text = clean_text(value).upper()
    text = text.replace(".", "")
    text = re.sub(r"\s+", " ", text)
    m = re.match(r"(\d{1,2}):?(\d{2})\s*([AP]M)\s*ET", text)
    if m:
        return f"{m.group(1)}:{m.group(2)}{m.group(3)} ET"
    return text


_READABILITY_KEEP_RE = re.compile(r"[^A-Za-z0-9+\-/. ]")


def sanitize_readability(value: str) -> str:
    """Strip OCR junk; keep letters, numbers, spaces, and + - / ."""
    text = clean_text(value or "")
    text = _READABILITY_KEEP_RE.sub("", text)
    return re.sub(r" +", " ", text).strip()


def sanitize_parsed_result(result: dict) -> dict:
    """Apply readability sanitization to user-facing OCR fields after parsing."""
    if not result or result.get("error"):
        return result

    for key in ("sportsbook", "parlay_type", "total_odds", "wager_amount", "potential_payout"):
        if key in result and isinstance(result[key], str):
            result[key] = sanitize_readability(result[key])

    if isinstance(result.get("leg_descriptions"), str):
        lines = [
            sanitize_readability(line)
            for line in result["leg_descriptions"].splitlines()
            if sanitize_readability(line)
        ]
        result["leg_descriptions"] = "\n".join(lines)

    legs = result.get("legs")
    if isinstance(legs, list):
        for leg in legs:
            if not isinstance(leg, dict):
                continue
            for key in (
                "selection",
                "bet_type",
                "line",
                "odds",
                "event",
                "game_time",
                "description",
            ):
                if key in leg and isinstance(leg[key], str):
                    leg[key] = sanitize_readability(leg[key])
            if leg.get("description"):
                leg["description"] = sanitize_readability(leg["description"])
            elif leg.get("selection") or leg.get("bet_type"):
                parts = [leg.get("selection", ""), leg.get("bet_type", "")]
                if leg.get("line"):
                    parts.insert(1, leg["line"])
                leg["description"] = sanitize_readability(" - ".join(p for p in parts if p))

    return result
