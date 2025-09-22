import json
import functools
from app.utils.logger import get_logger
from typing import Any, Optional, Callable
from datetime import datetime, timedelta
import pytz
import redis
from redis.connection import ConnectionPool
from app.config import settings

logger = get_logger(__name__)

# Redis client initialization
try:
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0,
        decode_responses=True,
        retry_on_timeout=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    # Test connection
    redis_client.ping()
    logger.info(f"Cache Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
except Exception as e:
    logger.warning(f"Cache Redis connection failed: {e}. Cache will be disabled.")
    redis_client = None

# Create a connection pool for better performance and connection management
redis_pool = ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    decode_responses=True,
    max_connections=20,  # Adjust based on your needs
    retry_on_timeout=True,
    socket_connect_timeout=5,
    socket_timeout=5
)

def is_redis_available() -> bool:
    """
    Check if Redis is available and connected.
    
    Returns:
        True if Redis is available, False otherwise
    """
    if redis_client is None:
        return False
    
    try:
        redis_client.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis ping failed: {e}")
        return False

def get_seconds_until_next_day_ist() -> int:
    """
    Calculate the number of seconds until the next day in IST.
    
    Returns:
        Number of seconds until next day 00:00:00 IST
    """
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    
    # Calculate next day at 00:00:00 IST
    next_day_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
    # Calculate seconds until next day
    seconds_until_next_day = (next_day_ist - now_ist).total_seconds()
    
    return int(seconds_until_next_day)

def get_seconds_until_end_of_date_ist(target_date: str) -> int:
    """
    Calculate the number of seconds until the end of a specific date in IST.
    The date should be in YYYY-MM-DD format.
    
    Args:
        target_date: Target date in YYYY-MM-DD format
        
    Returns:
        Number of seconds until the end of the target date (midnight of that date)
    """
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    
    try:
        # Parse the target date
        target_date_obj = datetime.strptime(target_date, '%Y-%m-%d').date()
        target_datetime_ist = datetime.combine(target_date_obj, datetime.max.time(), tzinfo=ist)
        
        # Calculate seconds until the end of the target date
        seconds_until_end = (target_datetime_ist - now_ist).total_seconds()
        
        # If the target date is in the past, return 0 (expire immediately)
        if seconds_until_end <= 0:
            return 0
            
        return int(seconds_until_end)
    except ValueError:
        # If date parsing fails, fall back to next day logic
        return get_seconds_until_next_day_ist()

def get_cached_data(key: str) -> Optional[Any]:
    """
    Get data from Redis cache.
    
    Args:
        key: The cache key
        
    Returns:
        The cached data if found, None otherwise
    """
    if not is_redis_available():
        return None
    
    try:
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.error(f"Error getting cached data for key {key}: {e}")
    
    return None

def set_cached_data(key: str, value: Any, expire_seconds: int = 3600) -> bool:
    """
    Set data in Redis cache with expiration.
    
    Args:
        key: The cache key
        value: The data to cache
        expire_seconds: Time to live in seconds (default: 1 hour)
        
    Returns:
        True if successful, False otherwise
    """
    if not is_redis_available():
        return False
    
    try:
        redis_client.setex(
            key,
            expire_seconds,
            json.dumps(value)
        )
        return True
    except Exception as e:
        logger.error(f"Error setting cached data for key {key}: {e}")
        return False

def delete_cached_data(key: str) -> bool:
    """
    Delete data from Redis cache.
    
    Args:
        key: The cache key
        
    Returns:
        True if successful, False otherwise
    """
    if not is_redis_available():
        return False
    
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        logger.error(f"Error deleting cached data for key {key}: {e}")
        return False

def scan_keys(pattern: str, count: int = 100) -> list:
    """
    Scan Redis keys matching a pattern.
    This is the recommended approach instead of using KEYS command.
    
    Args:
        pattern: The key pattern to match
        count: Number of keys to scan per iteration
        
    Returns:
        List of matching keys
    """
    if not is_redis_available():
        return []
    
    try:
        keys = []
        cursor = 0
        while True:
            cursor, batch = redis_client.scan(cursor, match=pattern, count=count)
            keys.extend(batch)
            if cursor == 0:
                break
        return keys
    except Exception as e:
        logger.error(f"Error scanning keys with pattern {pattern}: {e}")
        return []

