import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from .config import SETTINGS


def connect():
    db_path = SETTINGS.database_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, event_type TEXT, symbol TEXT, payload TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_ts TEXT, exit_ts TEXT, symbol TEXT, qty REAL,
        entry REAL, exit REAL, stop REAL, pnl REAL, r_multiple REAL, status TEXT
    )""")
    db.commit()
    return db


def log_event(event_type, symbol=None, payload=None):
    db = connect()
    db.execute(
        "INSERT INTO events(ts,event_type,symbol,payload) VALUES(?,?,?,?)",
        (
            datetime.now(timezone.utc).isoformat(),
            event_type,
            symbol,
            json.dumps(payload or {}),
        ),
    )
    db.commit()
    db.close()
