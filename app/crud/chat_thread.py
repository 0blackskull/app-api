from sqlalchemy.orm import Session
from app.models import ChatThread
from typing import List, Optional
from app.models import Message
from sqlalchemy import func


def _verify_thread_user_ownership(db: Session, thread_id: str, user_id: str) -> Optional[ChatThread]:
    """Verify that a thread belongs to a specific user."""
    return db.query(ChatThread).filter(
        ChatThread.id == thread_id,
        ChatThread.user_id == user_id
    ).first()


def create_chat_thread(
    db: Session,
    user_id: str,
    title: str,
    participant_user_ids: Optional[List[str]] = None,
    participant_partner_ids: Optional[List[str]] = None,
    compatibility_type: Optional[str] = None,
    ashtakoota_raw_json: Optional[str] = None,
) -> ChatThread:
    """Create a new chat thread for a user (no business logic)."""
    db_thread = ChatThread(
        user_id=user_id,
        title=title,
    )
    if participant_user_ids is not None:
        db_thread.participant_user_ids = participant_user_ids
    if participant_partner_ids is not None:
        db_thread.participant_partner_ids = participant_partner_ids
    if compatibility_type is not None:
        db_thread.compatibility_type = compatibility_type
    if ashtakoota_raw_json is not None:
        db_thread.ashtakoota_raw_json = ashtakoota_raw_json

    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)
    return db_thread


def get_chat_thread(db: Session, thread_id: str, user_id: str) -> Optional[ChatThread]:
    """Get a specific chat thread by ID, verifying user ownership."""
    return _verify_thread_user_ownership(db, thread_id, user_id)


def get_user_threads(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[ChatThread]:
    """Get all chat threads for a user with pagination."""
    return db.query(ChatThread).filter(
        ChatThread.user_id == user_id
    ).order_by(ChatThread.updated_at.desc()).offset(skip).limit(limit).all()


def update_chat_thread(db: Session, thread_id: str, user_id: str, **kwargs) -> Optional[ChatThread]:
    """Update a chat thread, verifying user ownership."""
    thread = _verify_thread_user_ownership(db, thread_id, user_id)
    if not thread:
        return None
    
    # Update fields
    for key, value in kwargs.items():
        if hasattr(thread, key):
            setattr(thread, key, value)
    
    thread.updated_at = func.now()
    db.commit()
    db.refresh(thread)
    return thread


def delete_chat_thread(db: Session, thread_id: str, user_id: str) -> bool:
    """Delete a chat thread, verifying user ownership."""
    thread = _verify_thread_user_ownership(db, thread_id, user_id)
    if not thread:
        return False
    
    db.delete(thread)
    db.commit()
    return True


def get_thread_message_count(db: Session, thread_id: str, user_id: str) -> int:
    """Get the count of messages in a specific thread for a user"""
    thread = get_chat_thread(db, thread_id, user_id)
    if not thread:
        return 0
    
    return db.query(Message).filter(Message.thread_id == thread_id).count() 