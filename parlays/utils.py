from decimal import Decimal, InvalidOperation

from django.conf import settings

from .models import Parlay

DEFAULT_CREATOR_NICKNAME = "Host"


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


