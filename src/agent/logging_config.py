from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

# Logger name for agent operations
AGENT_LOGGER_NAME = "chart_orchestrator.agent"
TOOL_LOGGER_NAME = "chart_orchestrator.tool"
WORKFLOW_LOGGER_NAME = "chart_orchestrator.workflow"


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter for telemetry-friendly logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add any extra fields from the record
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data.update(record.extra)

        # Add structured event data if present
        for key in ["event_type", "agent", "tool", "workflow_id", "duration_ms", "input", "output", "error"]:
            if hasattr(record, key):
                value = getattr(record, key)
                if value is not None:
                    log_data[key] = value

        return json.dumps(log_data, default=str)


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "agent_execution.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    enable_console: bool = True,
) -> None:
    """
    Configure logging with structured JSON format and file rotation.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        enable_console: Whether to also log to console
    """
    # Create log directory if it doesn't exist
    log_dir = os.path.dirname(os.path.abspath(log_file)) if os.path.dirname(log_file) else "."
    if log_dir != "." and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Set up JSON formatter
    json_formatter = JSONFormatter()

    # Root logger configuration
    root_logger = logging.getLogger("chart_orchestrator")
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.propagate = False

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # Capture all levels to file
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    # Console handler (optional, more readable format)
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        # Use simpler format for console readability
        console_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(f"chart_orchestrator.{name}")


# Initialize logging on module import (can be reconfigured later)
if not logging.getLogger("chart_orchestrator").handlers:
    setup_logging()

