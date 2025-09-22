from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Database connection pooling configuration
# Optimized for Lightsail auto-scaling (1-5 containers)
POOL_SIZE = 5          # Base connections per container
MAX_OVERFLOW = 10      # Additional connections when needed
POOL_TIMEOUT = 30      # Seconds to wait for connection
POOL_RECYCLE = 1800    # Recycle connections every 30 minutes (reduced for RDS)
POOL_PRE_PING = True   # Validate connections before use

# Global variables for lazy initialization
_engine = None
_session_local = None

def get_engine():
    """Get database engine with lazy initialization for Gunicorn worker compatibility."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            poolclass=QueuePool,
            pool_size=POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_timeout=POOL_TIMEOUT,
            pool_recycle=POOL_RECYCLE,
            pool_pre_ping=POOL_PRE_PING,
            echo=settings.DEBUG,  # Log SQL queries in debug mode
            echo_pool=settings.DEBUG,  # Log pool events in debug mode
        )
        # Log pool configuration
        logger.info(f"Database pool configured: size={POOL_SIZE}, max_overflow={MAX_OVERFLOW}, timeout={POOL_TIMEOUT}s")
    return _engine

def get_session_local():
    """Get SessionLocal with lazy initialization for Gunicorn worker compatibility."""
    global _session_local
    if _session_local is None:
        _session_local = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=get_engine())
    return _session_local

# For backward compatibility, create engine reference
engine = get_engine()

Base = declarative_base()

def get_db():
    """
    Database dependency for FastAPI.
    Provides database session with automatic cleanup.
    """
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        try:
            db.rollback()
        except Exception as rollback_error:
            logger.error(f"Error during rollback: {rollback_error}")
        
        # Log additional connection pool status for debugging
        try:
            pool_status = get_pool_status()
            logger.error(f"Pool status during error: {pool_status}")
        except Exception as pool_error:
            logger.error(f"Could not get pool status: {pool_error}")
        raise
    finally:
        try:
            db.close()
        except Exception as close_error:
            logger.error(f"Error closing database session: {close_error}")

def get_pool_status():
    """
    Get current database connection pool status.
    Useful for monitoring and debugging.
    """
    try:
        pool = get_engine().pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "pool_type": type(pool).__name__
        }
    except Exception as e:
        return {
            "error": f"Could not get pool status: {str(e)}",
            "pool_type": "unknown"
        }

def reset_pool():
    """
    Reset the database connection pool.
    Useful for clearing stuck connections.
    """
    try:
        logger.info("Resetting database connection pool...")
        get_engine().dispose()
        # Reset globals so new engine will be created
        global _engine, _session_local
        _engine = None
        _session_local = None
        logger.info("Database connection pool reset successfully")
        return True
    except Exception as e:
        logger.error(f"Error resetting database pool: {e}")
        return False 