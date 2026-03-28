# =============================================================================
# DuckPools Coinflip - Off-Chain Bot Dockerfile
# =============================================================================
#
# Multi-stage build for Python off-chain bot
# - development: Hot-reload enabled, installs dev dependencies
# - production: Optimized image, minimal dependencies, runs as non-root
#
# Usage:
#   docker build -t duckpools-offchain-bot --target development .
#   docker build -t duckpools-offchain-bot:prod --target production .
# =============================================================================

# =============================================================================
# Base Stage - Python Runtime
# =============================================================================
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# =============================================================================
# Development Stage
# =============================================================================
FROM base as development

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install pytest pytest-asyncio httpx  # For testing

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Health check - check if process is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "main.py" || exit 1

# Run with development settings
CMD ["python", "main.py"]

# =============================================================================
# Production Stage
# =============================================================================
FROM base as production

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install only runtime dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code with proper permissions
COPY --chown=appuser:appuser . .

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# Switch to non-root user
USER appuser

# Health check - check if process is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "main.py" || exit 1

# Run with production settings
CMD ["python", "main.py"]
