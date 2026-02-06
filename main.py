from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from alerts import new_market, price_spike, range_entry
from filters import liquidity, probability, time_to_resolution, volume
from notifier import TelegramNotifier
from scanner import OutcomeSnapshot, PolymarketScanner
from state import StateStore


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
    try:
        print("[scan] fetching markets...")
        snapshots = scanner.scan()
    except Exception as exc:
        print(f"[scan] error: {exc}")
        return
    print(f"[scan] outcomes: {len(snapshots)}")
    filters_config = config.get("filters", {})

    alerted = 0
    new_market_enabled = config.get("alerts", {}).get("new_market", {}).get("enabled", True)
    new_market_groups: dict[str, list[OutcomeSnapshot]] = {}
    for outcome in snapshots:
        existing_state = state.get(outcome.outcome_id)
        if not passes_filters(outcome, filters_config):
            state.upsert(outcome.outcome_id, outcome.price)
            continue

        if new_market_enabled and existing_state is None:
            group_key = outcome.event_title or outcome.market_id
            new_market_groups.setdefault(group_key, []).append(outcome)
            state.upsert(outcome.outcome_id, outcome.price)
            continue

        for message in build_alerts(outcome, existing_state, config):
            notifier.send(message)
            state.mark_alerted(outcome.outcome_id)
            alerted += 1

        state.upsert(outcome.outcome_id, outcome.price)

    for outcomes in new_market_groups.values():
        if not outcomes:
            continue
        first = outcomes[0]
        lines = ["🆕 New market(s) matched"]
        if first.event_title:
            lines.append(f"Event: {first.event_title}")
        lines.append("Market(s):")
        for outcome in outcomes:
            lines.append(f"- {outcome.market_name}: {outcome.outcome_name} {outcome.price * 100:.2f}%")
        lines.append(f"Liquidity (market): ${first.liquidity:,.2f}")
        lines.append(f"Volume (market): ${first.volume:,.2f}")
        lines.append(f"Link: {first.market_url}")
        notifier.send("\n".join(lines))
        for outcome in outcomes:
            state.mark_alerted(outcome.outcome_id)
        alerted += 1

    state.save()
    print(f"[scan] alerts sent: {alerted}")


def main() -> None:
    config = load_config("config.yaml")
    api_config = config.get("api", {})
    scanner = PolymarketScanner(
        base_url=api_config.get("base_url", "https://gamma-api.polymarket.com"),
        markets_endpoint=api_config.get("markets_endpoint", "/events"),
        active_only=api_config.get("active_only", True),
        limit=api_config.get("limit"),
        timeout_seconds=int(api_config.get("timeout_seconds", 30)),
        max_retries=int(api_config.get("max_retries", 3)),
        retry_backoff_seconds=float(api_config.get("retry_backoff_seconds", 2.0)),
        use_clob_prices=bool(api_config.get("use_clob_prices", True)),
        clob_base_url=api_config.get("clob_base_url", "https://clob.polymarket.com"),
        clob_price_side=api_config.get("clob_price_side", "BUY"),
        clob_batch_size=int(api_config.get("clob_batch_size", 200)),
        exclude_review=bool(api_config.get("exclude_review", True)),
    )
    state_path = config.get("state", {}).get("path", "state.json")
    state = StateStore(Path(state_path))

    telegram_config = config.get("telegram", {})
    output_config = config.get("output", {})
    notifier = TelegramNotifier(
        token=telegram_config.get("token", ""),
        chat_id=telegram_config.get("chat_id", ""),
        enabled=telegram_config.get("enabled", False),
        output_enabled=output_config.get("enabled", False),
        output_path=output_config.get("path", "alerts.log"),
    )

    scan_interval = int(config.get("scan_interval_seconds", 300))
    print(f"[boot] scan interval: {scan_interval}s")

    while True:
        start = datetime.now(timezone.utc)
        print(f"[loop] start: {start.isoformat()}")
        run_once(config, scanner, state, notifier)
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        sleep_for = max(0, scan_interval - elapsed)
        print(f"[loop] done in {elapsed:.2f}s, sleep {sleep_for:.2f}s")
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
