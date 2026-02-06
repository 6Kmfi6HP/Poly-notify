from __future__ import annotations

from bot.scanner import OutcomeSnapshot
from bot.state import OutcomeState


def evaluate(outcome: OutcomeSnapshot, existing_state: OutcomeState | None, config: dict) -> str | None:
    if not config.get("enabled", True):
        return None
    if existing_state is not None:
        return None
    return (
        "🆕 Новый рынок под фильтрами\n"
        f"Маркет: {outcome.market_name}\n"
        f"Исход: {outcome.outcome_name}\n"
        f"Цена: {outcome.price:.4f}\n"
        f"Ликвидность: ${outcome.liquidity:,.2f}\n"
        f"Объём: ${outcome.volume:,.2f}\n"
        f"Ссылка: {outcome.market_url}"
    )
