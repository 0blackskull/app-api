from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Dict, Any
from datetime import datetime
import re

class UserBase(BaseModel):
    """Base user schema with common attributes"""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    pronouns: Optional[str] = None
    state: Optional[str] = None
    genz_style_enabled: Optional[bool] = None
    
    # User data fields (consolidated from previous Profile schema)
    name: Optional[str] = None
    gender: Optional[str] = None  # 'male', 'female', 'other'
    city_of_birth: Optional[str] = None
    current_residing_city: Optional[str] = None
    time_of_birth: Optional[datetime] = None
    is_past_fact_visible: Optional[bool] = None

    @validator('username')
    def validate_username(cls, v):
        if v is not None:
            # Username validation rules
            if len(v) < 3:
                raise ValueError('Username must be at least 3 characters long')
            if len(v) > 30:
                raise ValueError('Username must be at most 30 characters long')
            if not re.match(r'^[a-zA-Z0-9_]+$', v):
                raise ValueError('Username can only contain letters, numbers, and underscores')
            if v.lower() in ['admin', 'root', 'system', 'user', 'test', 'guest']:
                raise ValueError('Username is not allowed')
        return v

class UserUpdate(UserBase):
    """Schema for updating user information"""
    pass

class UserResponse(UserBase):
    """Schema for user response"""
    id: str
    subscription_type: str
    subscription_status: str
    subscription_end_date: Optional[datetime] = None
    credits: int
    has_unlimited_chat: bool
    genz_style_enabled: bool
    created_at: datetime
    updated_at: datetime
    state: str

    class Config:
        from_attributes = True

class CurrentUser(BaseModel):
    """Simplified user model for authentication responses"""
    id: str
    email: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    pronouns: Optional[str] = None
    credits: int

# Chart data schema (consolidated from previous profile schema)
class ChartData(BaseModel):
    name: Optional[str] = None  # Name of the chart (e.g., 'D1', 'D9', etc.)
    chart_info: Optional[Dict[str, Any]] = None
    charts: Optional[Dict[str, Any] | list[Any]] = None
    ascendant_house: Optional[int] = None
    error: Optional[str] = None 