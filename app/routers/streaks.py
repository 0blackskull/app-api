from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone as dt_timezone
import pytz

from app.database import get_db
from app.auth import get_current_user
from app.schemas import CurrentUser
from app.schemas.streak import StreakResponse
from app.crud.streak import get_streak
from app.crud.subscription import get_active_subscription
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/streaks", tags=["streaks"])


def _today_local(tz_name: str) -> datetime.date:
    tz = pytz.timezone(tz_name)
    return datetime.now(dt_timezone.utc).astimezone(tz).date()


@router.get("/me", response_model=StreakResponse)
async def get_my_streak(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's streak information."""
    try:
        # Check if user has active subscription (streak protection)
        active_subscription = get_active_subscription(db, current_user.id)
        has_subscription_protection = active_subscription is not None
        
        streak, effective, today_local = get_streak(db, current_user.id, has_subscription_protection)
        
        if not streak:
            # Default to IST for today when streak not created yet
            tz_name = "Asia/Kolkata"
            return StreakResponse(
                user_id=current_user.id,
                timezone=tz_name,
                current_streak=0,
                longest_streak=0,
                last_active_local_date=None,
                last_active_at_utc=None,
                effective_streak=0,
                today_local_date=_today_local(tz_name),
            )
        
        return StreakResponse(
            user_id=streak.user_id,
            timezone=streak.timezone,
            current_streak=streak.current_streak,
            longest_streak=streak.longest_streak,
            last_active_local_date=streak.last_active_local_date,
            last_active_at_utc=streak.last_active_at_utc,
            effective_streak=effective,
            today_local_date=today_local,
        )
        
    except Exception as e:
        logger.exception(f"Failed to get streak for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get streak information") 