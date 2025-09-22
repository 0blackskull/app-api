from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import os

from app.config import settings
from app.database import Base, engine
from app.logging_config import configure_logging
from app.middleware.rate_limit import limiter
from app.middleware.request_id import RequestIDMiddleware
from app.routers import api, chat, credits, friends, partners, users, payments, streaks, support, devices, rants
from app.middleware.force_update import ForceUpdateMiddleware
from app.utils.logger import get_logger

# Configure logging first
configure_logging()
logger = get_logger(__name__)

# Initialize database tables
Base.metadata.create_all(bind=engine)

# Initialize Firebase Admin SDK with explicit credentials
firebase_app = None
try:
    firebase_json_path = settings.FIREBASE_SERVICE_ACCOUNT_JSON
    if os.path.exists(firebase_json_path):
        cred = credentials.Certificate(firebase_json_path)
        firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Initialized Firebase Admin with provided service account JSON")
    else:
        # Fallback to default if path missing (e.g., using Application Default Credentials in env)
        firebase_app = firebase_admin.initialize_app()
        logger.warning(f"FIREBASE_SERVICE_ACCOUNT_JSON not found at {firebase_json_path}. Initialized Firebase with default credentials.")
except Exception as e:
    logger.exception(f"Failed to initialize Firebase Admin SDK: {e}")
    raise

# Conditional docs configuration
docs_config = {}
if settings.DEBUG:
    docs_config = {
        "docs_url": "/docs",
        "redoc_url": "/redoc", 
        "openapi_url": "/openapi.json"
    }
    logger.info("DEBUG mode: Swagger docs enabled at /docs")
else:
    docs_config = {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None
    }
    logger.info("Production mode: Swagger docs disabled")

# Create FastAPI app with conditional docs
app = FastAPI(
    title="Ask Stellar API",
    description="Backend API for Ask Stellar astrology app with Google Play Billing",
    version="1.0.0",
    **docs_config
)

# Set up rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

logger.info(f"CORS_ORIGINS: {settings.CORS_ORIGINS}")

# Add Request ID middleware first for proper request tracing
app.add_middleware(RequestIDMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Force-update middleware: compares only when headers are present
app.add_middleware(ForceUpdateMiddleware)

# Include routers
app.include_router(api.router)
app.include_router(chat.router)
app.include_router(credits.router)
app.include_router(partners.router)
app.include_router(users.router)
app.include_router(payments.router)
app.include_router(friends.router)
app.include_router(streaks.router)
app.include_router(devices.router)
app.include_router(support.router)
app.include_router(rants.router)

@app.on_event("startup")
async def startup_event():
    """Log application startup information."""
    # Initialize database in this worker process (for Gunicorn compatibility)
    from app.database import get_engine
    get_engine()
    
    if settings.DEBUG:
        logger.info("🚀 Ask Stellar API started in DEBUG mode - Docs available at /docs")
    else:
        logger.info("🚀 Ask Stellar API started in PRODUCTION mode - Docs disabled")

@app.get("/")
async def root():
    return {"message": "Ask Stellar API", "version": "1.0.0"}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy", "service": "ask-stellar-api"} 