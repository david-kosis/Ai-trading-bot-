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
        if qty <= 0:
            log_event("entry_blocked", symbol, {"price": price, "stop": stop})
            return None
        self.broker.market_order(symbol, qty, "BUY")
        log_event("entry", symbol, {"qty": qty, "entry": price, "stop": stop})
        send(f"ENTRY {symbol} qty={qty} entry~{price:.2f} stop={stop:.2f} mode={SETTINGS.broker_mode}")
        return {"symbol": symbol, "qty": qty, "entry": price, "stop": stop}

    def force_close_all(self):
        for p in self.broker.positions():
            if p.position > 0:
                qty = int(p.position)
                self.broker.close_position(p.contract.symbol, qty)
                log_event("forced_exit", p.contract.symbol, {"qty": qty})
                send(f"FORCED EXIT {p.contract.symbol} qty={qty}")
