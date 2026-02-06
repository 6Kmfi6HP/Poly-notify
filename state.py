from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class OutcomeState:
    outcome_id: str
    last_seen_price: float | None = None
    last_seen_timestamp: datetime | None = None
    last_alerted_timestamp: datetime | None = None
    first_seen_timestamp: datetime | None = None


class StateStore:
    """Persists outcome state to avoid duplicate alerts and track recent prices."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._state: dict[str, OutcomeState] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text())
        for outcome_id, payload in raw.items():
            self._state[outcome_id] = OutcomeState(
                outcome_id=outcome_id,
                last_seen_price=payload.get("last_seen_price"),
                last_seen_timestamp=self._parse_datetime(payload.get("last_seen_timestamp")),
                last_alerted_timestamp=self._parse_datetime(payload.get("last_alerted_timestamp")),
                first_seen_timestamp=self._parse_datetime(payload.get("first_seen_timestamp")),
            )

    def save(self) -> None:
        payload: dict[str, Any] = {}
        for outcome_id, state in self._state.items():
            payload[outcome_id] = {
                "last_seen_price": state.last_seen_price,
                "last_seen_timestamp": self._format_datetime(state.last_seen_timestamp),
                "last_alerted_timestamp": self._format_datetime(state.last_alerted_timestamp),
                "first_seen_timestamp": self._format_datetime(state.first_seen_timestamp),
            }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    def get(self, outcome_id: str) -> OutcomeState | None:
        return self._state.get(outcome_id)

    def upsert(self, outcome_id: str, price: float) -> OutcomeState:
        now = datetime.now(timezone.utc)
        state = self._state.get(outcome_id)
        if state is None:
            state = OutcomeState(outcome_id=outcome_id, first_seen_timestamp=now)
            self._state[outcome_id] = state
        state.last_seen_price = price
        state.last_seen_timestamp = now
        return state

    def mark_alerted(self, outcome_id: str) -> None:
        state = self._state.get(outcome_id)
        if state is None:
            return
        state.last_alerted_timestamp = datetime.now(timezone.utc)

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value)

    @staticmethod
    def _format_datetime(value: datetime | None) -> str | None:
        if not value:
            return None
        return value.isoformat()
