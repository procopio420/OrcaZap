"""Structured logging configuration."""

import json
import logging
import sys
from typing import Any

from app.settings import settings


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from log record
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "tenant_id"):
            log_data["tenant_id"] = str(record.tenant_id)
        if hasattr(record, "user_id"):
            log_data["user_id"] = str(record.user_id)
        if hasattr(record, "channel_id"):
            log_data["channel_id"] = str(record.channel_id)
        if hasattr(record, "provider_message_id"):
            log_data["provider_message_id"] = record.provider_message_id
        
        # Add any other extra fields
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info",
                "request_id", "tenant_id", "user_id", "channel_id", "provider_message_id",
            ]:
                log_data[key] = value
        
        return json.dumps(log_data, default=str)


def setup_logging():
    """Setup structured logging based on environment."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Use JSON formatter in production, simple formatter in development
    if settings.environment == "production":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set levels for third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.debug else logging.WARNING
    )





