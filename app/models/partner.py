from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class Partner(Base):
    """Partner model for storing partner information for astrological compatibility."""
    __tablename__ = "partners"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    gender = Column(String(10), nullable=True)  # 'male', 'female', 'other'
    city_of_birth = Column(String, nullable=False)
    time_of_birth = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="partners")
    
    def __repr__(self):
        return f"<Partner id={self.id} name={self.name}>" 