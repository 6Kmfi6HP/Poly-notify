from __future__ import annotations


def evaluate(trade: dict, config: dict) -> str | None:
    """Return an alert message if *trade* qualifies as a whale trade, else ``None``.

    Parameters
    ----------
    trade:
        A single trade dict from the CLOB ``/trades`` endpoint.
        Expected keys: ``size``, ``price``, ``side``, ``maker_address``,
        ``market`` (token_id), ``id`` or ``transaction_hash``.
    config:
        Alert configuration.  Recognised keys:
        - ``enabled`` (bool, default ``True``)
        - ``min_usd`` (float, default ``10000``)
        - ``notify_new_wallet`` (bool, default ``True``)
    """
    if not config.get("enabled", True):
        return None

    min_usd = float(config.get("min_usd", 10000))

    try:
        size = float(trade.get("size", 0))
        price = float(trade.get("price", 0))
    except (TypeError, ValueError):
        return None

    usd_value = size * price
    if usd_value < min_usd:
        return None

    side = str(trade.get("side", "")).upper()
    side_label = "BUY" if side == "BUY" else "SELL" if side == "SELL" else side
    outcome = trade.get("outcome", "")
    outcome_label = (
        "YES"
        if str(outcome) == "Yes" or str(outcome) == "0"
        else "NO"
        if str(outcome) == "No" or str(outcome) == "1"
        else str(outcome)
    )

    wallet = trade.get("maker_address") or trade.get("taker_address") or ""
    wallet_display = f"{wallet[:10]}..." if len(wallet) > 10 else wallet

    market_name = trade.get("_market_name", "")
    market_url = trade.get("_market_url", "")

    price_cents = price * 100

    lines = [
        f"\U0001f40b WHALE ALERT: ${usd_value:,.0f} {side_label} {outcome_label}",
        "",
        f"Market: {market_name}" if market_name else None,
        f"Price: {price_cents:.1f}\u00a2",
        f"Size: {size:,.2f} shares",
        f"Wallet: {wallet_display}" if wallet_display else None,
    ]

    if market_url:
        lines.append(f"\n\U0001f517 {market_url}")

    return "\n".join(line for line in lines if line is not None)