def generate_cache_key(func_name: str, *args, **kwargs) -> str:
    """
    Generate a cache key based on function name and arguments.
    Excludes database sessions and other non-serializable dependencies.
    
    Args:
        func_name: Name of the function
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        A cache key string
    """
    # Filter out database sessions and other dependencies that shouldn't be in cache keys
    filtered_args = []
    for arg in args:
        # Skip database session objects and other dependencies
        if hasattr(arg, '__class__') and 'Session' in arg.__class__.__name__:
            continue
        if hasattr(arg, '__class__') and 'Depends' in str(type(arg)):
            continue
        # Check for SQLAlchemy Session type
        if hasattr(arg, '__class__') and hasattr(arg.__class__, '__module__'):
            if 'sqlalchemy' in arg.__class__.__module__ and 'Session' in arg.__class__.__name__:
                continue
        filtered_args.append(arg)
    
    # Filter out database sessions and dependencies from kwargs
    filtered_kwargs = {}
    for key, value in kwargs.items():
        # Skip database session objects and other dependencies
        if hasattr(value, '__class__') and 'Session' in value.__class__.__name__:
            continue
        if hasattr(value, '__class__') and 'Depends' in str(type(value)):
            continue
        # Check for SQLAlchemy Session type
        if hasattr(value, '__class__') and hasattr(value.__class__, '__module__'):
            if 'sqlalchemy' in value.__class__.__module__ and 'Session' in value.__class__.__name__:
                continue
        if key in ['db', 'current_user']:  # Skip common dependency names
            continue
        filtered_kwargs[key] = value
    
    # Convert filtered args and kwargs to a sorted string representation
    args_str = ":".join(str(arg) for arg in filtered_args)
    kwargs_str = ":".join(f"{k}={v}" for k, v in sorted(filtered_kwargs.items()))
    
    # Combine all parts with the function name
    key_parts = [func_name]
    if args_str:
        key_parts.append(args_str)
    if kwargs_str:
        key_parts.append(kwargs_str)
    
    return ":".join(key_parts)

