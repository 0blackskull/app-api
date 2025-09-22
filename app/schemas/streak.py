from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class StreakResponse(BaseModel):
    user_id: str
    timezone: str
    current_streak: int
    longest_streak: int
    last_active_local_date: Optional[date]
    last_active_at_utc: Optional[datetime]
    effective_streak: int
    today_local_date: date

    class Config:
        from_attributes = True 