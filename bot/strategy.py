import pandas as pd

from .config import RULES


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def atr(df, period):
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def _completed(broker, symbol, interval, limit):
    df = pd.DataFrame(broker.historical(symbol, interval, limit))
    if len(df) < 2:
        return df
    # The last Binance kline may still be forming. Signals use completed bars only.
    return df.iloc[:-1].copy().reset_index(drop=True)


def _regime_ok(broker):
    cfg = RULES["strategy"]
    df = _completed(
        broker,
        cfg["regime_symbol"],
        cfg["regime_timeframe"],
        cfg["regime_ema_slow"] + 30,
    )
    if len(df) < cfg["regime_ema_slow"] + 5:
        return False
    fast = ema(df["close"], cfg["regime_ema_fast"])
    slow = ema(df["close"], cfg["regime_ema_slow"])
    return bool(df.iloc[-1]["close"] > slow.iloc[-1] and fast.iloc[-1] > slow.iloc[-1])


def entry_signal(broker, symbol):
    """Crypto-native multi-timeframe breakout signal.

    4H BTC regime -> 1H trend -> 15M breakout + volume + ATR extension filter.
    The returned stop is volatility-based, not based on a stock-market daily low.
    """
    cfg = RULES["strategy"]
    if symbol == cfg["regime_symbol"]:
        # BTC can trade this strategy too; the regime still evaluates BTC itself.
        pass

    if not _regime_ok(broker):
        return None

    trend = _completed(broker, symbol, cfg["trend_timeframe"], cfg["trend_ema_slow"] + 30)
    entry = _completed(
        broker,
        symbol,
        cfg["entry_timeframe"],
        max(cfg["breakout_lookback"] + cfg["atr_period"] + 5, 60),
    )
    if len(trend) < cfg["trend_ema_slow"] + 5 or len(entry) < cfg["breakout_lookback"] + cfg["atr_period"] + 2:
        return None

    trend_fast = ema(trend["close"], cfg["trend_ema_fast"])
    trend_slow = ema(trend["close"], cfg["trend_ema_slow"])
    trend_close = float(trend.iloc[-1]["close"])
    if not (trend_close > trend_fast.iloc[-1] and trend_fast.iloc[-1] > trend_slow.iloc[-1]):
        return None

    entry["atr"] = atr(entry, cfg["atr_period"])
    current = entry.iloc[-1]
    previous = entry.iloc[:-1]
    if pd.isna(current["atr"]):
        return None

    breakout_level = float(previous["high"].tail(cfg["breakout_lookback"]).max())
    avg_volume = float(previous["volume"].tail(cfg["volume_lookback"]).mean())
    if avg_volume <= 0:
        return None

    price = float(current["close"])
    current_atr = float(current["atr"])
    relative_volume = float(current["volume"]) / avg_volume
    extension = price - breakout_level

    if price <= breakout_level:
        return None
    if relative_volume < cfg["relative_volume_min"]:
        return None
    if extension > cfg["max_extension_atr"] * current_atr:
        return None

    stop = price - cfg["stop_atr_multiple"] * current_atr
    if stop <= 0 or stop >= price:
        return None

    return {
        "symbol": symbol,
        "price": price,
        "stop": stop,
        "atr": current_atr,
        "breakout_level": breakout_level,
        "relative_volume": relative_volume,
        "trend_ema_fast": float(trend_fast.iloc[-1]),
        "trend_ema_slow": float(trend_slow.iloc[-1]),
    }
