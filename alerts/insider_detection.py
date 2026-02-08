from __future__ import annotations

from datetime import datetime, timezone


def evaluate(
    wallet: str,
    wallet_stats: dict,
    market_name: str,
    market_url: str,
    config: dict,
) -> str | None:
    """Return an alert message if *wallet* looks like an insider suspect, else ``None``.

    Parameters
    ----------
    wallet:
        The wallet address to evaluate.
    wallet_stats:
        Stats dict for this wallet with keys ``first_seen``, ``markets_traded``,
        ``total_volume``.
    market_name:
        Human-readable market name.
    market_url:
        Link to the market on Polymarket.
    config:
        Alert configuration.  Recognised keys:
        - ``enabled`` (bool, default ``True``)
        - ``new_wallet_age_hours`` (float, default ``24``)
        - ``single_market_focus`` (bool, default ``True``)
        - ``min_volume_usd`` (float, default ``5000``)
    """
    if not config.get("enabled", True):
        return None

    new_wallet_age_hours = float(config.get("new_wallet_age_hours", 24))
    single_market_focus = config.get("single_market_focus", True)
    min_volume_usd = float(config.get("min_volume_usd", 5000))

    first_seen: datetime | None = wallet_stats.get("first_seen")
    markets_traded: set = wallet_stats.get("markets_traded", set())
    total_volume: float = wallet_stats.get("total_volume", 0.0)

    if first_seen is None:
        return None

    now = datetime.now(timezone.utc)
    age_hours = (now - first_seen).total_seconds() / 3600

    if age_hours >= new_wallet_age_hours:
        return None
    if single_market_focus and len(markets_traded) > 1:
        return None
    if total_volume < min_volume_usd:
        return None

    wallet_display = f"{wallet[:10]}...{wallet[-4:]}" if len(wallet) > 14 else wallet

    lines = [
        "\U0001f575\ufe0f INSIDER SUSPECT",
        "",
        f"\u94b1\u5305: {wallet_display}",
        f"\u2022 \u521b\u5efa\u4e8e {age_hours:.0f} \u5c0f\u65f6\u524d",
        f"\u2022 \u53ea\u4ea4\u6613 {len(markets_traded)} \u4e2a\u5e02\u573a",
        f"\u2022 \u603b\u4ea4\u6613\u91cf: ${total_volume:,.0f}",
        "",
        f"\u5e02\u573a: {market_name}",
    ]

    if market_url:
        lines.append(f"\n\U0001f517 {market_url}")

    return "\n".join(lines)
