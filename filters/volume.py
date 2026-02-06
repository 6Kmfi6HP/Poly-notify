from __future__ import annotations

from scanner import OutcomeSnapshot


def passes(outcome: OutcomeSnapshot, config: dict) -> bool:
    if not config.get("enabled", True):
        return True
    minimum = float(config.get("min_usd", 0))
    return outcome.volume >= minimum
