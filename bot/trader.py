from datetime import datetime, timezone

from .config import RULES, SETTINGS
from .risk import position_size, stop_from_day_low
from .database import log_event
from .notify import send


class TradeManager:
    def __init__(self, broker):
        self.broker = broker
        self.active = {}

    def enter(self, symbol, price, day_low):
        equity = self.broker.account_equity()
        stop = stop_from_day_low(day_low)
        qty = position_size(equity, price, stop)
        qty = self.broker.normalize_quantity(symbol, qty)
        if qty <= 0:
            log_event("entry_blocked", symbol, {"price": price, "stop": stop, "reason": "quantity_zero"})
            return None

        order = self.broker.market_order(symbol, qty, "BUY")
        filled_price = float(order.get("fills", [{}])[0].get("price", price)) if order.get("fills") else price
        risk_per_unit = abs(filled_price - stop)
        target = filled_price + risk_per_unit * RULES["risk"]["partial_profit_r"]
        trade = {
            "symbol": symbol,
            "qty": qty,
            "entry": filled_price,
            "stop": stop,
            "target": target,
            "remaining_qty": qty,
            "partial_taken": False,
            "breakeven": False,
            "highest": filled_price,
            "entry_ts": datetime.now(timezone.utc).isoformat(),
        }
        self.active[symbol] = trade
        log_event("entry", symbol, trade | {"order": order})
        send(f"ENTRY {symbol} qty={qty} entry~{filled_price:.6f} stop={stop:.6f} mode={SETTINGS.broker_mode}")
        return trade

    def manage(self):
        """Poll active testnet positions and execute configured exits."""
        risk = RULES["risk"]
        for symbol, trade in list(self.active.items()):
            try:
                price = self.broker.last_price(symbol)
                trade["highest"] = max(trade["highest"], price)
                initial_risk = abs(trade["entry"] - trade["stop"])
                if initial_risk <= 0:
                    continue
                r = (price - trade["entry"]) / initial_risk

                # Protective stop: market exit for this running process.
                if price <= trade["stop"]:
                    self.broker.close_position(symbol, self.broker.normalize_quantity(symbol, trade["remaining_qty"]))
                    log_event("stop_exit", symbol, {"price": price, "qty": trade["remaining_qty"]})
                    send(f"STOP EXIT {symbol} price={price:.6f}")
                    del self.active[symbol]
                    continue

                # Take configured partial profit at 1R.
                if not trade["partial_taken"] and r >= risk["partial_profit_r"]:
                    partial_qty = trade["remaining_qty"] * risk["partial_profit_percent"] / 100
                    partial_qty = self.broker.normalize_quantity(symbol, partial_qty)
                    if partial_qty > 0:
                        self.broker.close_position(symbol, partial_qty)
                        trade["remaining_qty"] -= partial_qty
                        trade["partial_taken"] = True
                        log_event("partial_exit", symbol, {"price": price, "qty": partial_qty, "r": r})
                        send(f"PARTIAL EXIT {symbol} qty={partial_qty} price={price:.6f} R={r:.2f}")

                if r >= risk["breakeven_at_r"] and not trade["breakeven"]:
                    trade["stop"] = trade["entry"]
                    trade["breakeven"] = True
                    log_event("breakeven", symbol, {"stop": trade["stop"], "r": r})

                if r >= risk["trail_after_r"]:
                    trail_distance = initial_risk
                    new_stop = trade["highest"] - trail_distance
                    if new_stop > trade["stop"]:
                        trade["stop"] = new_stop
                        log_event("trail_update", symbol, {"stop": new_stop, "r": r})

            except Exception as exc:
                log_event("position_management_error", symbol, {"error": str(exc)})

    def force_close_all(self):
        for p in self.broker.positions():
            try:
                qty = self.broker.normalize_quantity(p["symbol"], p["quantity"])
                if qty <= 0:
                    continue
                self.broker.close_position(p["symbol"], qty)
                log_event("forced_exit", p["symbol"], {"qty": qty})
                send(f"FORCED EXIT {p['symbol']} qty={qty}")
            except Exception as exc:
                log_event("forced_exit_error", p.get("symbol", "unknown"), {"error": str(exc)})
