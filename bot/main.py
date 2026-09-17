import argparse
import logging
from datetime import datetime, timezone
import pandas as pd

from .logging_setup import setup_logging
from .config import RULES
from .broker import BinanceBroker
from .scanner import CryptoUniverse, gap_scan, save_watchlist
from .database import log_event
from .notify import send
from .trader import TradeManager

log = logging.getLogger("main")


def scan():
    broker = BinanceBroker("scanner")
    try:
        broker.connect()
        symbols = CryptoUniverse(broker).symbols()
        rows = gap_scan(broker, symbols)
        save_watchlist(rows)
        log_event("watchlist", payload={"count": len(rows), "symbols": [x["symbol"] for x in rows]})
        message = "BINANCE WATCHLIST READY\n" + "\n".join(
            f'{x["symbol"]} gap={x["gap_pct"]:.2f}%' for x in rows
        )
        send(message)
        log.info("Scanned %s symbols; %s candidates", len(symbols), len(rows))
    finally:
        broker.disconnect()


def trade_cycle():
    broker = BinanceBroker("execution")
    try:
        broker.connect()
        manager = TradeManager(broker)
        now = datetime.now(timezone.utc)

        # Crypto trades 24/7. This optional UTC force-exit is deliberately
        # disabled by default; position management can be added later.
        force_exit = RULES["risk"].get("force_exit_time_utc")
        if force_exit and now.strftime("%H:%M") >= force_exit:
            manager.force_close_all()
            return

        try:
            watch = pd.read_csv("data/watchlist.csv")
        except FileNotFoundError:
            log.warning("No watchlist. Run the scan first.")
            return

        for symbol in watch["symbol"].head(RULES["universe"]["max_candidates"]):
            log_event("candidate_cycle", str(symbol), {"time_utc": now.isoformat()})

        log.info("Trading cycle completed. Entry execution remains gated until strategy conditions pass.")
    finally:
        broker.disconnect()


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["scan", "trade"], required=True)
    args = parser.parse_args()
    scan() if args.mode == "scan" else trade_cycle()
