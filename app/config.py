import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    """Application settings."""
    # Base settings
    DEBUG: bool = False
    
    # CORS settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",  # Frontend development server
        "http://localhost:8000",  # Backend server
    ]
    
    # Firebase settings
    FIREBASE_PROJECT_ID: str = ""
    # Explicit Firebase Admin SDK credentials JSON path
    FIREBASE_SERVICE_ACCOUNT_JSON: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "./firebase-service-account.json")
    
    # AI/ML service settings
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Database settings
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME: str = os.getenv("DB_NAME", "fastapi_firebase")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    
    # Redis settings
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    
    # Email settings (Mailgun only)
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "info@astroyaar.co.in")
    EMAIL_FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "AstroYaar")
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    
    # Google Play Billing settings
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "mailgun")  # mailgun | logging

    # Mailgun settings
    MAILGUN_API_KEY: str = os.getenv("MAILGUN_API_KEY", "")
    MAILGUN_DOMAIN: str = os.getenv("MAILGUN_DOMAIN", "astroyaar.co.in")
    MAILGUN_BASE_URL: str = os.getenv("MAILGUN_BASE_URL", "https://api.mailgun.net")

    # Support email destinations
    SUPPORT_TO_EMAIL: str = os.getenv("SUPPORT_TO_EMAIL", "info@astroyaar.co.in")
    SUPPORT_BCC_EMAIL: str = os.getenv("SUPPORT_BCC_EMAIL", "")

    # Google Play Billing settings (webhook-based)
    GOOGLE_PLAY_PACKAGE_NAME: str = os.getenv("GOOGLE_PLAY_PACKAGE_NAME", "com.stellar.frontend")
    # Explicit Google Play credentials JSON path
    GOOGLE_PLAY_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "./purchase-service-account.json")
    
    # Force update configuration
    FORCE_UPDATE_ENABLED: bool = os.getenv("FORCE_UPDATE_ENABLED", "false").lower() == "true"
    MIN_SUPPORTED_VERSION_ANDROID: str = os.getenv("MIN_SUPPORTED_VERSION_ANDROID", "")
    MIN_SUPPORTED_VERSION_IOS: str = os.getenv("MIN_SUPPORTED_VERSION_IOS", "")
    FORCE_UPDATE_ANDROID_URL: str = os.getenv("FORCE_UPDATE_ANDROID_URL", "")
    FORCE_UPDATE_IOS_URL: str = os.getenv("FORCE_UPDATE_IOS_URL", "")
    APP_VERSION_HEADER: str = os.getenv("APP_VERSION_HEADER", "X-App-Version")
    APP_PLATFORM_HEADER: str = os.getenv("APP_PLATFORM_HEADER", "X-App-Platform")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

# Google Play Billing Configuration (module-level convenience)
GOOGLE_PLAY_PACKAGE_NAME = settings.GOOGLE_PLAY_PACKAGE_NAME

# Product ID to Credits Mapping
PRODUCT_TO_CREDITS = {
    "questions_3": 3,
    "questions_5": 5,
    "credits_3": 3,
    "credits_5": 5,
    "credits_10": 10,
    "credits_20": 20,
}

# Subscription Product IDs
SUBSCRIPTION_PRODUCTS = {
    "subscription_monthly": "monthly",
    "subscription_yearly": "yearly",
    "premium_monthly": "monthly",
    "premium_yearly": "yearly",
}
