import hashlib
import hmac
import logging
import time
from decimal import Decimal, ROUND_DOWN
from urllib.parse import urlencode

import requests

from .config import SETTINGS

log = logging.getLogger("broker")


class BinanceBroker:
    """Small Binance Spot REST adapter.

    Paper mode uses Binance Spot Testnet. Live mode uses production only when
    LIVE_TRADING_ENABLED=true. API secrets are read from environment variables.
    """

    def __init__(self, purpose="execution"):
        self.purpose = purpose
        self.base_url = (
            "https://testnet.binance.vision"
            if SETTINGS.binance_testnet or SETTINGS.broker_mode == "paper"
            else "https://api.binance.com"
        )
        self.session = requests.Session()
        if SETTINGS.binance_api_key:
            self.session.headers.update({"X-MBX-APIKEY": SETTINGS.binance_api_key})

    def connect(self):
        self.server_time()
        log.info("Binance connected; endpoint=%s mode=%s", self.base_url, SETTINGS.broker_mode)

    def disconnect(self):
        self.session.close()

    def _request(self, method, path, params=None, signed=False):
        params = dict(params or {})
        if signed:
            if not SETTINGS.binance_api_key or not SETTINGS.binance_api_secret:
                raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET are required for signed requests")
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = SETTINGS.binance_recv_window
            query = urlencode(params)
            params["signature"] = hmac.new(
                SETTINGS.binance_api_secret.encode(), query.encode(), hashlib.sha256
            ).hexdigest()
        response = self.session.request(
            method, self.base_url + path, params=params, timeout=15
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Binance API {response.status_code}: {response.text}")
        return response.json()

    def server_time(self):
        return self._request("GET", "/api/v3/time")["serverTime"]

    def exchange_info(self):
        return self._request("GET", "/api/v3/exchangeInfo")

    def symbol_info(self, symbol):
        data = self._request("GET", "/api/v3/exchangeInfo", {"symbol": symbol})
        if not data.get("symbols"):
            raise ValueError(f"Unknown Binance symbol: {symbol}")
        return data["symbols"][0]

    def ticker_24h(self):
        return self._request("GET", "/api/v3/ticker/24hr")

    def historical(self, symbol, interval="5m", limit=500):
        rows = self._request(
            "GET", "/api/v3/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        return [
            {
                "open_time": int(r[0]),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[5]),
                "close_time": int(r[6]),
            }
            for r in rows
        ]

    def account_equity(self):
        self.connect()
        balances = self._request("GET", "/api/v3/account", signed=True)["balances"]
        usdt = next((x for x in balances if x["asset"] == "USDT"), None)
        if not usdt:
            return 0.0
        return float(usdt["free"]) + float(usdt["locked"])

    def positions(self):
        self.connect()
        balances = self._request("GET", "/api/v3/account", signed=True)["balances"]
        positions = []
        for b in balances:
            qty = float(b["free"]) + float(b["locked"])
            asset = b["asset"]
            if asset == "USDT" or qty <= 0:
                continue
            symbol = asset + "USDT"
            try:
                info = self.symbol_info(symbol)
                if info.get("status") != "TRADING":
                    continue
                positions.append({"asset": asset, "symbol": symbol, "quantity": qty})
            except Exception:
                continue
        return positions

    def _step_size(self, symbol):
        info = self.symbol_info(symbol)
        lot = next((f for f in info["filters"] if f["filterType"] == "LOT_SIZE"), None)
        if not lot:
            return Decimal("0.00000001")
        return Decimal(lot["stepSize"])

    def normalize_quantity(self, symbol, quantity):
        step = self._step_size(symbol)
        value = Decimal(str(quantity)).quantize(step, rounding=ROUND_DOWN)
        return float(value)

    def market_order(self, symbol, qty, side):
        if qty <= 0:
            raise ValueError("qty must be positive")
        if not SETTINGS.can_trade_live and SETTINGS.broker_mode == "live":
            raise RuntimeError("Live trading is blocked: set LIVE_TRADING_ENABLED=true explicitly")
        qty = self.normalize_quantity(symbol, qty)
        if qty <= 0:
            raise ValueError("quantity is below Binance minimum step size")
        return self._request(
            "POST", "/api/v3/order",
            {"symbol": symbol, "side": side.upper(), "type": "MARKET", "quantity": qty},
            signed=True,
        )

    def close_position(self, symbol, qty):
        return self.market_order(symbol, qty, "SELL")

    def last_price(self, symbol):
        data = self._request("GET", "/api/v3/ticker/price", {"symbol": symbol})
        return float(data["price"])
