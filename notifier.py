from __future__ import annotations

import requests


class TelegramNotifier:
    """Lightweight Telegram Bot API notifier."""

    def __init__(self, token: str, chat_id: str, enabled: bool = True) -> None:
        self.token = token
        self.chat_id = chat_id
        self.enabled = enabled
        self.session = requests.Session()

    def send(self, message: str) -> None:
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        response = self.session.post(url, json=payload, timeout=20)
        response.raise_for_status()
