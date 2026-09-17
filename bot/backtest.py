"""Research backtester for the crypto-native breakout strategy.

Usage examples:
  python -m bot.backtest --symbol ETHUSDT --days 90
  python -m bot.backtest --symbol SOLUSDT --days 180 --interval 15m

The backtester downloads public Binance klines, builds 1H/4H context from
15-minute data, enters on the next bar open, models fees and slippage, and
reports equity, drawdown and trade statistics. It is research tooling only.
"""

import argparse
import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

from .config import RULES

PUBLIC_URL = "https://testnet.binance.vision/api/v3/klines"


@dataclass
class Position:
    symbol: str
    qty: float
    entry: float
    initial_stop: float
    stop: float
    risk_per_unit: float
    highest: float
    partial_taken: bool = False
    entry_time: pd.Timestamp | None = None


def fetch_klines(symbol, interval, days):
    """Download public historical klines in Binance's 1000-row pages."""
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    start = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    rows = []
    while start < end:
        params = {"symbol": symbol, "interval": interval, "startTime": start, "endTime": end, "limit": 1000}
        response = requests.get(PUBLIC_URL, params=params, timeout=20)
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        rows.extend(batch)
        next_start = int(batch[-1][0]) + 1
        if next_start <= start:
            break
        start = next_start
        if len(batch) < 1000:
            break
        time.sleep(0.05)

    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
    ])
    if df.empty:
        raise RuntimeError(f"No historical data returned for {symbol}")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True) + pd.Timedelta(minutes=15)
    return df.drop_duplicates("timestamp").set_index("timestamp").sort_index()


def resample_ohlcv(df, rule):
    return df.resample(rule, label="right", closed="right").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
    }).dropna()


def ema(s, period):
    return s.ewm(span=period, adjust=False).mean()


def atr(df, period):
    prev = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def signal_at(ts, symbol_df, btc_df):
    cfg = RULES["strategy"]
    entry = symbol_df.loc[:ts]
    btc = btc_df.loc[:ts]
    if len(entry) < cfg["breakout_lookback"] + cfg["atr_period"] + 2:
        return None

    btc4 = resample_ohlcv(btc, "4h")
    if len(btc4) < cfg["regime_ema_slow"] + 5:
        return None
    btc_fast = ema(btc4["close"], cfg["regime_ema_fast"])
    btc_slow = ema(btc4["close"], cfg["regime_ema_slow"])
    if not (btc4["close"].iloc[-1] > btc_slow.iloc[-1] and btc_fast.iloc[-1] > btc_slow.iloc[-1]):
        return None

    trend = resample_ohlcv(entry, "1h")
    if len(trend) < cfg["trend_ema_slow"] + 5:
        return None
    trend_fast = ema(trend["close"], cfg["trend_ema_fast"])
    trend_slow = ema(trend["close"], cfg["trend_ema_slow"])
    if not (trend["close"].iloc[-1] > trend_fast.iloc[-1] > trend_slow.iloc[-1]):
        return None

    e = entry.copy()
    e["atr"] = atr(e, cfg["atr_period"])
    current = e.iloc[-1]
    previous = e.iloc[:-1]
    if pd.isna(current["atr"]):
        return None

    breakout = previous["high"].tail(cfg["breakout_lookback"]).max()
    avg_volume = previous["volume"].tail(cfg["volume_lookback"]).mean()
    price = float(current["close"])
    current_atr = float(current["atr"])
    rv = float(current["volume"]) / float(avg_volume) if avg_volume else 0
    if price <= breakout or rv < cfg["relative_volume_min"]:
        return None
    if price - breakout > cfg["max_extension_atr"] * current_atr:
        return None
    stop = price - cfg["stop_atr_multiple"] * current_atr
    if stop <= 0 or stop >= price:
        return None
    return {"price": price, "stop": stop, "atr": current_atr, "rv": rv}


