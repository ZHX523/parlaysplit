import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone

from .models import Parlay

DEFAULT_CREATOR_NICKNAME = "HOST"


def normalize_host_code(raw: str) -> str:
    return (raw or "").strip().upper()


def is_valid_host_code_format(code: str) -> bool:
    """Accept current-length codes and legacy 5-digit numeric codes."""
    if not code:
        return False
    max_len = getattr(settings, "HOST_CODE_LENGTH", 6)
    if len(code) < 5 or len(code) > max_len:
        return False
    return code.isalnum()


def generate_host_code() -> str:
    """Unique alphanumeric host code for parlay lookup."""
    length = getattr(settings, "HOST_CODE_LENGTH", 6)
    alphabet = getattr(settings, "HOST_CODE_CHARSET", "ABCDEFGHJKLMNPQRSTUVWXYZ23456789")

    for _ in range(300):
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        if not Parlay.objects.filter(host_code=code).exists():
            return code
    raise RuntimeError("Could not allocate a unique host code.")


def clear_expired_host_codes() -> int:
    """Clear host codes for expired parlays (expiry timestamp is kept)."""
    now = timezone.now()
    expired = Parlay.objects.filter(
        host_code__isnull=False,
        host_code_expires_at__lt=now,
    )
    return expired.update(host_code=None)


def format_dollars(value) -> str:
    """Format a number as USD with thousands separators (e.g. $1,234.56)."""
    if value is None or value == "":
        return "—"
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    text = f"{amount:f}"
    if "." in text:
        whole, frac = text.split(".", 1)
    else:
        whole, frac = text, ""
    frac = (frac + "00")[:2]
    return f"${sign}{int(whole):,}.{frac}"

HOST_OWNERSHIP_COLOR = "#10b981"
FRIEND_OWNERSHIP_COLORS = (
    "#38bdf8",
    "#a78bfa",
    "#fbbf24",
    "#fb7185",
    "#22d3ee",
    "#f472b6",
    "#818cf8",
)


def parse_currency(value) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).replace("$", "").replace(",", "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def ownership_color(is_host: bool, friend_index: int = 0) -> str:
    if is_host:
        return HOST_OWNERSHIP_COLOR
    return FRIEND_OWNERSHIP_COLORS[friend_index % len(FRIEND_OWNERSHIP_COLORS)]


def build_ownership_bar(rows: list[dict]) -> list[dict]:
    segments = []
    for row in rows:
        pct = row.get("ownership")
        if pct is None or pct <= 0:
            continue
        segments.append(
            {
                "nickname": row["nickname"],
                "percent": pct,
                "color": row["color"],
                "is_host": row["is_host"],
            }
        )
    return segments


def next_participant_nickname(parlay: Parlay) -> str:
    for i in range(1, settings.MAX_PARTICIPANTS + 2):
        name = f"Contributor {i}"
        if not parlay.participants.filter(nickname=name).exists():
            return name
    return f"Contributor {parlay.participant_count + 1}"


