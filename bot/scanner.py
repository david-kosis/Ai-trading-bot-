import logging
import pandas as pd
from .config import RULES

log = logging.getLogger("scanner")


class CryptoUniverse:
    """Build a liquid USDT spot universe from Binance exchange/24h data."""

    def __init__(self, broker):
        self.broker = broker

    def symbols(self):
        info = self.broker.exchange_info()
        allowed = {
            s["symbol"] for s in info["symbols"]
            if s.get("status") == "TRADING"
            and s.get("quoteAsset") == "USDT"
            and s.get("isSpotTradingAllowed", True)
        }
        excluded = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
        tickers = self.broker.ticker_24h()
        ranked = []
        for t in tickers:
            symbol = t.get("symbol", "")
            if symbol not in allowed or symbol.endswith(excluded):
                continue
            ranked.append((symbol, float(t.get("quoteVolume", 0))))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in ranked[:100]]


def bars_to_df(bars):
    return pd.DataFrame(bars)


def gap_scan(broker, symbols):
    """Scan daily crypto candles for a configurable open-vs-prior-close gap."""
    cfg = RULES["universe"]
    candidates = []
    for symbol in symbols:
        try:
            df = bars_to_df(broker.historical(symbol, "1d", 6))
            if len(df) < 2:
                continue
            prev, today = df.iloc[-2], df.iloc[-1]
            if today.close < cfg["min_price"] or prev.close <= 0:
                continue
            gap = (today.open - prev.close) / prev.close * 100
            avg_dollar_volume = (df.close * df.volume).tail(5).mean()
            if abs(gap) >= cfg["gap_percent_min"] and avg_dollar_volume >= cfg["min_avg_dollar_volume"]:
                candidates.append({
                    "symbol": symbol,
                    "gap_pct": gap,
                    "prev_close": prev.close,
                    "open": today.open,
                    "day_high": today.high,
                    "day_low": today.low,
                    "volume": today.volume,
                })
        except Exception as exc:
            log.warning("scan failed for %s: %s", symbol, exc)
    candidates.sort(key=lambda x: abs(x["gap_pct"]), reverse=True)
    return candidates[:cfg["max_candidates"]]


def save_watchlist(rows, path="data/watchlist.csv"):
    # Always write CSV headers, even when no symbols qualify.
    columns = ["symbol", "gap_pct", "prev_close", "open", "day_high", "day_low", "volume"]
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
