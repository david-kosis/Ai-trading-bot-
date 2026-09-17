import json, os
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
    ib_host: str = os.getenv("IBKR_HOST", "127.0.0.1")
    ib_port: int = int(os.getenv("IBKR_PORT", "7497"))
    scan_client_id: int = int(os.getenv("IBKR_SCAN_CLIENT_ID", "71"))
    exec_client_id: int = int(os.getenv("IBKR_EXEC_CLIENT_ID", "72"))
    db_path: str = os.getenv("DATABASE_PATH", "data/trading.db")
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
