import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .config import SETTINGS

def setup_logging():
    Path("logs").mkdir(exist_ok=True)
    root = logging.getLogger()
    root.setLevel(getattr(logging, SETTINGS.log_level.upper(), logging.INFO))
    if not root.handlers:
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        fh = RotatingFileHandler("logs/bot.log", maxBytes=5_000_000, backupCount=7, encoding="utf-8")
        sh = logging.StreamHandler()
        fh.setFormatter(fmt); sh.setFormatter(fmt)
        root.addHandler(fh); root.addHandler(sh)
