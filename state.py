from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_MAX_PROCESSED_TRADES = 50_000
_MAX_WALLETS = 100_000


@dataclass
class OutcomeState:
    outcome_id: str
    last_seen_price: float | None = None
    last_seen_timestamp: datetime | None = None
    last_alerted_timestamp: datetime | None = None
    first_seen_timestamp: datetime | None = None


class StateStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._state: dict[str, OutcomeState] = {}
        self._processed_trades: deque[str] = deque(maxlen=_MAX_PROCESSED_TRADES)
        self._processed_trades_set: set[str] = set()

        self._wallet_stats: dict[str, dict[str, Any]] = {}
        self._insider_alerted: set[str] = set()

        self._volume_history: dict[str, list[tuple[datetime, float]]] = {}

        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text())

        if isinstance(raw, dict) and "outcomes" in raw:
            outcomes = raw["outcomes"]
            for trade_id in raw.get("_processed_trades", []):
                self._processed_trades.append(str(trade_id))
                self._processed_trades_set.add(str(trade_id))
        else:
            outcomes = raw

        for outcome_id, payload in outcomes.items():
            self._state[outcome_id] = OutcomeState(
                outcome_id=outcome_id,
                last_seen_price=payload.get("last_seen_price"),
                last_seen_timestamp=self._parse_datetime(
                    payload.get("last_seen_timestamp")
                ),
                last_alerted_timestamp=self._parse_datetime(
                    payload.get("last_alerted_timestamp")
                ),
                first_seen_timestamp=self._parse_datetime(
                    payload.get("first_seen_timestamp")
                ),
            )

    def save(self) -> None:
        outcomes: dict[str, Any] = {}
        for outcome_id, state in self._state.items():
            outcomes[outcome_id] = {
                "last_seen_price": state.last_seen_price,
                "last_seen_timestamp": self._format_datetime(state.last_seen_timestamp),
                "last_alerted_timestamp": self._format_datetime(
                    state.last_alerted_timestamp
                ),
                "first_seen_timestamp": self._format_datetime(
                    state.first_seen_timestamp
                ),
            }
        payload: dict[str, Any] = {
            "outcomes": outcomes,
            "_processed_trades": list(self._processed_trades),
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

    def has_processed_trade(self, trade_id: str) -> bool:
        return trade_id in self._processed_trades_set

    def add_processed_trade(self, trade_id: str) -> None:
        if trade_id in self._processed_trades_set:
            return
        if len(self._processed_trades) == self._processed_trades.maxlen:
            evicted = self._processed_trades[0]
            self._processed_trades_set.discard(evicted)
        self._processed_trades.append(trade_id)
        self._processed_trades_set.add(trade_id)

    def update_wallet(
        self, address: str, token_id: str, usd_value: float
    ) -> dict[str, Any]:
        if not address:
            return {}
        stats = self._wallet_stats.get(address)
        if stats is None:
            stats = {
                "first_seen": datetime.now(timezone.utc),
                "markets_traded": set(),
                "total_volume": 0.0,
            }
            self._wallet_stats[address] = stats
        stats["markets_traded"].add(token_id)
        stats["total_volume"] += usd_value
        self._evict_old_wallets()
        return stats

    def get_wallet_stats(self, address: str) -> dict[str, Any] | None:
        return self._wallet_stats.get(address)

    def has_insider_alerted(self, address: str) -> bool:
        return address in self._insider_alerted

    def mark_insider_alerted(self, address: str) -> None:
        self._insider_alerted.add(address)

    def _evict_old_wallets(self) -> None:
        if len(self._wallet_stats) <= _MAX_WALLETS:
            return
        sorted_addrs = sorted(
            self._wallet_stats,
            key=lambda a: self._wallet_stats[a]["first_seen"],
        )
        to_remove = len(self._wallet_stats) - _MAX_WALLETS
        for addr in sorted_addrs[:to_remove]:
            del self._wallet_stats[addr]
            self._insider_alerted.discard(addr)

    def record_volume(self, market_id: str, volume: float) -> None:
        now = datetime.now(timezone.utc)
        history = self._volume_history.setdefault(market_id, [])
        history.append((now, volume))

    def get_volume_window(self, market_id: str, window_minutes: int = 30) -> float:
        history = self._volume_history.get(market_id)
        if not history or len(history) < 2:
            return 0.0
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        recent = [(ts, vol) for ts, vol in history if ts >= cutoff]
        if not recent:
            return 0.0
        return recent[-1][1] - recent[0][1]

    def get_volume_baseline(
        self, market_id: str, window_minutes: int = 30, baseline_days: int = 7
    ) -> float:
        history = self._volume_history.get(market_id)
        if not history or len(history) < 2:
            return 0.0
        now = datetime.now(timezone.utc)
        baseline_start = now - timedelta(days=baseline_days)
        window_start = now - timedelta(minutes=window_minutes)
        baseline_points = [
            (ts, vol) for ts, vol in history if baseline_start <= ts < window_start
        ]
        if len(baseline_points) < 2:
            return 0.0
        total_span = (baseline_points[-1][0] - baseline_points[0][0]).total_seconds()
        if total_span <= 0:
            return 0.0
        total_volume_change = baseline_points[-1][1] - baseline_points[0][1]
        if total_volume_change <= 0:
            return 0.0
        window_seconds = window_minutes * 60
        num_windows = total_span / window_seconds
        if num_windows <= 0:
            return 0.0
        return total_volume_change / num_windows

    def prune_volume_history(self, retention_days: int = 8) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        for market_id in list(self._volume_history):
            self._volume_history[market_id] = [
                (ts, vol) for ts, vol in self._volume_history[market_id] if ts >= cutoff
            ]
            if not self._volume_history[market_id]:
                del self._volume_history[market_id]

    def prune_wallets(self, retention_days: int = 30) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        for addr in list(self._wallet_stats):
            if self._wallet_stats[addr]["first_seen"] < cutoff:
                del self._wallet_stats[addr]
                self._insider_alerted.discard(addr)

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
