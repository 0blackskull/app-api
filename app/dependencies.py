from fastapi import Request
from typing import Optional


def get_request_id(request: Request) -> str:
    """
    FastAPI dependency to get the current request ID.
    
    This dependency can be used in route handlers to access the request ID
    for logging or passing to downstream services.
    
    Usage:
        @router.get("/example")
        async def example_endpoint(request_id: str = Depends(get_request_id)):
            logger.info(f"Processing request {request_id}")
            return {"request_id": request_id}
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: The request ID for the current request
        
    Raises:
        HTTPException: If request ID is not available
    """
    from fastapi import HTTPException, status
    
    if not hasattr(request.state, 'request_id'):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Request ID not available"
        )
    
    return request.state.request_id


def get_optional_request_id(request: Request) -> Optional[str]:
    """
    FastAPI dependency to get the current request ID (optional).
    
    This dependency returns None if no request ID is available,
    making it safe to use in any context.
    
    Usage:
        @router.get("/example")
        async def example_endpoint(request_id: Optional[str] = Depends(get_optional_request_id)):
            if request_id:
                logger.info(f"Processing request {request_id}")
            return {"status": "ok"}
    
    Args:
        request: FastAPI request object
        
    Returns:
        Optional[str]: The request ID for the current request or None
    """
    return getattr(request.state, 'request_id', None) 