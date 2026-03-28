"""
DuckPools - Off-Chain Bot Structured Logging

Configures structlog for structured JSON logging with key context fields.

MAT-223: Retry logic and graceful shutdown for off-chain bot
"""

import logging
import sys
from typing import Any

import structlog


def configure_structured_logging(log_level: str = "INFO") -> None:
    """
    Configure structlog for structured JSON logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Configure structlog processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # Development renderer (human-readable)
    dev_renderer = structlog.dev.ConsoleRenderer(
        exception_formatter=structlog.dev.plain_traceback
    )

    # Production renderer (JSON)
    prod_renderer = structlog.processors.JSONRenderer()

    # Choose renderer based on environment
    is_dev = log_level.upper() == "DEBUG"

    structlog.configure(
        processors=shared_processors
        + ([structlog.processors.UnicodeDecoder()] if is_dev else [])
        + ([dev_renderer] if is_dev else [prod_renderer]),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)
