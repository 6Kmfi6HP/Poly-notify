from __future__ import annotations

from bot.scanner import OutcomeSnapshot
from bot.state import OutcomeState


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

    min_prob = float(probability_config.get("min", 0))
    max_prob = float(probability_config.get("max", 1))

    if existing_state.last_seen_price > max_prob and min_prob <= outcome.price <= max_prob:
        return (
            "🎯 Вход цены в диапазон\n"
            f"Маркет: {outcome.market_name}\n"
            f"Исход: {outcome.outcome_name}\n"
            f"Было: {existing_state.last_seen_price:.4f} → Стало: {outcome.price:.4f}\n"
            f"Диапазон: [{min_prob:.4f}, {max_prob:.4f}]\n"
            f"Ссылка: {outcome.market_url}"
        )
    return None
