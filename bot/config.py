import json
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parents[1]


def load_rules():
    with open(ROOT / "config" / "rules.json", encoding="utf-8") as f:
        return json.load(f)


@dataclass(frozen=True)
class Settings:
    broker_mode: str = os.getenv("BROKER_MODE", "paper").lower()
    live_enabled: bool = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
    binance_api_key: str = os.getenv("BINANCE_API_KEY", "")
    binance_api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    binance_testnet: bool = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    binance_recv_window: int = int(os.getenv("BINANCE_RECV_WINDOW", "5000"))
    database_path: str = os.getenv("DATABASE_PATH", "data/trading.db")
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def can_trade_live(self):
        return self.broker_mode == "live" and self.live_enabled


SETTINGS = Settings()
RULES = load_rules()

if SETTINGS.broker_mode not in {"paper", "live"}:
    raise ValueError("BROKER_MODE must be paper or live")

if SETTINGS.broker_mode == "live" and not SETTINGS.live_enabled:
    # Live API access is allowed for account/market-data checks, but order
    # submission is blocked unless both flags are explicitly enabled.
    pass
