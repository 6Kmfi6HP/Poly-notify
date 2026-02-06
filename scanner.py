from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from typing import Any, Iterable

import requests


@dataclass(frozen=True)
class OutcomeSnapshot:
    outcome_id: str
    market_id: str
    market_name: str
    market_url: str
    event_title: str | None
    outcome_name: str
    price: float
    liquidity: float
    volume: float
    volume_24h: float
    resolution_time: datetime | None


class PolymarketScanner:
    """Fetches and normalizes Polymarket market data for downstream filters and alerts."""

    def __init__(
        self,
        base_url: str,
        markets_endpoint: str,
        active_only: bool = True,
        limit: int | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        retry_backoff_seconds: float = 2.0,
        use_clob_prices: bool = True,
        clob_base_url: str = "https://clob.polymarket.com",
        clob_price_side: str = "BUY",
        clob_batch_size: int = 200,
        exclude_review: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.markets_endpoint = markets_endpoint
        self.active_only = active_only
        self.limit = limit
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.use_clob_prices = use_clob_prices
        self.clob_base_url = clob_base_url.rstrip("/")
        self.clob_price_side = clob_price_side.upper()
        self.clob_batch_size = max(1, min(int(clob_batch_size), 500))
        self.exclude_review = exclude_review
        self.session = requests.Session()

    def fetch_active_markets(self) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if self.active_only:
            params["active"] = "true"
            params["closed"] = "false"
        if self.limit:
            params["limit"] = str(self.limit)
        print(f"[scan] GET {self.base_url}{self.markets_endpoint} params={params}")
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if attempt > 1:
                    print(f"[scan] retry {attempt}/{self.max_retries} for markets")
                response = self.session.get(
                    f"{self.base_url}{self.markets_endpoint}",
                    params=params,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and "markets" in data:
                    print(f"[scan] markets response: {len(data['markets'])} items (dict)")
                    return data["markets"]
                if isinstance(data, list):
                    print(f"[scan] markets response: {len(data)} items (list)")
                    return data
                print("[scan] markets response: empty/unknown shape")
                return []
            except requests.RequestException as exc:
                last_error = exc
                print(f"[scan] markets error: {exc}")
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds * attempt)
        if last_error:
            raise last_error
        return []

    def scan(self) -> list[OutcomeSnapshot]:
        markets = self.fetch_active_markets()
        snapshots: list[OutcomeSnapshot] = []
        for record in markets:
            if isinstance(record, dict) and isinstance(record.get("markets"), list):
                snapshots.extend(self._normalize_event(record))
            else:
                snapshots.extend(self._normalize_market(record))
        return snapshots

    def _normalize_event(self, event: dict[str, Any]) -> Iterable[OutcomeSnapshot]:
        if self.exclude_review and self._is_review_stage(event):
            return []
        event_slug = event.get("slug") or event.get("url") or ""
        event_title = event.get("title") or event.get("question") or ""
        resolution_time = self._parse_datetime(
            event.get("resolutionTime")
            or event.get("resolvedAt")
            or event.get("endDate")
            or event.get("closeTime")
        )

        for market in event.get("markets", []):
            if self.exclude_review and self._is_review_stage(market):
                continue
            market_id = str(market.get("id") or market.get("marketId") or "")
            market_name = market.get("question") or market.get("title") or event_title or ""
            slug = market.get("slug") or event_slug or ""
            market_url = slug if slug.startswith("http") else f"https://polymarket.com/market/{slug}" if slug else ""
            market_resolution = self._parse_datetime(
                market.get("resolutionTime")
                or market.get("resolvedAt")
                or market.get("endDate")
                or market.get("closeTime")
            )
            market_resolution = market_resolution or resolution_time

            outcomes = self._parse_json_list(market.get("outcomes"))
            outcome_prices = self._parse_json_list(market.get("outcomePrices"))
            token_ids = self._parse_json_list(market.get("clobTokenIds") or market.get("tokenIds"))

            liquidity = float(market.get("liquidity") or event.get("liquidity") or 0.0)
            volume_total = float(market.get("volume") or event.get("volume") or 0.0)
            volume_24h = float(market.get("volume24h") or event.get("volume24h") or 0.0)

            token_id_strings = [str(token_id) for token_id in token_ids if token_id is not None]
            clob_prices = (
                self._fetch_clob_prices(token_id_strings) if self.use_clob_prices and token_id_strings else {}
            )

            for index, outcome_name in enumerate(outcomes):
                price = 0.0
                if index < len(outcome_prices):
                    try:
                        price = float(outcome_prices[index])
                    except (TypeError, ValueError):
                        price = 0.0
                outcome_id = ""
                if index < len(token_ids):
                    outcome_id = str(token_ids[index])
                if not outcome_id:
                    outcome_id = f"{market_id}:{outcome_name}"
                if self.use_clob_prices and outcome_id in clob_prices:
                    price = clob_prices[outcome_id]

                yield OutcomeSnapshot(
                    outcome_id=outcome_id,
                    market_id=market_id,
                    market_name=market_name,
                    market_url=market_url,
                    event_title=event_title or None,
                    outcome_name=str(outcome_name),
                    price=price,
                    liquidity=liquidity,
                    volume=volume_total,
                    volume_24h=volume_24h,
                    resolution_time=market_resolution,
                )

    def _normalize_market(self, market: dict[str, Any]) -> Iterable[OutcomeSnapshot]:
        if self.exclude_review and self._is_review_stage(market):
            return []
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

        outcomes_raw = market.get("outcomes") or []
        if outcomes_raw and isinstance(outcomes_raw[0], dict):
            token_ids = [
                str(outcome.get("id") or outcome.get("outcomeId") or outcome.get("tokenId") or "")
                for outcome in outcomes_raw
                if outcome.get("id") or outcome.get("outcomeId") or outcome.get("tokenId")
            ]
            clob_prices = (
                self._fetch_clob_prices(token_ids) if self.use_clob_prices and token_ids else {}
            )
            for outcome in outcomes_raw:
                outcome_id = str(outcome.get("id") or outcome.get("outcomeId") or outcome.get("tokenId") or "")
                price = self._extract_price(outcome)
                liquidity = float(outcome.get("liquidity") or market.get("liquidity") or 0.0)
                volume_total = float(outcome.get("volume") or market.get("volume") or 0.0)
                volume_24h = float(outcome.get("volume24h") or market.get("volume24h") or 0.0)
                outcome_name = outcome.get("name") or outcome.get("title") or outcome.get("label") or ""

                if not outcome_id:
                    outcome_id = f"{market_id}:{outcome_name}"
                if self.use_clob_prices and outcome_id in clob_prices:
                    price = clob_prices[outcome_id]

            yield OutcomeSnapshot(
                outcome_id=outcome_id,
                market_id=market_id,
                market_name=market_name,
                market_url=market_url,
                event_title=None,
                outcome_name=outcome_name,
                price=price,
                liquidity=liquidity,
                volume=volume_total,
                    volume_24h=volume_24h,
                    resolution_time=resolution_time,
                )
            return

        outcomes = self._parse_json_list(outcomes_raw)
        outcome_prices = self._parse_json_list(market.get("outcomePrices"))
        token_ids = self._parse_json_list(market.get("clobTokenIds") or market.get("tokenIds"))
        token_id_strings = [str(token_id) for token_id in token_ids if token_id is not None]
        clob_prices = (
            self._fetch_clob_prices(token_id_strings) if self.use_clob_prices and token_id_strings else {}
        )
        liquidity = float(market.get("liquidity") or 0.0)
        volume_total = float(market.get("volume") or 0.0)
        volume_24h = float(market.get("volume24h") or 0.0)

        for index, outcome_name in enumerate(outcomes):
            price = 0.0
            if index < len(outcome_prices):
                try:
                    price = float(outcome_prices[index])
                except (TypeError, ValueError):
                    price = 0.0
            outcome_id = ""
            if index < len(token_ids):
                outcome_id = str(token_ids[index])
            if not outcome_id:
                outcome_id = f"{market_id}:{outcome_name}"
            if self.use_clob_prices and outcome_id in clob_prices:
                price = clob_prices[outcome_id]

            yield OutcomeSnapshot(
                outcome_id=outcome_id,
                market_id=market_id,
                market_name=market_name,
                market_url=market_url,
                event_title=None,
                outcome_name=str(outcome_name),
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

    def _fetch_clob_prices(self, token_ids: list[str]) -> dict[str, float]:
        if not token_ids:
            return {}
        prices: dict[str, float] = {}
        for start in range(0, len(token_ids), self.clob_batch_size):
            batch = token_ids[start : start + self.clob_batch_size]
            payload = [{"token_id": token_id, "side": self.clob_price_side} for token_id in batch]
            last_error: Exception | None = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    if attempt == 1:
                        print(f"[scan] POST {self.clob_base_url}/prices batch={len(batch)}")
                    else:
                        print(f"[scan] retry {attempt}/{self.max_retries} for clob prices batch={len(batch)}")
                    response = self.session.post(
                        f"{self.clob_base_url}/prices",
                        json=payload,
                        timeout=self.timeout_seconds,
                    )
                    response.raise_for_status()
                    data = response.json()
                    if isinstance(data, dict):
                        for token_id, sides in data.items():
                            if isinstance(sides, dict) and self.clob_price_side in sides:
                                try:
                                    prices[str(token_id)] = float(sides[self.clob_price_side])
                                except (TypeError, ValueError):
                                    continue
                    print(f"[scan] clob prices received: {len(prices)}")
                    break
                except (requests.RequestException, ValueError, TypeError) as exc:
                    last_error = exc
                    print(f"[scan] clob prices error: {exc}")
                    if attempt >= self.max_retries:
                        break
                    time.sleep(self.retry_backoff_seconds * attempt)
            if last_error:
                continue
        return prices

    @staticmethod
    def _is_review_stage(payload: dict[str, Any]) -> bool:
        for key in ("status", "marketStatus", "phase", "resolutionStatus", "reviewStatus"):
            value = payload.get(key)
            if isinstance(value, str) and "review" in value.lower():
                return True
        for key in ("isReviewing", "inReview", "reviewing", "in_review"):
            value = payload.get(key)
            if isinstance(value, bool) and value:
                return True
        return False

    @staticmethod
    def _parse_json_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
        return []

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
