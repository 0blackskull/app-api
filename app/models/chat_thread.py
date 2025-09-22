from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import json
import uuid

class ChatThread(Base):
    """ChatThread model for storing chat conversation threads."""
    __tablename__ = "chat_threads"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False, default="New Chat")
    is_title_edited = Column(Boolean, default=False)
    auto_generated_title = Column(String(255), nullable=True)

    participants_json = Column(Text, nullable=True)  # JSON string of {"user_ids": [...], "partner_ids": [...]} or None
    compatibility_type = Column(String(20), nullable=True)  # 'love' or 'friendship' when one participant present
    ashtakoota_raw_json = Column(Text, nullable=True)  # cached raw ashtakoota dict for current participants+type

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="chat_threads")
    messages = relationship("Message", back_populates="thread", cascade="all, delete-orphan")

    def _get_participants_obj(self) -> dict:
        if not self.participants_json:
            return {"user_ids": [], "partner_ids": []}
        try:
            data = json.loads(self.participants_json)
            if isinstance(data, dict):
                return {
                    "user_ids": [str(x) for x in (data.get("user_ids") or [])],
                    "partner_ids": [str(x) for x in (data.get("partner_ids") or [])],
                }
            # No backward-compat for legacy list shapes per requirements
            return {"user_ids": [], "partner_ids": []}
        except Exception:
            return {"user_ids": [], "partner_ids": []}

    def _set_participants_obj(self, user_ids: list[str] | None, partner_ids: list[str] | None) -> None:
        user_ids = user_ids or []
        partner_ids = partner_ids or []
        unique_user_ids: list[str] = []
        seen_u = set()
        for v in user_ids:
            sv = str(v)
            if sv not in seen_u:
                seen_u.add(sv)
                unique_user_ids.append(sv)
        unique_partner_ids: list[str] = []
        seen_p = set()
        for v in partner_ids:
            sv = str(v)
            if sv not in seen_p:
                seen_p.add(sv)
                unique_partner_ids.append(sv)
        self.participants_json = json.dumps({"user_ids": unique_user_ids, "partner_ids": unique_partner_ids})

    @property
    def participant_user_ids(self) -> list[str] | None:
        obj = self._get_participants_obj()
        return obj["user_ids"] or None

    @participant_user_ids.setter
    def participant_user_ids(self, value: list[str] | None) -> None:
        current = self._get_participants_obj()
        self._set_participants_obj(value, current["partner_ids"])

    @property
    def participant_partner_ids(self) -> list[str] | None:
        obj = self._get_participants_obj()
        return obj["partner_ids"] or None

    @participant_partner_ids.setter
    def participant_partner_ids(self, value: list[str] | None) -> None:
        current = self._get_participants_obj()
        self._set_participants_obj(current["user_ids"], value)

    
    def __repr__(self):
        return f"<ChatThread id={self.id} user_id={self.user_id} title='{self.title}'>" 