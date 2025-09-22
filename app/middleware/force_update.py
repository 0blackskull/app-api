from app.utils.logger import get_logger
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


logger = get_logger(__name__)


def parse_semver(version_str: str) -> tuple[int, int, int]:
    """Parse a version like '1.2.3' into a comparable tuple. Missing parts default to 0."""
    if not version_str:
        return (0, 0, 0)
    parts = version_str.strip().split(".")
    major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return (major, minor, patch)


def is_version_less_than(a: str, b: str) -> bool:
    """Return True if version a < version b using numeric comparison."""
    a_tuple = parse_semver(a)
    b_tuple = parse_semver(b)
    return a_tuple < b_tuple


class ForceUpdateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        logger.info(f"ForceUpdateMiddleware dispatch {settings.FORCE_UPDATE_ENABLED}")
        # Short-circuit if disabled
        if not settings.FORCE_UPDATE_ENABLED:
            return await call_next(request)

        # Read headers lazily; compare only if provided
        version_header_name = settings.APP_VERSION_HEADER
        platform_header_name = settings.APP_PLATFORM_HEADER

        app_version = request.headers.get(version_header_name)
        app_platform = (request.headers.get(platform_header_name) or "").lower()

        # Only enforce when version header present; otherwise allow
        if app_version:
            if app_platform == "android":
                min_version = settings.MIN_SUPPORTED_VERSION_ANDROID
                store_url = settings.FORCE_UPDATE_ANDROID_URL
                platform = "android"
            elif app_platform == "ios":
                min_version = settings.MIN_SUPPORTED_VERSION_IOS
                store_url = settings.FORCE_UPDATE_IOS_URL
                platform = "ios"
            else:
                # Unknown platform, do a generic min check if any is configured
                min_version = settings.MIN_SUPPORTED_VERSION_ANDROID or settings.MIN_SUPPORTED_VERSION_IOS or ""
                store_url = settings.FORCE_UPDATE_ANDROID_URL or settings.FORCE_UPDATE_IOS_URL or ""
                platform = app_platform or "unknown"

            logger.error(f"App version: {app_version}, Min version: {min_version}, Platform: {platform}")
            if min_version and is_version_less_than(app_version, min_version):
                # 426 Upgrade Required
                from fastapi.responses import JSONResponse
                payload = {
                    "error": "update_required",
                    "platform": platform,
                    "current_version": app_version,
                    "min_version": min_version,
                    "message": "Please update to continue.",
                }
                if store_url:
                    payload["store_url"] = store_url
                return JSONResponse(status_code=426, content=payload)

        # Pass-through
        return await call_next(request) 