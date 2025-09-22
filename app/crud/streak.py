from __future__ import annotations
from typing import Optional, Tuple
from datetime import datetime, timedelta, timezone as dt_timezone
import pytz
from sqlalchemy.orm import Session
from sqlalchemy import text, bindparam
from sqlalchemy.types import Date

from app.models.user_streak import UserStreak


def _get_today_in_tz(now_utc: datetime, tz_name: str) -> datetime.date:
    tz = pytz.timezone(tz_name)
    now_local = now_utc.astimezone(tz)
    return now_local.date()


def _yesterday(d: datetime.date) -> datetime.date:
    return d - timedelta(days=1)


def compute_effective_streak(current_streak: int, last_active_local_date: Optional[datetime.date], today_local: datetime.date, has_subscription_protection: bool = False) -> int:
    """
    Compute effective streak considering subscription protection.
    
    Args:
        current_streak: Current streak count
        last_active_local_date: Last active date
        today_local: Today's date in user's timezone
        has_subscription_protection: Whether user has active subscription
        
    Returns:
        Effective streak count
    """
    if last_active_local_date is None:
        return 0
    
    # If user has subscription protection, they don't lose streaks for missed days
    if has_subscription_protection:
        if last_active_local_date < today_local:
            # Still active, just missed some days
            return current_streak
        else:
            return current_streak
    
    # Free users lose streaks if they miss a day
    if last_active_local_date < _yesterday(today_local):
        return 0
    
    return current_streak


def ping_streak(db: Session, user_id: str, has_subscription_protection: bool = False) -> Tuple[UserStreak, int, datetime.date]:
    """
    Atomically record activity for 'today' in the user's timezone using an UPSERT.
    Considers subscription protection for streak calculations.
    
    Args:
        db: Database session
        user_id: User ID
        has_subscription_protection: Whether user has active subscription
        
    Returns:
        Tuple of (UserStreak, effective_streak, today_local_date)
    """
    now_utc = datetime.now(dt_timezone.utc)

    # Determine timezone to use: prefer existing row, else default IST
    existing: Optional[UserStreak] = db.query(UserStreak).filter(UserStreak.user_id == user_id).first()
    tz_name = (existing.timezone if existing and existing.timezone else None) or "Asia/Kolkata"

    today_local = _get_today_in_tz(now_utc, tz_name)

    # Use a single upsert statement to avoid race conditions
    sql = text(
        """
        INSERT INTO user_streaks (user_id, timezone, current_streak, longest_streak, last_active_local_date, last_active_at_utc)
        VALUES (:user_id, :timezone, 1, 1, :today_local, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
          timezone = COALESCE(EXCLUDED.timezone, user_streaks.timezone),
          current_streak = CASE
            WHEN user_streaks.last_active_local_date = EXCLUDED.last_active_local_date THEN user_streaks.current_streak
            WHEN user_streaks.last_active_local_date = ((EXCLUDED.last_active_local_date - INTERVAL '1 day')::date) THEN user_streaks.current_streak + 1
            ELSE 1
          END,
          longest_streak = GREATEST(
            user_streaks.longest_streak,
            CASE
              WHEN user_streaks.last_active_local_date = EXCLUDED.last_active_local_date THEN user_streaks.current_streak
              WHEN user_streaks.last_active_local_date = ((EXCLUDED.last_active_local_date - INTERVAL '1 day')::date) THEN user_streaks.current_streak + 1
              ELSE 1
            END
          ),
          last_active_local_date = EXCLUDED.last_active_local_date,
          last_active_at_utc = NOW()
        RETURNING user_id, timezone, current_streak, longest_streak, last_active_local_date, last_active_at_utc
        """
    ).bindparams(
        bindparam("user_id"),
        bindparam("timezone"),
        bindparam("today_local", type_=Date),
    )

    result = db.execute(sql, {"user_id": user_id, "timezone": tz_name, "today_local": today_local})
    row = result.fetchone()
    db.commit()

    # Materialize ORM object for convenience
    streak = UserStreak(
        user_id=row[0],
        timezone=row[1],
        current_streak=row[2],
        longest_streak=row[3],
        last_active_local_date=row[4],
        last_active_at_utc=row[5],
    )

    effective = compute_effective_streak(streak.current_streak, streak.last_active_local_date, today_local, has_subscription_protection)
    return streak, effective, today_local


def get_streak(db: Session, user_id: str, has_subscription_protection: bool = False) -> Tuple[Optional[UserStreak], int, Optional[datetime.date]]:
    """
    Get user's streak information considering subscription protection.
    
    Args:
        db: Database session
        user_id: User ID
        has_subscription_protection: Whether user has active subscription
        
    Returns:
        Tuple of (UserStreak, effective_streak, today_local_date)
    """
    now_utc = datetime.now(dt_timezone.utc)
    streak: Optional[UserStreak] = db.query(UserStreak).filter(UserStreak.user_id == user_id).first()
    if not streak:
        return None, 0, None
    today_local = _get_today_in_tz(now_utc, streak.timezone or "Asia/Kolkata")
    effective = compute_effective_streak(streak.current_streak, streak.last_active_local_date, today_local, has_subscription_protection)
    return streak, effective, today_local 