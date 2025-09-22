import logging
import contextvars
from typing import Optional

# Context variable to store request ID across async operations
request_id_context = contextvars.ContextVar('request_id', default=None)


class RequestAwareFormatter(logging.Formatter):
    """
    Custom formatter that includes request ID in log messages.
    
    This formatter automatically adds request ID to all log messages
    when available in the current context.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Get request ID from context if available
        request_id = getattr(record, 'request_id', None)
        if not request_id:
            request_id = request_id_context.get()
        
        # Add request ID to record if we have one
        if request_id:
            record.request_id = request_id
        else:
            record.request_id = "no-request-id"
        
        # Use the enhanced format with request ID
        return super().format(record)


class RequestAwareLogger:
    """
    A logger wrapper that automatically includes request context.
    
    This class provides a seamless way to log messages with request IDs
    without manually passing the request object to every logging call.
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name
    
    def _log_with_context(self, level: int, msg: str, *args, **kwargs):
        """Internal method to log with request context."""
        # Extract request_id from kwargs if provided
        request_id = kwargs.pop('request_id', None)
        
        # If no request_id in kwargs, try to get from context
        if not request_id:
            request_id = request_id_context.get()
        
        # Add request_id to extra for the formatter
        if request_id:
            extra = kwargs.get('extra', {})
            extra['request_id'] = request_id
            kwargs['extra'] = extra
        
        self.logger.log(level, msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        self._log_with_context(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        self._log_with_context(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self._log_with_context(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self._log_with_context(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        self._log_with_context(logging.CRITICAL, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        self._log_with_context(logging.ERROR, msg, *args, **kwargs, exc_info=True)


def get_logger(name: str) -> RequestAwareLogger:
    """
    Get a request-aware logger for the specified name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        RequestAwareLogger: A logger that automatically includes request context
    """
    return RequestAwareLogger(name)


def set_request_context(request_id: str):
    """
    Set the request ID in the current context.
    
    This should be called at the beginning of each request to establish
    the request context for logging.
    
    Args:
        request_id: The request ID to set in context
    """
    request_id_context.set(request_id)


def get_request_context() -> Optional[str]:
    """
    Get the current request ID from context.
    
    Returns:
        Optional[str]: The current request ID or None if not set
    """
    return request_id_context.get()


def clear_request_context():
    """Clear the current request context."""
    request_id_context.set(None)


def log_with_request_id(logger: logging.Logger, level: int, msg: str, request_id: str, *args, **kwargs):
    """
    Convenience function to log with request ID using standard logging.
    
    Args:
        logger: Standard Python logger instance
        level: Log level
        msg: Log message
        request_id: Request ID to include
        *args: Additional arguments for the log message
        **kwargs: Additional keyword arguments for the log message
    """
    extra = kwargs.get('extra', {})
    extra['request_id'] = request_id
    kwargs['extra'] = extra
    logger.log(level, msg, *args, **kwargs) 