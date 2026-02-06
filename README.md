# Poly-notify

Telegram bot that scans Polymarket (Gamma API), applies filters to market outcomes, and sends alerts based on configured rules.


## Run

### 1) Dependencies
Python 3.10+ is required.

Install dependencies in one step:

```bash
pip install -r requirements.txt
```

### 2) Config
Edit `config.yaml`:
- `telegram.token` and `telegram.chat_id`
- `telegram.enabled: true` to enable sending
- filter and alert parameters

### 3) Start

```bash
python main.py
```

## Default settings
- `scan_interval_seconds`: 300 sec
- probability filter: 0.2%–1%
- time-to-resolution filter: 7–180 days
- liquidity filter: from $5,000
- price spike alert: 30% within 60 minutes

## State storage
By default the state is stored in `state.json` next to the config (configurable via `state.path`).

## If you get timeouts
You can tune retries in `config.yaml`:
- `api.timeout_seconds`
- `api.max_retries`
- `api.retry_backoff_seconds`

If your network blocks `polymarket.com`, set a different `api.base_url`.

## API note
Gamma API is used by default: `https://gamma-api.polymarket.com/events` with `active=true` and `closed=false`.
Prices are fetched from the CLOB API (`https://clob.polymarket.com/prices`) using `token_id`. This is more accurate but adds extra requests per outcome.
If you want faster scanning, set `api.use_clob_prices: false` to use `outcomePrices` from Gamma API.
