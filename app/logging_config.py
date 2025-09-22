from logging.config import dictConfig
import logging

from app.config import settings


class SafeRequestIDFormatter(logging.Formatter):
    """
    A formatter that safely handles missing request_id attributes.
    """
    
    def format(self, record):
        # Ensure request_id attribute exists
        if not hasattr(record, 'request_id'):
            record.request_id = 'no-request-id'
        return super().format(record)


# Central logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": SafeRequestIDFormatter,
            "format": "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s",
        },
        "detailed": {
            "()": SafeRequestIDFormatter,
            "format": "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(threadName)s - %(message)s",
        },
        "simple": {
            "()": SafeRequestIDFormatter,
            "format": "%(asctime)s - %(levelname)s - [%(request_id)s] - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        "detailed_console": {
            "class": "logging.StreamHandler",
            "formatter": "detailed",
        },
    },
    "root": {  # Root logger for all logs
        "level": "DEBUG" if settings.DEBUG else "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "app": {  # Catch-all logger for all app modules
            "level": "DEBUG" if settings.DEBUG else "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "uvicorn": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False,
        },
        "uvicorn.error": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False,
        },
        "uvicorn.access": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False,
        },
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "autogen_core": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

def configure_logging():
    """Configure logging for the application."""
    dictConfig(LOGGING_CONFIG) 