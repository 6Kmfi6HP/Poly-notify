from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from bot.alerts import new_market, price_spike, range_entry
from bot.filters import liquidity, probability, time_to_resolution, volume
from bot.notifier import TelegramNotifier
from bot.scanner import OutcomeSnapshot, PolymarketScanner
from bot.state import StateStore


def load_config(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text())


def passes_filters(outcome: OutcomeSnapshot, filters_config: dict) -> bool:
    return all(
        (
            probability.passes(outcome, filters_config.get("probability", {})),
            time_to_resolution.passes(outcome, filters_config.get("time_to_resolution", {})),
            liquidity.passes(outcome, filters_config.get("liquidity", {})),
            volume.passes(outcome, filters_config.get("volume", {})),
        )
    )


def build_alerts(
    outcome: OutcomeSnapshot,
    existing_state,
    config: dict,
) -> Iterable[str]:
    alerts_config = config.get("alerts", {})
    probability_config = config.get("filters", {}).get("probability", {})

    for message in (
        new_market.evaluate(outcome, existing_state, alerts_config.get("new_market", {})),
        price_spike.evaluate(outcome, existing_state, alerts_config.get("price_spike", {})),
        range_entry.evaluate(outcome, existing_state, alerts_config.get("range_entry", {}), probability_config),
    ):
        if message:
            yield message


def run_once(config: dict, scanner: PolymarketScanner, state: StateStore, notifier: TelegramNotifier) -> None:
    snapshots = scanner.scan()
    filters_config = config.get("filters", {})

    for outcome in snapshots:
        existing_state = state.get(outcome.outcome_id)
        if not passes_filters(outcome, filters_config):
            state.upsert(outcome.outcome_id, outcome.price)
            continue

        for message in build_alerts(outcome, existing_state, config):
            notifier.send(message)
            state.mark_alerted(outcome.outcome_id)

        state.upsert(outcome.outcome_id, outcome.price)

    state.save()


def main() -> None:
    config = load_config("bot/config.yaml")
    api_config = config.get("api", {})
    scanner = PolymarketScanner(
        base_url=api_config.get("base_url", "https://polymarket.com/api"),
        markets_endpoint=api_config.get("markets_endpoint", "/markets"),
        active_only=api_config.get("active_only", True),
    )
    state_path = config.get("state", {}).get("path", "state.json")
    state = StateStore(Path("bot") / state_path)

    telegram_config = config.get("telegram", {})
    notifier = TelegramNotifier(
        token=telegram_config.get("token", ""),
        chat_id=telegram_config.get("chat_id", ""),
        enabled=telegram_config.get("enabled", False),
    )

    scan_interval = int(config.get("scan_interval_seconds", 300))

    while True:
        start = datetime.now(timezone.utc)
        run_once(config, scanner, state, notifier)
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        sleep_for = max(0, scan_interval - elapsed)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
