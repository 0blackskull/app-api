from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Rant(Base):
    """Model for storing user rant submissions."""
    __tablename__ = "rants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Rant content and analysis
    content = Column(Text, nullable=False)
    therapist_response = Column(Text, nullable=False)
    is_valid_rant = Column(Boolean, nullable=False)
    rant_type = Column(String(50), nullable=False)  # gratitude, complaint, random, etc.
    emotional_tone = Column(String(100), nullable=False)
    validation_reasoning = Column(Text, nullable=False)
    
    # Streak information at time of submission
    streak_updated = Column(Boolean, nullable=False, default=False)
    current_streak = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    submitted_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="rants")
    
    def __repr__(self) -> str:
        return f"<Rant id={self.id} user_id={self.user_id} type={self.rant_type} valid={self.is_valid_rant}>" 