from decimal import Decimal, InvalidOperation


def american_odds_to_payout(wager: Decimal, odds_american: int) -> Decimal | None:
    """
    Total return if the parlay wins (stake + profit) from American odds.
    """
    if wager is None or odds_american is None:
        return None
    try:
        wager = Decimal(wager)
        odds = int(odds_american)
    except (InvalidOperation, TypeError, ValueError):
        return None

    if wager <= 0 or odds == 0:
        return None

    if odds > 0:
        profit = wager * Decimal(odds) / Decimal(100)
    else:
        profit = wager * Decimal(100) / Decimal(abs(odds))

    return (wager + profit).quantize(Decimal("0.01"))
