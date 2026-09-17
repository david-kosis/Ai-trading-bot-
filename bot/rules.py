import pandas as pd
from datetime import time

def parse_time(value):
    return time.fromisoformat(value)

def evaluate(daily, intraday, premarket_high, relative_volume, rules):
    prior = daily.iloc[-2].copy()
    daily = daily.copy()
    daily["sma200"] = daily["close"].rolling(200).mean()
    sma200 = float(daily.iloc[-2]["sma200"])

    current = intraday.iloc[-1]
    previous_intraday_high = float(intraday.iloc[:-1]["high"].max()) if len(intraday) > 1 else float("nan")
    price = float(current["close"])

    checks = {
        "price_above_prior_day_high": price > float(prior["high"]),
        "prior_close_above_sma200": float(prior["close"]) > sma200,
        "gap_ok": True,
        "price_above_premarket_high": premarket_high is not None and price > premarket_high,
        "price_above_today_high": previous_intraday_high == previous_intraday_high and price > previous_intraday_high,
        "relative_volume": relative_volume >= rules["entry"]["relative_volume_min"]
    }

    e = rules["entry"]
    enabled = [
        ("price_above_prior_day_high", e["require_prior_day_high"]),
        ("prior_close_above_sma200", e["require_prior_close_above_sma200"]),
        ("price_above_premarket_high", e["require_price_above_premarket_high"]),
        ("price_above_today_high", e["require_breakout_above_prior_intraday_high"])
    ]
    passed = all(checks[name] for name, active in enabled if active) and checks["relative_volume"]
    return passed, checks
