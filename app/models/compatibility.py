from sqlalchemy import Column, DateTime, ForeignKey, Text, UniqueConstraint, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class Compatibility(Base):
    """Compatibility model for storing astrological compatibility results between users and partners or between users."""
    __tablename__ = "compatibilities"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    partner_id = Column(String, ForeignKey("partners.id", ondelete="CASCADE"), nullable=True)  # Optional for user-user compatibility
    other_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)  # For user-user compatibility
    report_type = Column(String(20), nullable=False, default="love")  # 'love' or 'friendship'
    result_json = Column(Text, nullable=False)  # JSON string of CompatibilityAnalysis
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    partner = relationship("Partner")
    other_user = relationship("User", foreign_keys=[other_user_id])
    
    # Ensure unique compatibility result per user-partner pair OR user-other_user pair, scoped by report_type
    __table_args__ = (
        UniqueConstraint('user_id', 'partner_id', 'report_type', name='uq_user_partner_compatibility'),
        UniqueConstraint('user_id', 'other_user_id', 'report_type', name='uq_user_other_user_compatibility'),
    )
    
    def __repr__(self):
        if self.partner_id:
            return f"<Compatibility id={self.id} user_id={self.user_id} partner_id={self.partner_id} type={self.report_type}>"
        else:
            return f"<Compatibility id={self.id} user_id={self.user_id} other_user_id={self.other_user_id} type={self.report_type}>" 