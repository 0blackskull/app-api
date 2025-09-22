from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
import redis
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Redis connection for rate limiting
try:
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True,
        retry_on_timeout=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    # Test connection
    redis_client.ping()
    logger.info(f"Rate limiting Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
except Exception as e:
    logger.warning(f"Rate limiting Redis connection failed: {e}. Using in-memory fallback.")
    redis_client = None

def get_user_id_or_ip(request: Request):
    """
    Get user ID from Firebase token or fall back to IP address.
    This provides better rate limiting for authenticated users.
    """
    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, 'user_id', None)
    if user_id:
        return f"user:{user_id}"
    
    # Fall back to IP address
    return f"ip:{get_remote_address(request)}"

# Create limiter instance
limiter = Limiter(
    key_func=get_user_id_or_ip,
    storage_uri=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}" if redis_client else "memory://",
    default_limits=["1000/hour"]  # Global default limit
)

# Rate limiting configurations for different endpoints
RATE_LIMITS = {
    # Authentication endpoints
    "auth": "10/minute",
    
    # Chat endpoints (most resource intensive)
    "chat": "30/hour",
    "chat_stream": "20/hour",
    
    # User operations
    "user_read": "100/hour",
    "user_write": "50/hour",
    
    # Payment endpoints
    "payment": "20/hour",
    
    # General API endpoints
    "api_read": "200/hour",
    "api_write": "100/hour",
    
    # Health checks (very generous for monitoring tools)
    "health": "300/minute"  # 5 requests per second - very generous for monitoring
}

def get_rate_limit_for_endpoint(endpoint: str) -> str:
    """Get rate limit configuration for specific endpoint."""
    return RATE_LIMITS.get(endpoint, "100/hour")

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom rate limit exceeded handler with helpful error messages.
    """
    response = Response(
        content=f"Rate limit exceeded: {exc.detail}. Please try again later.",
        status_code=429,
        headers={
            "Retry-After": str(exc.retry_after) if exc.retry_after else "60",
            "X-RateLimit-Limit": str(exc.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(exc.reset_time) if exc.reset_time else ""
        }
    )
    return response

# Rate limiting decorators for different endpoint types
def rate_limit_chat(func):
    """Rate limit for chat endpoints."""
    return limiter.limit(get_rate_limit_for_endpoint("chat"))(func)

def rate_limit_auth(func):
    """Rate limit for authentication endpoints."""
    return limiter.limit(get_rate_limit_for_endpoint("auth"))(func)

def rate_limit_payment(func):
    """Rate limit for payment endpoints."""
    return limiter.limit(get_rate_limit_for_endpoint("payment"))(func)

def rate_limit_api_read(func):
    """Rate limit for read API endpoints."""
    return limiter.limit(get_rate_limit_for_endpoint("api_read"))(func)

def rate_limit_api_write(func):
    """Rate limit for write API endpoints."""
    return limiter.limit(get_rate_limit_for_endpoint("api_write"))(func) 