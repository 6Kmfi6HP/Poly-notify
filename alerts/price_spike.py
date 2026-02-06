from __future__ import annotations

from datetime import datetime, timezone

from bot.scanner import OutcomeSnapshot
from bot.state import OutcomeState


def evaluate(outcome: OutcomeSnapshot, existing_state: OutcomeState | None, config: dict) -> str | None:
    if not config.get("enabled", True):
        return None
    if existing_state is None or existing_state.last_seen_price is None or existing_state.last_seen_timestamp is None:
        return None

    lookback_minutes = float(config.get("lookback_minutes", 60))
    threshold_percent = float(config.get("percent_change", 0))
    threshold_absolute = config.get("absolute_change")

    now = datetime.now(timezone.utc)
    age_minutes = (now - existing_state.last_seen_timestamp).total_seconds() / 60
    if age_minutes > lookback_minutes:
        return None

    previous_price = existing_state.last_seen_price
    if previous_price == 0:
        return None

    percent_change = ((outcome.price - previous_price) / previous_price) * 100
    absolute_change = outcome.price - previous_price

    triggered = False
    if threshold_percent:
        triggered = triggered or abs(percent_change) >= threshold_percent
    if threshold_absolute is not None:
        triggered = triggered or abs(absolute_change) >= float(threshold_absolute)

    if not triggered:
        return None

    return (
        "⚡ Резкое изменение цены\n"
        f"Маркет: {outcome.market_name}\n"
        f"Исход: {outcome.outcome_name}\n"
        f"Было: {previous_price:.4f} → Стало: {outcome.price:.4f}\n"
        f"Δ%: {percent_change:+.2f}% (Δ {absolute_change:+.4f})\n"
        f"Ссылка: {outcome.market_url}"
    )
