import os
import sys
from app.utils.logger import get_logger

# Add the parent directory to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


logger = get_logger(__name__)

def init_db():
    """Initialize the database if needed."""
    try:
        # Just log initialization - migrations are handled by Alembic
        logger.info("Database initialization check complete")
        print("Database initialization check complete")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        print(f"Error during database initialization: {e}")
        raise

if __name__ == "__main__":
    init_db() 