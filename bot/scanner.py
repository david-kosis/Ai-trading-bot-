import logging
import pandas as pd
from .config import RULES
from .broker import IBKRBroker

log = logging.getLogger("scanner")

class SP500Universe:
    def __init__(self, path="data/sp500.csv"):
        self.path = path

    def symbols(self):
        df = pd.read_csv(self.path)
        return df["symbol"].dropna().astype(str).str.upper().unique().tolist()

def bars_to_df(bars):
    return pd.DataFrame([{
        "date": b.date, "open": b.open, "high": b.high,
        "low": b.low, "close": b.close, "volume": b.volume
    } for b in bars])

def gap_scan(broker, symbols):
    cfg = RULES["universe"]
    candidates = []
    for symbol in symbols:
        try:
            df = bars_to_df(broker.historical(symbol, "5 D", "1 day", True))
            if len(df) < 2:
                continue
            prev, today = df.iloc[-2], df.iloc[-1]
            if today.close < cfg["min_price"] or prev.close <= 0:
                continue
            gap = (today.open - prev.close) / prev.close * 100
            avg_dollar_volume = (df.close * df.volume).tail(5).mean()
            if abs(gap) >= cfg["gap_percent_min"] and avg_dollar_volume >= cfg["min_avg_dollar_volume"]:
                candidates.append({
                    "symbol": symbol, "gap_pct": gap,
                    "prev_close": prev.close, "open": today.open
                })
        except Exception as exc:
            log.warning("scan failed for %s: %s", symbol, exc)
    candidates.sort(key=lambda x: abs(x["gap_pct"]), reverse=True)
    return candidates[:cfg["max_candidates"]]

def save_watchlist(rows, path="data/watchlist.csv"):
    pd.DataFrame(rows).to_csv(path, index=False)
