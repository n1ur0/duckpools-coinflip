"""
DuckPools Off-Chain Bot - Structured Logging Configuration

Configures structlog for JSON-structured logging with timestamp and level.

MAT-182: Structured logging and error recovery
"""

import logging
import sys
from typing import Any

import structlog


def configure_logging() -> structlog.stdlib.BoundLogger:
    """
    Configure structlog for JSON-structured logging.

    Returns:
        Configured structlog logger
    """
    # Configure standard library logging to forward to structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            # Add context attributes to log entry
            structlog.contextvars.merge_contextvars,
            # Add timestamp
            structlog.processors.TimeStamper(fmt="iso"),
            # Add log level
            structlog.stdlib.add_log_level,
            # Convert to JSON
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger(__name__)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a logger with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)
