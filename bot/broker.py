import logging
from ib_insync import IB, Stock, MarketOrder
from .config import SETTINGS

log = logging.getLogger("broker")

class IBKRBroker:
    def __init__(self, purpose="execution"):
        self.ib = IB()
        self.client_id = SETTINGS.exec_client_id if purpose == "execution" else SETTINGS.scan_client_id

    def connect(self):
        if not self.ib.isConnected():
            self.ib.connect(SETTINGS.ib_host, SETTINGS.ib_port, clientId=self.client_id)
        log.info("IBKR connected; mode=%s client_id=%s", SETTINGS.broker_mode, self.client_id)

    def disconnect(self):
        if self.ib.isConnected():
            self.ib.disconnect()

    def stock(self, symbol):
        return Stock(symbol, "SMART", "USD")

    def qualify(self, symbol):
        contract = self.stock(symbol)
        self.ib.qualifyContracts(contract)
        return contract

    def historical(self, symbol, duration="30 D", bar_size="5 mins", use_rth=False):
        contract = self.qualify(symbol)
        return self.ib.reqHistoricalData(
            contract, endDateTime="", durationStr=duration,
            barSizeSetting=bar_size, whatToShow="TRADES",
            useRTH=use_rth, formatDate=1
        )

    def account_equity(self):
        self.connect()
        for x in self.ib.accountSummary():
            if x.tag == "NetLiquidation" and x.currency == "BASE":
                return float(x.value)
        raise RuntimeError("NetLiquidation not found")

    def positions(self):
        self.connect()
        return self.ib.positions()

    def market_order(self, symbol, qty, side):
        if qty <= 0:
            raise ValueError("qty must be positive")
        if SETTINGS.broker_mode == "live" and not SETTINGS.live_enabled:
            raise RuntimeError("LIVE_TRADING_ENABLED is false")
        contract = self.qualify(symbol)
        order = MarketOrder(side.upper(), int(qty))
        return self.ib.placeOrder(contract, order)

    def close_position(self, symbol, qty):
        return self.market_order(symbol, qty, "SELL")
