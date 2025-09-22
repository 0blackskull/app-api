from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from app.models.rant import Rant


def create_rant(db: Session, rant_data: dict) -> Rant:
    """
    Create a new rant record in the database.
    
    Args:
        db: Database session
        rant_data: Dictionary containing rant information
        
    Returns:
        Created Rant object
    """
    db_rant = Rant(**rant_data)
    db.add(db_rant)
    db.commit()
    db.refresh(db_rant)
    return db_rant


def get_rants_by_user(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> list[Rant]:
    """
    Get rants for a specific user.
    
    Args:
        db: Database session
        user_id: User ID to get rants for
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of Rant objects
    """
    return db.query(Rant).filter(
        Rant.user_id == user_id
    ).order_by(Rant.submitted_at.desc()).offset(skip).limit(limit).all()


def get_rant_by_id(db: Session, rant_id: str, user_id: str) -> Optional[Rant]:
    """Get a specific rant by ID for a specific user"""
    return db.query(Rant).filter(
        Rant.id == rant_id,
        Rant.user_id == user_id
    ).first()


def get_rant_count_by_user(db: Session, user_id: str) -> int:
    """
    Get the total count of rants for a user.
    
    Args:
        db: Database session
        user_id: User ID to count rants for
        
    Returns:
        Total number of rants
    """
    return db.query(Rant).filter(Rant.user_id == user_id).count() 