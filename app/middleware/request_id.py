import uuid
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.logger import set_request_context, get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that generates and manages request IDs for logging correlation.
    
    This middleware:
    1. Checks for existing X-Request-ID or X-Correlation-ID headers
    2. Generates a new UUID4 if no ID is provided
    3. Stores the request ID in request.state for easy access
    4. Sets the request ID in the logging context
    5. Adds the request ID to response headers
    6. Enables request tracing throughout the application
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Check for existing request ID in headers
        request_id = (
            request.headers.get("X-Correlation-ID") or  # Highest priority
            request.headers.get("X-Request-ID") or       # Second priority
            str(uuid.uuid4())                           # Generate new if none provided
        )
        
        # Store request ID in request state for easy access
        request.state.request_id = request_id
        
        # Set request ID in logging context for automatic inclusion in logs
        set_request_context(request_id)
        
        # Log the incoming request with request ID
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            request_id=request_id
        )
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Add request ID to response headers for client correlation
            response.headers["X-Request-ID"] = request_id
            
            # Log the completed request
            logger.info(
                f"Request completed: {request.method} {request.url.path} - Status: {response.status_code}",
                request_id=request_id
            )
            
            return response
            
        except Exception as e:
            # Log any errors with request ID
            logger.error(
                f"Request failed: {request.method} {request.url.path} - Error: {str(e)}",
                request_id=request_id
            )
            raise
        finally:
            # Clear the request context after processing
            from app.utils.logger import clear_request_context
            clear_request_context()


def get_request_id(request: Request) -> str:
    """
    Get the current request ID from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: The request ID for the current request
        
    Raises:
        RuntimeError: If called outside of a request context
    """
    if not hasattr(request.state, 'request_id'):
        raise RuntimeError("Request ID not available. Ensure RequestIDMiddleware is configured.")
    return request.state.request_id 