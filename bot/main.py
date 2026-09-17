import argparse, logging
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from .logging_setup import setup_logging
from .config import RULES
from .broker import IBKRBroker
from .scanner import SP500Universe, gap_scan, save_watchlist
from .database import log_event
from .notify import send
from .trader import TradeManager

log = logging.getLogger("main")
ET = ZoneInfo("America/New_York")

def scan():
    broker = IBKRBroker("scanner")
    broker.connect()
    rows = gap_scan(broker, SP500Universe().symbols())
    save_watchlist(rows)
    log_event("watchlist", payload={"count": len(rows), "symbols": [x["symbol"] for x in rows]})
    send("WATCHLIST READY\n" + "\n".join(f'{x["symbol"]} gap={x["gap_pct"]:.2f}%' for x in rows))
    broker.disconnect()

def trade_cycle():
    broker = IBKRBroker("execution")
    broker.connect()
    manager = TradeManager(broker)
    now = datetime.now(ET)

    if now.strftime("%H:%M") >= RULES["risk"]["force_exit_time_et"]:
        manager.force_close_all()
        broker.disconnect()
        return

    try:
        watch = pd.read_csv("data/watchlist.csv")
    except FileNotFoundError:
        log.warning("No watchlist. Run the scan first.")
        broker.disconnect()
        return

    # Candidate processing is intentionally separated from order submission.
    # Complete real-time evaluation should consume IBKR real-time bars/ticks,
    # then call TradeManager.enter() only when every rule passes.
    for symbol in watch["symbol"].head(RULES["universe"]["max_candidates"]):
        log_event("candidate_cycle", str(symbol), {"time_et": now.isoformat()})

    log.info("Trading cycle completed.")
    broker.disconnect()

if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["scan", "trade"], required=True)
    args = parser.parse_args()
    scan() if args.mode == "scan" else trade_cycle()
