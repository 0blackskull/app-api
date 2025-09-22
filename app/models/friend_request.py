from sqlalchemy import Column, String, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum
import uuid

class FriendRequestStatus(enum.Enum):
    PENDING = "pending"

class FriendRequest(Base):
    """Friend request model for managing friend requests between users."""
    __tablename__ = "friend_requests"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    requester_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, default="pending", nullable=False)  # Use string directly to match database enum
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    requester = relationship("User", foreign_keys=[requester_id], back_populates="sent_friend_requests")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="received_friend_requests")
    
    # Composite unique constraint to prevent duplicate requests
    __table_args__ = (
        UniqueConstraint('requester_id', 'recipient_id', name='unique_friend_request'),
    )
    
    def __repr__(self):
        return f"<FriendRequest id={self.id} requester={self.requester_id} recipient={self.recipient_id} status={self.status}>" 