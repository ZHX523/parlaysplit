"""
Detect and validate FanDuel / DraftKings shared bet slip URLs.
"""
import re
from urllib.parse import urlparse

from parlays.models import Sportsbook

FANDUEL_HOSTS = (
    "fanduel.com",
    "sportsbook.fanduel.com",
    "account.sportsbook.fanduel.com",
)
DRAFTKINGS_HOSTS = (
    "draftkings.com",
    "sportsbook.draftkings.com",
    "myaccount.draftkings.com",
)

SHARE_PATH_HINTS = re.compile(
    r"(share|shared|bet|slip|social|invite|receipt)",
    re.IGNORECASE,
)


def detect_sportsbook_from_url(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.netloc or "").lower().removeprefix("www.")
    if any(host == h or host.endswith("." + h) for h in FANDUEL_HOSTS):
        return Sportsbook.FANDUEL
    if any(host == h or host.endswith("." + h) for h in DRAFTKINGS_HOSTS):
        return Sportsbook.DRAFTKINGS
    return None


def is_supported_bet_link(url: str) -> bool:
    return detect_sportsbook_from_url(url) is not None


def parse_bet_slip_link(url: str) -> dict:
    """
    Extract coordination fields from a shared bet URL.
    Share links are often opaque; sportsbook + link are reliable.
    """
    url = url.strip()
    sportsbook = detect_sportsbook_from_url(url)
    if not sportsbook:
        return {}

    parsed = urlparse(url)
    return {
        "sportsbook": sportsbook,
        "external_link": url,
    }
