from pydantic import BaseModel, Field
from datetime import datetime


class RantRequest(BaseModel):
    """Schema for rant submission request."""
    content: str = Field(..., min_length=1, max_length=2000, description="The rant or expression content")


class RantResponse(BaseModel):
    """Schema for rant submission response."""
    rant_id: str = Field(..., description="Unique identifier for the rant")
    therapist_response: str = Field(..., description="Therapeutic response from the AI")
    is_valid_rant: bool = Field(..., description="Whether the content was validated as a genuine rant")
    rant_type: str = Field(..., description="Classification of the rant content")
    emotional_tone: str = Field(..., description="Analysis of emotional tone")
    validation_reasoning: str = Field(..., description="Explanation of validation decision")
    streak_updated: bool = Field(..., description="Whether the user's streak was updated")
    current_streak: int = Field(..., description="User's current streak after processing")
    longest_streak: int = Field(..., description="User's longest streak")
    submitted_at: datetime = Field(..., description="When the rant was submitted")
    
    class Config:
        from_attributes = True 