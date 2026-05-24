"""Sportsbook-specific bet slip parsers."""

from .registry import detect_sportsbook, parse_slip

__all__ = ["detect_sportsbook", "parse_slip"]
