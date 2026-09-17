import math
from .config import RULES

def stop_from_day_low(day_low):
    pct = RULES["risk"]["stop_below_low_pct"] / 100
    return day_low * (1 - pct)

def position_size(equity, entry, stop):
    risk_dollars = equity * RULES["risk"]["risk_per_trade_pct"] / 100
    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0:
        return 0
    return max(0, math.floor(risk_dollars / risk_per_share))
