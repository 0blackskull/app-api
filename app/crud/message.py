from sqlalchemy.orm import Session
from app.models import Message
from typing import List, Optional

def get_messages(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[Message]:
    """Get all messages for a user."""
    return db.query(Message).filter(
        Message.user_id == user_id
    ).order_by(Message.created_at).offset(skip).limit(limit).all()

def create_message(db: Session, user_id: str, role: str, query: str, content: str, thread_id: str) -> Message:
    """Create a new message"""
    db_message = Message(
        user_id=user_id,
        role=role,
        query=query,
        content=content,
        thread_id=thread_id
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

def get_last_messages(db: Session, user_id: str, n: int = 3, skip: int = 0) -> List[Message]:
    """Get the last n messages for a user, most recent last, with optional skip."""
    return db.query(Message).filter(
        Message.user_id == user_id
    ).order_by(Message.created_at.desc()).offset(skip).limit(n).all()[::-1]

def get_thread_messages(db: Session, thread_id: str, skip: int = 0, limit: int = 100) -> List[Message]:
    """Get messages for a specific thread with pagination"""
    return db.query(Message).filter(
        Message.thread_id == thread_id
    ).order_by(Message.created_at.desc()).offset(skip).limit(limit).all()

def get_last_thread_messages(db: Session, thread_id: str, n: int = 3, skip: int = 0) -> List[Message]:
    """Get the last N messages for a specific thread"""
    return db.query(Message).filter(
        Message.thread_id == thread_id
    ).order_by(Message.created_at.desc()).offset(skip).limit(n).all() 