def run_backtest(symbol, days):
    cfg = RULES["strategy"]
    risk_cfg = RULES["risk"]
    bt_cfg = RULES["backtest"]
    equity = float(bt_cfg["initial_equity"])
    peak = equity
    max_dd = 0.0
    position = None
    trades = []
    daily_start = equity
    daily_pnl = 0.0
    daily_key = None
    trades_today = 0
    consecutive_losses = 0
    cooldown_until = None

    data = fetch_klines(symbol, cfg["entry_timeframe"], days)
    btc = fetch_klines(cfg["regime_symbol"], cfg["entry_timeframe"], days)
    common = data.index.intersection(btc.index)
    data = data.loc[common]
    btc = btc.loc[common]
    if len(data) < 1000:
        raise RuntimeError("Not enough overlapping data for this backtest window")

    fee = float(bt_cfg["fee_rate"])
    slip = float(bt_cfg["slippage_rate"])

    for i in range(1, len(data)):
        ts = data.index[i]
        bar = data.iloc[i]
        day = ts.date()
        if day != daily_key:
            daily_key = day
            daily_start = equity
            daily_pnl = 0.0
            trades_today = 0

        # Manage existing position using this bar's OHLC.
        if position is not None:
            position.highest = max(position.highest, float(bar.high))
            exit_price = None
            exit_reason = None

            if float(bar.low) <= position.stop:
                exit_price = position.stop * (1 - slip)
                exit_reason = "stop"
            else:
                r_high = (float(bar.high) - position.entry) / position.risk_per_unit
                if not position.partial_taken and r_high >= risk_cfg["partial_profit_r"]:
                    partial_qty = position.qty * risk_cfg["partial_profit_percent"] / 100
                    fill = position.entry + position.risk_per_unit * risk_cfg["partial_profit_r"]
                    fill *= 1 - slip
                    proceeds = partial_qty * fill
                    fee_paid = proceeds * fee
                    equity += proceeds - fee_paid
                    position.qty -= partial_qty
                    position.partial_taken = True
                    position.stop = max(position.stop, position.entry)

                if r_high >= risk_cfg["breakeven_at_r"]:
                    position.stop = max(position.stop, position.entry)

                if r_high >= risk_cfg["trail_after_r"]:
                    # Use ATR from data available up to this bar only.
                    local = data.iloc[: i + 1]
                    a = float(atr(local, cfg["atr_period"]).iloc[-1])
                    new_stop = position.highest - risk_cfg["trail_atr_multiple"] * a
                    position.stop = max(position.stop, new_stop)

                if float(bar.close) <= position.stop:
                    exit_price = position.stop * (1 - slip)
                    exit_reason = "trail"

            if exit_price is not None:
                proceeds = position.qty * exit_price
                fee_paid = proceeds * fee
                equity += proceeds - fee_paid
                pnl = (exit_price - position.entry) * position.qty
                daily_pnl += pnl
                trades.append({"entry_time": position.entry_time, "exit_time": ts, "pnl": pnl, "reason": exit_reason})
                if pnl < 0:
                    consecutive_losses += 1
                    if consecutive_losses >= risk_cfg["max_consecutive_losses"]:
                        cooldown_until = ts + pd.Timedelta(minutes=risk_cfg["cooldown_minutes"])
                else:
                    consecutive_losses = 0
                position = None

        # Signal at close; execute at next bar open, so no lookahead.
        if position is None and i + 1 < len(data):
            if trades_today >= RULES["entry"]["max_daily_trades"]:
                continue
            if daily_pnl <= -daily_start * risk_cfg["max_daily_loss_percent"] / 100:
                continue
            if cooldown_until is not None and ts < cooldown_until:
                continue
            signal = signal_at(ts, data, btc)
            if signal is not None:
                next_open = float(data.iloc[i + 1]["open"]) * (1 + slip)
                risk_per_unit = next_open - signal["stop"]
                if risk_per_unit <= 0:
                    continue
                risk_cash = equity * risk_cfg["risk_per_trade_percent"] / 100
                qty = risk_cash / risk_per_unit
                notional = qty * next_open
                entry_fee = notional * fee
                if notional + entry_fee >= equity or qty <= 0:
                    continue
                equity -= entry_fee
                position = Position(symbol, qty, next_open, signal["stop"], signal["stop"], risk_per_unit, next_open, entry_time=data.index[i + 1])
                trades_today += 1

        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0)

    if position is not None:
        last = data.iloc[-1]
        exit_price = float(last["close"]) * (1 - slip)
        proceeds = position.qty * exit_price
        equity += proceeds - proceeds * fee
        pnl = (exit_price - position.entry) * position.qty
        trades.append({"entry_time": position.entry_time, "exit_time": data.index[-1], "pnl": pnl, "reason": "end_of_test"})

    pnls = np.array([t["pnl"] for t in trades], dtype=float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    profit_factor = wins.sum() / abs(losses.sum()) if losses.size else math.inf
    win_rate = len(wins) / len(pnls) if len(pnls) else 0.0
    return {
        "symbol": symbol,
        "days": days,
        "initial_equity": bt_cfg["initial_equity"],
        "final_equity": round(equity, 2),
        "return_pct": round((equity / bt_cfg["initial_equity"] - 1) * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "trades": len(trades),
        "win_rate_pct": round(win_rate * 100, 2),
        "profit_factor": round(profit_factor, 3) if math.isfinite(profit_factor) else "inf",
        "total_pnl": round(float(pnls.sum()) if len(pnls) else 0.0, 2),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="ETHUSDT")
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args()
    result = run_backtest(args.symbol.upper(), args.days)
    print("\nCRYPTO BREAKOUT BACKTEST")
    for key, value in result.items():
        print(f"{key}: {value}")
    print("\nResearch only: historical results include modeled fees/slippage but do not predict future performance.")


if __name__ == "__main__":
    main()
