"""
Logging utilities for the Conductor Agent.
Provides structured logging with rich console output.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.logging import RichHandler
from config.settings import settings


# Rich console for beautiful output
console = Console()


def setup_logger(name: str = "conductor_agent") -> logging.Logger:
    """
    Set up a logger with console output + a file handler when the log
    directory is writable. On Cloud Run / Render the container FS layer is
    writable but ephemeral; on read-only FS we skip the file handler instead
    of crashing at import.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    logger.handlers.clear()

    # Console handler is always safe.
    console_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=False,
        show_path=False,
    )
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # File handler — best effort. Falls back to /tmp, then disables entirely.
    candidates = [Path(settings.log_file), Path("/tmp/conductor.log")]
    for log_file in candidates:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            logger.addHandler(file_handler)
            break
        except OSError:
            continue

    return logger


# Global logger instance
logger = setup_logger()


def log_processing_stats(processor_name: str, **stats):
    """Log processing statistics in a formatted way."""
    logger.info(f"[bold blue]{processor_name}[/bold blue] Processing Stats:", extra={"markup": True})
    for key, value in stats.items():
        logger.info(f"  • {key}: {value}")
