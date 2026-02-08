from __future__ import annotations

import time
from typing import Any

import requests

from alerts import insider_detection, whale_trade
from notifier import TelegramNotifier
from scanner import PolymarketScanner
from state import StateStore


class TradeWatcher:
    def __init__(
        self,
        scanner: PolymarketScanner,
        state: StateStore,
        notifier: TelegramNotifier,
        config: dict,
    ) -> None:
        self.scanner = scanner
        self.state = state
        self.notifier = notifier
        self.config = config
        self.session = requests.Session()

        api_config = config.get("api", {})
        self.clob_base_url = api_config.get(
            "clob_base_url", "https://clob.polymarket.com"
        ).rstrip("/")
        self.timeout_seconds = int(api_config.get("timeout_seconds", 30))
        self.max_retries = int(api_config.get("max_retries", 3))
        self.retry_backoff_seconds = float(api_config.get("retry_backoff_seconds", 2.0))

        self.whale_config = config.get("alerts", {}).get("whale_trade", {})
        self.insider_config = config.get("alerts", {}).get("insider_detection", {})
        self.wallet_tracking_enabled = config.get("wallet_tracking", {}).get(
            "enabled", True
        )

    def check_trades(self) -> int:
        whale_enabled = self.whale_config.get("enabled", True)
        insider_enabled = self.insider_config.get("enabled", True)

        if not whale_enabled and not insider_enabled:
            return 0

        try:
            snapshots = self.scanner.scan()
        except Exception as exc:
            print(f"[trade] error fetching markets: {exc}")
            return 0

        token_market_map = self._build_token_map(snapshots)
        if not token_market_map:
            return 0

        alerted = 0
        for token_id, market_info in token_market_map.items():
            trades = self._fetch_trades(token_id)
            for trade in trades:
                trade_id = str(trade.get("id") or trade.get("transaction_hash") or "")
                if not trade_id:
                    continue
                if self.state.has_processed_trade(trade_id):
                    continue

                trade["_market_name"] = market_info["name"]
                trade["_market_url"] = market_info["url"]

                wallet = trade.get("maker_address") or trade.get("taker_address") or ""
                usd_value = self._calc_usd_value(trade)

                if self.wallet_tracking_enabled and wallet:
                    wallet_stats = self.state.update_wallet(wallet, token_id, usd_value)

                    if insider_enabled and not self.state.has_insider_alerted(wallet):
                        msg = insider_detection.evaluate(
                            wallet,
                            wallet_stats,
                            market_info["name"],
                            market_info["url"],
                            self.insider_config,
                        )
                        if msg:
                            self.notifier.send(msg)
                            self.state.mark_insider_alerted(wallet)
                            alerted += 1

                if whale_enabled:
                    message = whale_trade.evaluate(trade, self.whale_config)
                    if message:
                        self.notifier.send(message)
                        alerted += 1

                self.state.add_processed_trade(trade_id)

        self.state.save()
        return alerted

    @staticmethod
    def _calc_usd_value(trade: dict) -> float:
        try:
            size = float(trade.get("size", 0))
            price = float(trade.get("price", 0))
        except (TypeError, ValueError):
            return 0.0
        return size * price

    @staticmethod
    def _build_token_map(snapshots: list) -> dict[str, dict[str, str]]:
        token_map: dict[str, dict[str, str]] = {}
        for snap in snapshots:
            if snap.outcome_id and snap.outcome_id not in token_map:
                token_map[snap.outcome_id] = {
                    "name": snap.market_name,
                    "url": snap.market_url,
                }
        return token_map

    def _fetch_trades(self, token_id: str) -> list[dict[str, Any]]:
        url = f"{self.clob_base_url}/trades"
        params: dict[str, str] = {"market": token_id}

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if attempt == 1:
                    print(f"[trade] GET {url} market={token_id[:16]}...")
                else:
                    print(
                        f"[trade] retry {attempt}/{self.max_retries} for trades market={token_id[:16]}..."
                    )
                response = self.session.get(
                    url, params=params, timeout=self.timeout_seconds
                )
                response.raise_for_status()
                data = response.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "trades" in data:
                    return data["trades"]
                return []
            except (requests.RequestException, ValueError, TypeError) as exc:
                last_error = exc
                print(f"[trade] trades error: {exc}")
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_backoff_seconds * attempt)

        if last_error:
            print(f"[trade] giving up on trades for {token_id[:16]}...: {last_error}")
        return []
