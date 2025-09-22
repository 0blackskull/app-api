from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Boolean, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class GooglePlayPayment(Base):
    """Google Play payment model for storing in-app purchase information."""
    __tablename__ = "google_play_payments"

    id = Column(String, primary_key=True)  # Order ID from Google Play
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(String, nullable=False, index=True)  # Google Play product ID
    purchase_token = Column(String, nullable=False, unique=True, index=True)  # Google Play purchase token
    amount = Column(Integer, nullable=False)  # Amount in smallest currency unit
    currency = Column(String, nullable=False, default="INR")
    status = Column(String, nullable=False, default="pending", index=True)  # pending, completed, failed, refunded
    purchase_state = Column(String, nullable=False, default="pending", index=True)  # purchased, pending
    # Track whether the in-app product has been consumed on Google Play ("0" = not consumed, "1" = consumed)
    consumption_state = Column(String, nullable=False, default="0", index=True)
    acknowledgment_state = Column(String, nullable=False, default="not_acknowledged", index=True)  # acknowledged, not_acknowledged
    is_acknowledged = Column(Boolean, nullable=False, default=False)
    # Distinguish purchase type (e.g., 'inapp' for one-time products). Subscriptions use the `subscriptions` table.
    purchase_type = Column(String, nullable=False, default="inapp", index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationship to user
    user = relationship("User", back_populates="google_play_payments")
    
    def __repr__(self):
        return f"<GooglePlayPayment id={self.id} user_id={self.user_id} product_id={self.product_id} status={self.status}>"

class Subscription(Base):
    """Google Play subscription model for storing subscription information."""
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True)  # Subscription ID from Google Play
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(String, nullable=False, index=True)  # Google Play subscription product ID
    purchase_token = Column(String, nullable=False, unique=True, index=True)  # Google Play purchase token
    status = Column(String, nullable=False, default="pending", index=True)  # active, cancelled, expired, pending
    purchase_state = Column(String, nullable=False, default="pending", index=True)  # purchased, pending
    start_time = Column(Integer, nullable=True)  # Subscription start timestamp (milliseconds)
    end_time = Column(Integer, nullable=True)  # Subscription end timestamp (milliseconds)
    acknowledgment_state = Column(String, nullable=False, default="not_acknowledged", index=True)  # acknowledged, not_acknowledged
    is_acknowledged = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationship to user
    user = relationship("User", back_populates="subscriptions")
    
    def __repr__(self):
        return f"<Subscription id={self.id} user_id={self.user_id} product_id={self.product_id} status={self.status}>" 

class PurchaseEvent(Base):
    """Model for storing RTDN events and their processing status."""
    __tablename__ = "purchase_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    message_id = Column(String, unique=True, index=True)  # Pub/Sub message ID for deduplication
    purchase_token = Column(String, nullable=False, index=True)  # Google Play purchase token
    user_id = Column(String, ForeignKey("users.id"), index=True)  # NULL until resolved
    product_id = Column(String)  # Google Play product ID
    event_type = Column(String)  # 'purchase', 'renewal', 'cancel', etc.
    status = Column(String, default="pending")  # 'pending', 'processed', 'failed'
    raw_payload = Column(JSON)  # Store full RTDN payload
    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime)

    def __repr__(self):
        return f"<PurchaseEvent id={self.id} purchase_token={self.purchase_token} status={self.status}>" 