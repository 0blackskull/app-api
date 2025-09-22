from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class PartnerBase(BaseModel):
    name: str
    gender: Optional[str] = None  # 'male', 'female', 'other'
    city_of_birth: str
    time_of_birth: datetime

class PartnerCreate(PartnerBase):
    user_id: str

class Partner(PartnerBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    moon_sign: str | None = None

    class Config:
        from_attributes = True 