from sqlalchemy import Column, String, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class Friendship(Base):
    """Friendship model for storing confirmed friendships between users."""
    __tablename__ = "friendships"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user1_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user2_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user1 = relationship("User", foreign_keys=[user1_id], back_populates="friendships_as_user1")
    user2 = relationship("User", foreign_keys=[user2_id], back_populates="friendships_as_user2")
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('user1_id', 'user2_id', name='unique_friendship'),
    )
    
    def __repr__(self):
        return f"<Friendship id={self.id} user1={self.user1_id} user2={self.user2_id}>" 