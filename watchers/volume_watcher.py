from __future__ import annotations

from alerts import volume_spike
from notifier import TelegramNotifier
from scanner import PolymarketScanner
from state import StateStore


class VolumeWatcher:
    def __init__(
        self,
        scanner: PolymarketScanner,
        state: StateStore,
        notifier: TelegramNotifier,
        config: dict,
    ) -> None:
        self.scanner = scanner
        self.state = state
        self.notifier = notifier
        self.config = config
        self.spike_config = config.get("alerts", {}).get("volume_spike", {})

    def check_volumes(self) -> int:
        if not self.spike_config.get("enabled", True):
            return 0

        try:
            snapshots = self.scanner.scan()
        except Exception as exc:
            print(f"[volume] error fetching markets: {exc}")
            return 0

        seen_markets: set[str] = set()
        for snap in snapshots:
            if snap.market_id in seen_markets:
                continue
            seen_markets.add(snap.market_id)
            self.state.record_volume(snap.market_id, snap.volume)

        lookback_minutes = int(self.spike_config.get("lookback_minutes", 30))
        baseline_days = int(self.spike_config.get("baseline_days", 7))

        alerted = 0
        for snap in snapshots:
            if snap.market_id not in seen_markets:
                continue
            seen_markets.discard(snap.market_id)

            current = self.state.get_volume_window(snap.market_id, lookback_minutes)
            baseline = self.state.get_volume_baseline(
                snap.market_id, lookback_minutes, baseline_days
            )

            msg = volume_spike.evaluate(
                snap.market_name,
                snap.market_url,
                current,
                baseline,
                self.spike_config,
            )
            if msg:
                self.notifier.send(msg)
                alerted += 1

        self.state.prune_volume_history(baseline_days + 1)
        return alerted
