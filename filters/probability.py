from __future__ import annotations

from scanner import OutcomeSnapshot


def _normalize_bounds(config: dict) -> tuple[float, float]:
    minimum = float(config.get("min", 0))
    maximum = float(config.get("max", 1))
    if minimum > 1 or maximum > 1:
        return minimum / 100.0, maximum / 100.0
    return minimum, maximum


def passes(outcome: OutcomeSnapshot, config: dict) -> bool:
    if not config.get("enabled", True):
        return True
    minimum, maximum = _normalize_bounds(config)
    return minimum <= outcome.price <= maximum
