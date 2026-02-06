from __future__ import annotations

from datetime import datetime, timezone

from bot.scanner import OutcomeSnapshot


def passes(outcome: OutcomeSnapshot, config: dict) -> bool:
    if not config.get("enabled", True):
        return True
    if outcome.resolution_time is None:
        return False
    now = datetime.now(timezone.utc)
    delta = outcome.resolution_time - now
    days = delta.total_seconds() / 86400
    min_days = float(config.get("min_days", 0))
    max_days = float(config.get("max_days", 36500))
    return min_days <= days <= max_days
