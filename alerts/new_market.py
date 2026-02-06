from __future__ import annotations

from scanner import OutcomeSnapshot
from state import OutcomeState


def evaluate(outcome: OutcomeSnapshot, existing_state: OutcomeState | None, config: dict) -> str | None:
    if not config.get("enabled", True):
        return None
    if existing_state is not None:
        return None
    price_pct = outcome.price * 100
    lines = ["🆕 New market matched"]
    if outcome.event_title and outcome.event_title != outcome.market_name:
        lines.append(f"Event: {outcome.event_title}")
    lines.extend(
        [
            f"Market: {outcome.market_name}",
            f"Outcome: {outcome.outcome_name}",
            f"Price: {price_pct:.2f}%",
            f"Liquidity: ${outcome.liquidity:,.2f}",
            f"Volume: ${outcome.volume:,.2f}",
            f"Link: {outcome.market_url}",
        ]
    )
    return "\n".join(lines)
