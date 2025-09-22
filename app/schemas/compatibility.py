from datetime import datetime
from pydantic import BaseModel, validator
from typing import Optional
from app.llm.schemas import CompatibilityAnalysis

class CompatibilityBase(BaseModel):
    user_id: str
    partner_id: Optional[str] = None
    other_user_id: Optional[str] = None
    result_json: str

    @validator('partner_id', 'other_user_id')
    def validate_exclusive_ids(cls, v, values):
        """Ensure either partner_id or other_user_id is provided, but not both."""
        if 'partner_id' in values and 'other_user_id' in values:
            if values['partner_id'] is not None and values['other_user_id'] is not None:
                raise ValueError("Cannot have both partner_id and other_user_id")
            if values['partner_id'] is None and values['other_user_id'] is None:
                raise ValueError("Must provide either partner_id or other_user_id")
        return v

class CompatibilityCreate(CompatibilityBase):
    pass

class Compatibility(CompatibilityBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CompatibilityReport(BaseModel):
    """Schema for a compatibility report with partner details and analysis."""
    id: str
    partner_id: Optional[str] = None
    other_user_id: Optional[str] = None
    partner_name: Optional[str] = None
    partner_gender: Optional[str] = None
    other_user_name: Optional[str] = None
    other_user_gender: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    analysis: CompatibilityAnalysis

    class Config:
        from_attributes = True 