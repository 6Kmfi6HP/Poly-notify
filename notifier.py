from __future__ import annotations

from pathlib import Path

import requests


class TelegramNotifier:
    """Lightweight Telegram Bot API notifier with optional file output."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        enabled: bool = True,
        output_enabled: bool = False,
        output_path: str | None = None,
    ) -> None:
        self.token = token
        self.chat_id = chat_id
        self.enabled = enabled
        self.output_enabled = output_enabled
        self.output_path = Path(output_path) if output_path else None
        self.session = requests.Session()

    def send(self, message: str) -> None:
        if self.output_enabled and self.output_path:
            self._append_to_file(message)
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

    def _append_to_file(self, message: str) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(message)
            handle.write("\n\n")
