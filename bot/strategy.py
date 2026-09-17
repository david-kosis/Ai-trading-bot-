import pandas as pd

from .config import RULES


def _daily_context(broker, symbol):
    daily = pd.DataFrame(broker.historical(symbol, "1d", 220))
    if len(daily) < 201:
        return None
    # Exclude the currently forming daily candle from the SMA/previous-day values.
    completed = daily.iloc[:-1].copy()
    prev = completed.iloc[-1]
    sma200 = completed["close"].tail(200).mean()
    return {
        "previous_close": float(prev["close"]),
        "previous_high": float(prev["high"]),
        "sma200": float(sma200),
    }


def entry_signal(broker, symbol):
    """Return an entry signal dict when all configured breakout conditions pass."""
    cfg = RULES["entry"]
    daily_ctx = _daily_context(broker, symbol)
    if daily_ctx is None:
        return None

    bars = pd.DataFrame(broker.historical(symbol, cfg.get("timeframe", "5m"), 100))
    if len(bars) < 25:
        return None

    current = bars.iloc[-1]
    previous_bars = bars.iloc[:-1]
    prior_intraday_high = float(previous_bars["high"].tail(20).max())
    avg_volume = float(previous_bars["volume"].tail(20).mean())
    if avg_volume <= 0:
        return None

    price = float(current["close"])
    relative_volume = float(current["volume"]) / avg_volume

    if cfg.get("require_previous_day_high", True) and price <= daily_ctx["previous_high"]:
        return None
    if cfg.get("require_previous_close_above_sma200", True) and daily_ctx["previous_close"] <= daily_ctx["sma200"]:
        return None
    if cfg.get("require_price_above_day_high", True) and price <= daily_ctx["previous_high"]:
        return None
    if cfg.get("require_breakout_above_prior_intraday_high", True) and price <= prior_intraday_high:
        return None
    if relative_volume < cfg.get("relative_volume_min", 1.5):
        return None

    # Current day's low is used for the configured protective stop.
    day = pd.DataFrame(broker.historical(symbol, "1d", 2))
    if day.empty:
        return None
    day_low = float(day.iloc[-1]["low"])

    return {
        "symbol": symbol,
        "price": price,
        "day_low": day_low,
        "relative_volume": relative_volume,
        "previous_high": daily_ctx["previous_high"],
        "sma200": daily_ctx["sma200"],
    }
