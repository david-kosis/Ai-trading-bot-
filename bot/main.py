import argparse
import logging
import time
from datetime import datetime, timezone

import pandas as pd

from .logging_setup import setup_logging
from .config import RULES, SETTINGS
from .broker import BinanceBroker
from .scanner import CryptoUniverse, gap_scan, save_watchlist
from .strategy import entry_signal
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
        message = "BINANCE LIQUID WATCHLIST READY\n" + "\n".join(
            f'{x["symbol"]} 24h_volume={x["quote_volume_24h"]:.0f} change={x["change_pct_24h"]:.2f}%'
            for x in rows
        )
        send(message)
        log.info("Ranked %s liquid symbols; watchlist contains %s", len(symbols), len(rows))
        return rows
    finally:
        broker.disconnect()


def trade_cycle(manager, broker, trades_today):
    watch_path = "data/watchlist.csv"
    try:
        watch = pd.read_csv(watch_path)
    except FileNotFoundError:
        log.warning("No watchlist. Run the scan first.")
        return trades_today
    except pd.errors.EmptyDataError:
        log.info("Watchlist is empty; no candidates to evaluate.")
        return trades_today

    if "symbol" not in watch.columns or watch.empty:
        log.info("Watchlist contains no candidates.")
        return trades_today

    max_trades = RULES["entry"]["max_daily_trades"]
    max_positions = RULES["entry"]["max_concurrent_positions"]

    manager.manage()
    if trades_today >= max_trades or len(manager.active) >= max_positions:
        return trades_today

    for symbol in watch["symbol"].head(RULES["universe"]["max_candidates"]):
        symbol = str(symbol).upper()
        if symbol in manager.active:
            continue
        if trades_today >= max_trades or len(manager.active) >= max_positions:
            break
        try:
            signal = entry_signal(broker, symbol)
            if not signal:
                continue
            log_event("entry_signal", symbol, signal)
            trade = manager.enter(symbol, signal["price"], signal["stop"])
            if trade:
                trades_today += 1
                log.info("Entered %s; trades_today=%s", symbol, trades_today)
        except Exception as exc:
            log_event("candidate_error", symbol, {"error": str(exc)})
            log.warning("Candidate evaluation failed for %s: %s", symbol, exc)

    return trades_today


def run_bot(interval_seconds=30):
    """Continuously scan and evaluate the crypto-native strategy."""
    broker = BinanceBroker("execution")
    manager = TradeManager(broker)
    trades_today = 0
    day_key = datetime.now(timezone.utc).date()

    try:
        broker.connect()
        log.info("AUTONOMOUS TESTNET BOT STARTED; live=%s", SETTINGS.can_trade_live)
        while True:
            now = datetime.now(timezone.utc)
            if now.date() != day_key:
                day_key = now.date()
                trades_today = 0

            try:
                symbols = CryptoUniverse(broker).symbols()
                rows = gap_scan(broker, symbols)
                save_watchlist(rows)
            except Exception as exc:
                log.warning("Scan cycle failed: %s", exc)

            trades_today = trade_cycle(manager, broker, trades_today)
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        log.info("Bot stopped by user")
    finally:
        broker.disconnect()


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["scan", "trade", "run"], required=True)
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()

    if args.mode == "scan":
        scan()
    elif args.mode == "trade":
        broker = BinanceBroker("execution")
        try:
            broker.connect()
            manager = TradeManager(broker)
            trade_cycle(manager, broker, 0)
        finally:
            broker.disconnect()
    else:
        run_bot(args.interval)
