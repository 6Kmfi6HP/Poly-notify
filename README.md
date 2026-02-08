# Poly-notify

Telegram bot that scans Polymarket (Gamma API), applies filters to market outcomes, and sends alerts based on configured rules.

**What it does**
- `scanner.py`: fetches data from Polymarket APIs and normalizes outcomes.
- `filters/`: filters outcomes by probability, liquidity, volume, and time to resolution.
- `alerts/`: builds messages for new markets, price spikes, and range entry.
- `notifier.py`: sends messages via Telegram Bot API and/or writes to a local file.
- `state.py`: persists state to avoid duplicates and track price changes.
- `main.py`: main loop — scan → filter → alert → save state.

## Quick Start with Docker

### Pull from GHCR

```bash
docker pull ghcr.io/6kmfi6hp/poly-notify:latest
```

### Run with Docker

```bash
docker run -d \
  --name poly-notify \
  -e TELEGRAM_BOT_TOKEN="your_bot_token" \
  -e TELEGRAM_CHAT_ID="your_chat_id" \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/data:/app/data \
  ghcr.io/6kmfi6hp/poly-notify:latest
```

### Run with Docker Compose

1. Create a `.env` file:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

2. Start the container:

```bash
docker-compose up -d
```

3. View logs:

```bash
docker-compose logs -f
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token | - |
| `TELEGRAM_CHAT_ID` | Target chat/channel ID | - |
| `TELEGRAM_ENABLED` | Enable Telegram notifications | `true` (auto-enabled if token+chat_id set) |
| `CONFIG_PATH` | Path to config file | `config.yaml` |
| `STATE_PATH` | Path to state file | `state.json` |
| `SCAN_INTERVAL` | Scan interval in seconds | `300` |

Environment variables override values in `config.yaml`.

## Build Locally

```bash
# Build image
docker build -t poly-notify .

# Run
docker run -d \
  --name poly-notify \
  -e TELEGRAM_BOT_TOKEN="your_token" \
  -e TELEGRAM_CHAT_ID="your_chat_id" \
  -v $(pwd)/data:/app/data \
  poly-notify
```

## Run Without Docker

### 1) Dependencies
Python 3.10+ is required.

```bash
pip install -r requirements.txt
```

### 2) Config
Edit `config.yaml`:
- `telegram.token` and `telegram.chat_id`
- `telegram.enabled: true` to enable sending
- `output.enabled: true` and `output.path` to save alerts to a file
- filter and alert parameters

### 3) Start

```bash
python main.py
```

## Default Settings

- `scan_interval_seconds`: 300 sec (5 min)
- probability filter: 0.4% – 2%
- time-to-resolution filter: disabled
- liquidity filter: disabled
- volume filter: disabled
- price spike alert: 20% within 60 minutes

## State Storage

By default the state is stored in `state.json` next to the config (configurable via `state.path` or `STATE_PATH` env).

For Docker, state is persisted in `/app/data/state.json` via volume mount.

## Troubleshooting

### Timeouts
Tune retries in `config.yaml`:
- `api.timeout_seconds`
- `api.max_retries`
- `api.retry_backoff_seconds`

If your network blocks `polymarket.com`, set a different `api.base_url`.

### API Note
Gamma API is used by default: `https://gamma-api.polymarket.com/events` with `active=true` and `closed=false`.

Prices are fetched from the CLOB API (`https://clob.polymarket.com/prices`) using `token_id`. This is more accurate but adds extra requests per outcome.

If you want faster scanning, set `api.use_clob_prices: false` to use `outcomePrices` from Gamma API.

## License

MIT
