"""Detect sportsbook and route to the correct parser."""

from __future__ import annotations

from parlays.services.ocr.extract import OCRLine
from parlays.services.ocr.segmentation import extract_header, segment_leg_blocks

from .base import BaseSlipParser, ParsedSlip
from .draftkings import DraftKingsParser
from .fanduel import FanDuelParser
from .generic import GenericParser

PARSERS: list[type[BaseSlipParser]] = [
    DraftKingsParser,
    FanDuelParser,
]


def detect_sportsbook(lines: list[OCRLine], raw_text: str) -> str:
    for parser_cls in PARSERS:
        if parser_cls.detect(lines, raw_text):
            return parser_cls.sportsbook_name
    return GenericParser.sportsbook_name


def get_parser(sportsbook: str) -> BaseSlipParser:
    for parser_cls in PARSERS:
        if parser_cls.sportsbook_name.lower() == sportsbook.lower():
            return parser_cls()
    return GenericParser()


def parse_slip(lines: list[OCRLine], raw_text: str) -> ParsedSlip:
    sportsbook = detect_sportsbook(lines, raw_text)
    header = extract_header(lines)
    leg_blocks = segment_leg_blocks(lines, header)
    parser = get_parser(sportsbook)
    return parser.parse(lines, header, leg_blocks, raw_text)
