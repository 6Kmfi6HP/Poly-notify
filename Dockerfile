# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/app/deps -r requirements.txt

# Production stage
FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/6Kmfi6HP/Poly-notify"
LABEL org.opencontainers.image.description="Polymarket notification bot - Monitor markets, price spikes, and new opportunities"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 poly && \
    mkdir -p /app/data && \
    chown -R poly:poly /app

# Copy dependencies from builder
COPY --from=builder /app/deps /usr/local/lib/python3.12/site-packages/

# Copy application code
COPY --chown=poly:poly . .

# Create data directory for state persistence
VOLUME ["/app/data"]

# Switch to non-root user
USER poly

# Environment variables (can be overridden)
ENV TELEGRAM_BOT_TOKEN=""
ENV TELEGRAM_CHAT_ID=""
ENV CONFIG_PATH="/app/config.yaml"
ENV STATE_PATH="/app/data/state.json"

# Health check - verify Python can import main modules
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import main; import scanner; print('ok')" || exit 1

# Run the bot
CMD ["python", "-u", "main.py"]
