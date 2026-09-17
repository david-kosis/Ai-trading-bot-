import math
from .config import RULES


def stop_from_day_low(day_low):
    pct = RULES["risk"]["stop_below_day_low_percent"] / 100
    return day_low * (1 - pct)


def position_size(equity, entry, stop):
    risk_dollars = equity * RULES["risk"]["risk_per_trade_percent"] / 100
    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0:
        return 0
    return max(0, math.floor(risk_dollars / risk_per_unit * 10**8) / 10**8)
