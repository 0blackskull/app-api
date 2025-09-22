from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    fcm_token = Column(String, unique=True, nullable=False)
    platform = Column(String, nullable=True)  # "ios" | "android" | "web"
    app_version = Column(String, nullable=True)
    lang = Column(String, nullable=True)
    push_enabled = Column(Boolean, default=True, nullable=False)

    last_seen = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("fcm_token", name="uq_devices_fcm_token"),
    )