"""
Detect and validate shared bet slip URLs (FanDuel / DraftKings hosts).
"""
import re
from urllib.parse import urlparse

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


def is_supported_bet_link(url: str) -> bool:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.netloc or "").lower().removeprefix("www.")
    if any(host == h or host.endswith("." + h) for h in FANDUEL_HOSTS):
        return True
    if any(host == h or host.endswith("." + h) for h in DRAFTKINGS_HOSTS):
        return True
    return False


def sportsbook_display_name(url: str = "") -> str:
    """Human-readable sportsbook label for share previews."""
    if not url or not str(url).strip():
        return "Parlay"
    host = (urlparse(url.strip()).netloc or "").lower().removeprefix("www.")
    if any(host == h or host.endswith("." + h) for h in FANDUEL_HOSTS):
        return "FanDuel"
    if any(host == h or host.endswith("." + h) for h in DRAFTKINGS_HOSTS):
        return "DraftKings"
    return "Sportsbook"


def parse_bet_slip_link(url: str) -> dict:
    """Extract coordination fields from a shared bet URL."""
    url = url.strip()
    if not is_supported_bet_link(url):
        return {}
    return {"external_link": url}