def cache(expire_seconds: int = 3600, until_next_day_ist: bool = False):
    """
    Decorator for caching function results.
    
    Args:
        expire_seconds: Time to live in seconds (default: 1 hour)
        until_next_day_ist: If True, cache until next day 00:00:00 IST (overrides expire_seconds)
        
    Returns:
        Decorated function that caches its results
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = generate_cache_key(func.__name__, *args, **kwargs)
            
            # Log cache key for debugging (only in debug mode)
            if settings.DEBUG:
                logger.debug(f"Generated cache key for {func.__name__}: {cache_key}")
            
            # Try to get cached data
            cached_data = get_cached_data(cache_key)
            if cached_data is not None:
                if settings.DEBUG:
                    logger.debug(f"Cache hit for {func.__name__}")
                return cached_data
            
            # If no cache, call the function
            if settings.DEBUG:
                logger.debug(f"Cache miss for {func.__name__}, executing function")
            result = await func(*args, **kwargs)
            
            # Convert Pydantic model to dict if needed
            if hasattr(result, 'model_dump'):
                result = result.model_dump()
            
            # Determine expiration time
            if until_next_day_ist:
                actual_expire_seconds = get_seconds_until_next_day_ist()
            else:
                actual_expire_seconds = expire_seconds
            
            # Cache the result
            set_cached_data(cache_key, result, actual_expire_seconds)
            
            return result
        return wrapper
    return decorator

def generate_daily_facts_key(user_id: str) -> str:
    """
    Generate a cache key for daily facts.
    
    Args:
        user_id: The user ID
        
    Returns:
        A cache key string
    """
    return f"daily_facts:{user_id}"

def generate_daily_facts_date_key(user_id: str, target_date: str) -> str:
    """
    Generate a date-based cache key for daily facts.
    
    Args:
        user_id: The user ID
        target_date: The target date in YYYY-MM-DD format
        
    Returns:
        A cache key string that includes the date
    """
    return f"daily_facts:{user_id}:{target_date}"

def get_daily_facts_from_cache(user_id: str, target_date: str) -> Optional[Any]:
    """
    Get daily facts from cache for a specific user and date.
    
    Args:
        user_id: The user ID
        target_date: The target date in YYYY-MM-DD format
        
    Returns:
        The cached daily facts if found, None otherwise
    """
    cache_key = generate_daily_facts_date_key(user_id, target_date)
    return get_cached_data(cache_key)

def set_daily_facts_in_cache(user_id: str, target_date: str, daily_facts: Any, expire_seconds: int = None) -> bool:
    """
    Set daily facts in cache for a specific user and date.
    
    Args:
        user_id: The user ID
        target_date: The target date in YYYY-MM-DD format
        daily_facts: The daily facts data to cache
        expire_seconds: Time to live in seconds (if None, uses 72 hours)
        
    Returns:
        True if successful, False otherwise
    """
    cache_key = generate_daily_facts_date_key(user_id, target_date)
    
    # Convert Pydantic model to dict if needed
    if hasattr(daily_facts, 'model_dump'):
        daily_facts = daily_facts.model_dump()
    elif hasattr(daily_facts, 'dict'):
        daily_facts = daily_facts.dict()
    
    # If no expiration specified, use 72 hours (3 days)
    if expire_seconds is None:
        expire_seconds = 72 * 60 * 60  # 72 hours in seconds
    
    return set_cached_data(cache_key, daily_facts, expire_seconds)

def get_seconds_until_end_of_week_ist(week_start_date: str) -> int:
    """
    Calculate the number of seconds until the end of the week (Sunday) in IST.
    The week_start_date should be in YYYY-MM-DD format (Monday).
    
    Args:
        week_start_date: Week start date in YYYY-MM-DD format (Monday)
        
    Returns:
        Number of seconds until the end of the week (midnight of Sunday)
    """
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    
    try:
        # Parse the week start date (Monday)
        week_start_obj = datetime.strptime(week_start_date, '%Y-%m-%d').date()
        # Calculate week end date (Sunday) - 6 days after Monday
        week_end_obj = week_start_obj + timedelta(days=6)
        week_end_datetime_ist = datetime.combine(week_end_obj, datetime.max.time(), tzinfo=ist)
        
        # Calculate seconds until the end of the week
        seconds_until_end = (week_end_datetime_ist - now_ist).total_seconds()
        
        # If the week is in the past, return 0 (expire immediately)
        if seconds_until_end <= 0:
            return 0
            
        return int(seconds_until_end)
    except ValueError:
        # If date parsing fails, fall back to 7 days
        return 7 * 24 * 60 * 60  # 7 days in seconds

def generate_weekly_horoscope_date_key(user_id: str, week_start_date: str) -> str:
    """
    Generate a date-based cache key for weekly horoscope.
    
    Args:
        user_id: The user ID
        week_start_date: The week start date in YYYY-MM-DD format (Monday)
        
    Returns:
        A cache key string that includes the week start date
    """
    return f"weekly_horoscope:{user_id}:{week_start_date}"

def get_weekly_horoscope_from_cache(user_id: str, week_start_date: str) -> Optional[Any]:
    """
    Get weekly horoscope from cache for a specific user and week.
    
    Args:
        user_id: The user ID
        week_start_date: The week start date in YYYY-MM-DD format (Monday)
        
    Returns:
        The cached weekly horoscope if found, None otherwise
    """
    cache_key = generate_weekly_horoscope_date_key(user_id, week_start_date)
    return get_cached_data(cache_key)

def set_weekly_horoscope_in_cache(user_id: str, week_start_date: str, weekly_horoscope: Any, expire_seconds: int = None) -> bool:
    """
    Set weekly horoscope in cache for a specific user and week.
    
    Args:
        user_id: The user ID
        week_start_date: The week start date in YYYY-MM-DD format (Monday)
        weekly_horoscope: The weekly horoscope data to cache
        expire_seconds: Time to live in seconds (if None, uses until_end_of_week logic)
        
    Returns:
        True if successful, False otherwise
    """
    cache_key = generate_weekly_horoscope_date_key(user_id, week_start_date)
    
    # Convert Pydantic model to dict if needed
    if hasattr(weekly_horoscope, 'model_dump'):
        weekly_horoscope = weekly_horoscope.model_dump()
    elif hasattr(weekly_horoscope, 'dict'):
        weekly_horoscope = weekly_horoscope.dict()
    
    # If no expiration specified, use until_end_of_week logic
    if expire_seconds is None:
        expire_seconds = get_seconds_until_end_of_week_ist(week_start_date)
    
    return set_cached_data(cache_key, weekly_horoscope, expire_seconds)

def clear_user_cache(user_id: str) -> bool:
    """
    Clear all cache entries for a specific user.
    
    Args:
        user_id: The user ID to clear cache for
        
    Returns:
        True if successful, False otherwise
    """
    if not is_redis_available():
        logger.warning("Redis not available, cannot clear user cache")
        return False
    
    try:
        # Get all keys that match the user pattern
        # This includes daily_facts, weekly_horoscope, and any other user-specific cache keys
        user_patterns = [
            f"daily_facts:{user_id}*",
            f"weekly_horoscope:{user_id}*",
            f"*:{user_id}:*",  # Any cache key that contains the user_id
            f"*:{user_id}",    # Any cache key that ends with user_id
        ]
        
        total_deleted = 0
        for pattern in user_patterns:
            # Use SCAN to find matching keys (more efficient than KEYS for large datasets)
            cursor = 0
            while True:
                cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    deleted_count = redis_client.delete(*keys)
                    total_deleted += deleted_count
                    logger.info(f"Deleted {deleted_count} cache keys matching pattern '{pattern}' for user {user_id}")
                
                if cursor == 0:
                    break
        
        logger.info(f"Cleared {total_deleted} total cache entries for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error clearing cache for user {user_id}: {e}")
        return False


