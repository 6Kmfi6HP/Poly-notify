from __future__ import annotations

from bot.scanner import OutcomeSnapshot


def passes(outcome: OutcomeSnapshot, config: dict) -> bool:
    if not config.get("enabled", True):
        return True
    minimum = float(config.get("min", 0))
    maximum = float(config.get("max", 1))
    return minimum <= outcome.price <= maximum
