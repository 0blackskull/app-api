from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    """User model for storing Firebase user information and user data in the database."""
    __tablename__ = "users"

    id = Column(String, primary_key=True)  # Firebase UID
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True, nullable=True)  # Optional unique username
    display_name = Column(String, nullable=True)
    pronouns = Column(String, nullable=True)
    
    # User data fields (consolidated from previous Profile model)
    name = Column(String, nullable=True)  # Made nullable since existing users might not have it
    gender = Column(String(10), nullable=True)  # 'male', 'female', 'other'
    city_of_birth = Column(String, nullable=True)
    current_residing_city = Column(String, nullable=True)
    time_of_birth = Column(DateTime, nullable=True)
    life_events_json = Column(Text, nullable=True)
    is_past_fact_visible = Column(Boolean, nullable=False, default=True)
    trust_analysis = Column(Text, nullable=True)  # Trust and behavior analysis
    
    # Subscription fields
    subscription_type = Column(String, default="free", nullable=False)  # free, monthly, yearly
    subscription_status = Column(String, default="inactive", nullable=False)  # active, cancelled, expired, grace_period
    subscription_end_date = Column(DateTime, nullable=True)  # When subscription expires
    state = Column(String, default="inactive", nullable=False)  # User activation state
    credits = Column(Integer, default=3, nullable=False)  # Chat credits - 3 free credits initially
    has_unlimited_chat = Column(Boolean, default=False, nullable=False)  # Whether user has unlimited chat access
    genz_style_enabled = Column(Boolean, default=False, nullable=False)  # Whether Tara should use GenZ style for this user
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships - one to many
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    chat_threads = relationship("ChatThread", back_populates="user", cascade="all, delete-orphan")
    partners = relationship("Partner", back_populates="user", cascade="all, delete-orphan")
    google_play_payments = relationship("GooglePlayPayment", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    rants = relationship("Rant", back_populates="user", cascade="all, delete-orphan")
    
    # Friend relationships
    sent_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.requester_id", back_populates="requester", cascade="all, delete-orphan")
    received_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.recipient_id", back_populates="recipient", cascade="all, delete-orphan")
    friendships_as_user1 = relationship("Friendship", foreign_keys="Friendship.user1_id", back_populates="user1", cascade="all, delete-orphan")
    friendships_as_user2 = relationship("Friendship", foreign_keys="Friendship.user2_id", back_populates="user2", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User id={self.id} email={self.email} username={self.username} name={self.name}>" 