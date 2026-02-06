from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import requests


@dataclass(frozen=True)
class OutcomeSnapshot:
    outcome_id: str
    market_id: str
    market_name: str
    market_url: str
    outcome_name: str
    price: float
    liquidity: float
    volume: float
    volume_24h: float
    resolution_time: datetime | None


class PolymarketScanner:
    """Fetches and normalizes Polymarket market data for downstream filters and alerts."""

    def __init__(self, base_url: str, markets_endpoint: str, active_only: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self.markets_endpoint = markets_endpoint
        self.active_only = active_only
        self.session = requests.Session()

    def fetch_active_markets(self) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if self.active_only:
            params["active"] = "true"
        response = self.session.get(f"{self.base_url}{self.markets_endpoint}", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "markets" in data:
            return data["markets"]
        if isinstance(data, list):
            return data
        return []

    def scan(self) -> list[OutcomeSnapshot]:
        markets = self.fetch_active_markets()
        snapshots: list[OutcomeSnapshot] = []
        for market in markets:
            snapshots.extend(self._normalize_market(market))
        return snapshots

    def _normalize_market(self, market: dict[str, Any]) -> Iterable[OutcomeSnapshot]:
        market_id = str(market.get("id") or market.get("marketId") or "")
        market_name = market.get("question") or market.get("title") or market.get("name") or ""
        slug = market.get("slug") or market.get("url") or ""
        market_url = slug if slug.startswith("http") else f"https://polymarket.com/market/{slug}" if slug else ""
        resolution_time = self._parse_datetime(
            market.get("resolutionTime")
            or market.get("resolvedAt")
            or market.get("endDate")
            or market.get("closeTime")
        )

        outcomes = market.get("outcomes") or []
        for outcome in outcomes:
            outcome_id = str(outcome.get("id") or outcome.get("outcomeId") or outcome.get("tokenId") or "")
            price = self._extract_price(outcome)
            liquidity = float(outcome.get("liquidity") or market.get("liquidity") or 0.0)
            volume_total = float(outcome.get("volume") or market.get("volume") or 0.0)
            volume_24h = float(outcome.get("volume24h") or market.get("volume24h") or 0.0)
            outcome_name = outcome.get("name") or outcome.get("title") or outcome.get("label") or ""

            if not outcome_id:
                outcome_id = f"{market_id}:{outcome_name}"

            yield OutcomeSnapshot(
                outcome_id=outcome_id,
                market_id=market_id,
                market_name=market_name,
                market_url=market_url,
                outcome_name=outcome_name,
                price=price,
                liquidity=liquidity,
                volume=volume_total,
                volume_24h=volume_24h,
                resolution_time=resolution_time,
            )

    @staticmethod
    def _extract_price(outcome: dict[str, Any]) -> float:
        for key in ("bestAsk", "best_ask", "clobBestAsk", "bestAskPrice"):
            if key in outcome and outcome[key] is not None:
                return float(outcome[key])
        for key in ("price", "midpoint", "mid", "lastPrice"):
            if key in outcome and outcome[key] is not None:
                return float(outcome[key])
        return 0.0

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str):
            cleaned = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(cleaned)
            except ValueError:
                return None
        return None
