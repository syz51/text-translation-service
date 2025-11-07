"""Logging configuration."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from app.core.config import get_settings
from app.core.log_filter import SensitiveDataFilter


def setup_logging() -> None:
    """Configure application logging with stdout and rotating file handlers."""
    settings = get_settings()

    # Create logs directory
    logs_dir = Path("./logs")
    logs_dir.mkdir(exist_ok=True)

    # Configure handlers
    handlers = [
        # Stdout handler for console output
        logging.StreamHandler(sys.stdout),
        # Rotating file handler (10MB, 5 backups)
        RotatingFileHandler(
            logs_dir / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        ),
    ]

    # Apply sensitive data filter to all handlers if enabled
    if settings.enable_log_redaction:
        log_filter = SensitiveDataFilter()
        for handler in handlers:
            handler.addFilter(log_filter)

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


def get_logger(name: str) -> logging.Logger:
    """Get logger instance for module."""
    return logging.getLogger(name)
