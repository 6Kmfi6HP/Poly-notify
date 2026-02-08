from __future__ import annotations


def evaluate(
    market_name: str,
    market_url: str,
    current_volume: float,
    baseline_volume: float,
    config: dict,
) -> str | None:
    """Return an alert message if current volume represents a spike, else ``None``.

    Parameters
    ----------
    market_name:
        Human-readable market name.
    market_url:
        Link to the market on Polymarket.
    current_volume:
        Volume in the most recent window (e.g. last 30 minutes) in USD.
    baseline_volume:
        Average volume per window over the baseline period in USD.
    config:
        Alert configuration.  Recognised keys:
        - ``enabled`` (bool, default ``True``)
        - ``percent_change`` (float, default ``200``)
    """
    if not config.get("enabled", True):
        return None

    percent_threshold = float(config.get("percent_change", 200))

    if baseline_volume <= 0:
        return None

    percent_change = ((current_volume - baseline_volume) / baseline_volume) * 100

    if percent_change < percent_threshold:
        return None

    lines = [
        f"\U0001f4ca VOLUME SPIKE +{percent_change:.0f}%",
        "",
        f"\u5e02\u573a: {market_name}",
        f"\u2022 \u8fc7\u53bb30\u5206\u949f: ${current_volume:,.0f}",
        f"\u2022 \u5e73\u574730\u5206\u949f: ${baseline_volume:,.0f}",
    ]

    if market_url:
        lines.append(f"\n\U0001f517 {market_url}")

    return "\n".join(lines)
