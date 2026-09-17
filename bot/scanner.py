import logging
import pandas as pd
from .config import RULES

log = logging.getLogger("scanner")


class CryptoUniverse:
    """Build a liquid USDT spot universe from Binance 24h data."""

    def __init__(self, broker):
        self.broker = broker

    def symbols(self):
        info = self.broker.exchange_info()
        quote_asset = RULES["universe"].get("quote_asset", "USDT")
        allowed = {
            s["symbol"] for s in info["symbols"]
            if s.get("status") == "TRADING"
            and s.get("quoteAsset") == quote_asset
            and s.get("isSpotTradingAllowed", True)
        }
        excluded = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
        tickers = self.broker.ticker_24h()
        ranked = []
        for t in tickers:
            symbol = t.get("symbol", "")
            if symbol not in allowed or symbol.endswith(excluded):
                continue
            price = float(t.get("lastPrice", 0))
            quote_volume = float(t.get("quoteVolume", 0))
            if price < RULES["universe"]["min_price"] or quote_volume < RULES["universe"]["min_avg_dollar_volume"]:
                continue
            ranked.append((symbol, quote_volume))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in ranked[: RULES["universe"]["max_candidates"]]]


def gap_scan(broker, symbols):
    """Compatibility name: create a liquid watchlist without a stock-style gap filter."""
    tickers = {x.get("symbol"): x for x in broker.ticker_24h()}
    rows = []
    for symbol in symbols:
        ticker = tickers.get(symbol, {})
        rows.append({
            "symbol": symbol,
            "quote_volume_24h": float(ticker.get("quoteVolume", 0)),
            "change_pct_24h": float(ticker.get("priceChangePercent", 0)),
            "last_price": float(ticker.get("lastPrice", 0)),
        })
    rows.sort(key=lambda x: x["quote_volume_24h"], reverse=True)
    return rows[: RULES["universe"]["max_candidates"]]


def save_watchlist(rows, path="data/watchlist.csv"):
    columns = ["symbol", "quote_volume_24h", "change_pct_24h", "last_price"]
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
