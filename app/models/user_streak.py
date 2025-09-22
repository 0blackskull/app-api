from sqlalchemy import Column, String, Date, DateTime, Integer, ForeignKey, UniqueConstraint, text
from app.database import Base


class UserStreak(Base):
    __tablename__ = "user_streaks"

    # Use user_id as primary key to ensure one row per user
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    timezone = Column(String, nullable=False, default="Asia/Kolkata")

    # Streak counters
    current_streak = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)

    # Dates/timestamps
    last_active_local_date = Column(Date, nullable=True)
    last_active_at_utc = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=text('now()'))
    updated_at = Column(DateTime, server_default=text('now()'))

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_streaks_user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserStreak user_id={self.user_id} current={self.current_streak} "
            f"longest={self.longest_streak} last_local={self.last_active_local_date} tz={self.timezone}>"
        ) 