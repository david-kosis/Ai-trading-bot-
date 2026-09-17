import requests
from .config import SETTINGS

def send(text):
    if not SETTINGS.telegram_token or not SETTINGS.telegram_chat_id:
        return
    url = f"https://api.telegram.org/bot{SETTINGS.telegram_token}/sendMessage"
    requests.post(url, json={"chat_id": SETTINGS.telegram_chat_id, "text": text}, timeout=10).raise_for_status()
