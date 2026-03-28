# =============================================================================
# DuckPools Coinflip - Backend Dockerfile (Development Only)
# =============================================================================
#
# Development-only Dockerfile for FastAPI backend
# - Hot-reload enabled
# - Non-root user for security
# - Health check endpoint
#
# Usage:
#   docker build -t duckpools-backend .
#   docker run -p 8000:8000 -v $(pwd)/.env:/app/.env duckpools-backend
#
# Docker Compose (recommended):
#   services:
#     backend:
#       build: ./backend
#       ports:
#         - "8000:8000"
#       environment:
#         - NODE_URL=http://host.docker.internal:9052
#       volumes:
#         - ./backend/.env:/app/.env
#         - ./backend:/app
#       extra_hosts:
#         - "host.docker.internal:host-gateway"
#
# IMPORTANT: This is a dev-only Dockerfile. The backend connects to Ergo node 
# on the host machine via host.docker.internal:9052
# =============================================================================

FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies (curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Create working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code with proper permissions
COPY --chown=appuser:appuser . .

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with hot-reload for development
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]