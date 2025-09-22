from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

class ChatThreadBase(BaseModel):
    """Base chat thread schema with common attributes"""
    title: str = Field(..., min_length=1, max_length=255, description="Thread title")

class ChatThreadCreate(ChatThreadBase):
    """Schema for creating a new chat thread"""
    participant_user_ids: Optional[List[str]] = Field(None, description="Participant user IDs to associate with the thread")
    participant_partner_ids: Optional[List[str]] = Field(None, description="Participant partner IDs to associate with the thread")
    compatibility_type: Optional[Literal["love", "friendship"]] = Field(None, description="When exactly one participant is present, set the compatibility context type")

class ChatThreadUpdate(BaseModel):
    """Schema for updating a chat thread"""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Thread title")
    participant_user_ids: Optional[List[str]] = Field(None, description="Replace participant user IDs for the thread")
    participant_partner_ids: Optional[List[str]] = Field(None, description="Replace participant partner IDs for the thread")
    compatibility_type: Optional[Literal["love", "friendship", None]] = Field(None, description="Set or clear the compatibility context type")


class ChatThread(ChatThreadBase):
    """Schema for chat thread response"""
    id: str
    user_id: str
    is_title_edited: bool
    auto_generated_title: Optional[str] = None
    participant_user_ids: Optional[List[str]] = None
    participant_partner_ids: Optional[List[str]] = None
    compatibility_type: Optional[Literal["love", "friendship"]] = None

    # Enriched participant names for convenience in UI
    participant_user_names: Optional[List[str]] = None
    participant_partner_names: Optional[List[str]] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 