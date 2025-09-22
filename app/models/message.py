from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class Message(Base):
    """Message model for storing chat messages."""
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    thread_id = Column(String, ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    query = Column(Text, nullable=False)  # The question asked
    content = Column(Text, nullable=False)  # The answer received
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="messages")
    thread = relationship("ChatThread", back_populates="messages")
    
    def __repr__(self):
        return f"<Message id={self.id} user_id={self.user_id} thread_id={self.thread_id}>" 