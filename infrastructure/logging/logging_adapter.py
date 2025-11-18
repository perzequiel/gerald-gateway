"""
Logging adapter that implements LoggingPort protocol.

This adapter wraps structlog to provide a clean interface for the application layer.
"""
from typing import Any
from domain.interfaces import LoggingPort, BoundLogger
from infrastructure.logging.structlog_logs import logger as structlog_logger


class StructlogBoundLogger:
    """
    Wrapper for structlog bound logger that implements BoundLogger protocol.
    """
    
    def __init__(self, bound_logger):
        """
        Initialize with a structlog bound logger.
        
        Args:
            bound_logger: A structlog bound logger instance
        """
        self._logger = bound_logger
    
    def info(self, event: str, **kwargs: Any) -> None:
        """Log an info message."""
        self._logger.info(event, **kwargs)
    
    def warning(self, event: str, **kwargs: Any) -> None:
        """Log a warning message."""
        self._logger.warning(event, **kwargs)
    
    def error(self, event: str, exc_info: bool = False, **kwargs: Any) -> None:
        """Log an error message."""
        self._logger.error(event, exc_info=exc_info, **kwargs)


class LoggingAdapter:
    """
    Adapter that implements LoggingPort for structured logging.
    
    This adapter wraps structlog to provide structured JSON logging
    with context binding capabilities.
    """
    
    def bind(self, **kwargs: Any) -> BoundLogger:
        """
        Create a bound logger with context.
        
        Args:
            **kwargs: Context fields to bind to all log messages
            
        Returns:
            A bound logger with the specified context
        """
        bound_logger = structlog_logger.bind(**kwargs)
        return StructlogBoundLogger(bound_logger)

