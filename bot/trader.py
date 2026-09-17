from .config import RULES, SETTINGS
from .risk import position_size, stop_from_day_low
from .database import log_event
from .notify import send


class TradeManager:
    def __init__(self, broker):
        self.broker = broker

    def enter(self, symbol, price, day_low):
        equity = self.broker.account_equity()
        stop = stop_from_day_low(day_low)
        qty = position_size(equity, price, stop)
        qty = self.broker.normalize_quantity(symbol, qty)
        if qty <= 0:
            log_event("entry_blocked", symbol, {"price": price, "stop": stop, "reason": "quantity_zero"})
            return None
        order = self.broker.market_order(symbol, qty, "BUY")
        log_event("entry", symbol, {"qty": qty, "entry": price, "stop": stop, "order": order})
        send(f"ENTRY {symbol} qty={qty} entry~{price:.6f} stop={stop:.6f} mode={SETTINGS.broker_mode}")
        return {"symbol": symbol, "qty": qty, "entry": price, "stop": stop, "order": order}

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
