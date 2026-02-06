from __future__ import annotations

from datetime import datetime, timezone

from scanner import OutcomeSnapshot
from state import OutcomeState


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
    previous_price_pct = previous_price * 100
    current_price_pct = outcome.price * 100

    triggered = False
    if threshold_percent:
        triggered = triggered or abs(percent_change) >= threshold_percent
    if threshold_absolute is not None:
        triggered = triggered or abs(absolute_change) >= float(threshold_absolute)

    if not triggered:
        return None

    lines = ["⚡ Price spike"]
    if outcome.event_title and outcome.event_title != outcome.market_name:
        lines.append(f"Event: {outcome.event_title}")
    lines.extend(
        [
            f"Market: {outcome.market_name}",
            f"Outcome: {outcome.outcome_name}",
            f"Was: {previous_price_pct:.2f}% → Now: {current_price_pct:.2f}%",
            f"Δ%: {percent_change:+.2f}% (Δ {absolute_change:+.4f})",
            f"Link: {outcome.market_url}",
        ]
    )
    return "\n".join(lines)
