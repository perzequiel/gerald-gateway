from typing_extensions import Protocol
from typing import Any, Optional


class BoundLogger(Protocol):
    """Protocol for a bound logger with context."""
    
    def info(self, event: str, **kwargs: Any) -> None:
        """
        Log an info message.
        
        Args:
            event: Event name/message
            **kwargs: Additional context fields
        """
        ...
    
    def warning(self, event: str, **kwargs: Any) -> None:
        """
        Log a warning message.
        
        Args:
            event: Event name/message
            **kwargs: Additional context fields
        """
        ...
    
    def error(self, event: str, exc_info: bool = False, **kwargs: Any) -> None:
        """
        Log an error message.
        
        Args:
            event: Event name/message
            exc_info: Whether to include exception info
            **kwargs: Additional context fields
        """
        ...


class LoggingPort(Protocol):
    """Protocol for logging operations."""
    
    def bind(self, **kwargs: Any) -> BoundLogger:
        """
        Create a bound logger with context.
        
        Args:
            **kwargs: Context fields to bind to all log messages
            
        Returns:
            A bound logger with the specified context
        """
        ...

