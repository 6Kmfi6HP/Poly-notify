from __future__ import annotations

from filters.probability import _normalize_bounds
from scanner import OutcomeSnapshot
from state import OutcomeState


def evaluate(
    outcome: OutcomeSnapshot,
    existing_state: OutcomeState | None,
    config: dict,
    probability_config: dict,
) -> str | None:
    if not config.get("enabled", True):
        return None
    if existing_state is None or existing_state.last_seen_price is None:
        return None

    min_prob, max_prob = _normalize_bounds(probability_config)

    if existing_state.last_seen_price > max_prob and min_prob <= outcome.price <= max_prob:
        previous_price_pct = existing_state.last_seen_price * 100
        current_price_pct = outcome.price * 100
        min_prob_pct = min_prob * 100
        max_prob_pct = max_prob * 100
        lines = ["🎯 Price entered range"]
        if outcome.event_title and outcome.event_title != outcome.market_name:
            lines.append(f"Event: {outcome.event_title}")
        lines.extend(
            [
                f"Market: {outcome.market_name}",
                f"Outcome: {outcome.outcome_name}",
                f"Was: {previous_price_pct:.2f}% → Now: {current_price_pct:.2f}%",
                f"Range: [{min_prob_pct:.2f}%, {max_prob_pct:.2f}%]",
                f"Link: {outcome.market_url}",
            ]
        )
        return "\n".join(lines)
    return None
