from sqlalchemy.orm import Session
from app.models.compatibility import Compatibility
from typing import Optional

def create_compatibility(db: Session, user_id: str, partner_id: Optional[str] = None, other_user_id: str = None, result_json: str = None, report_type: str = "love") -> Compatibility:
    """Create a new compatibility record. Either partner_id or other_user_id must be provided."""
    if not partner_id and not other_user_id:
        raise ValueError("Either partner_id or other_user_id must be provided")
    
    db_compatibility = Compatibility(
        user_id=user_id,
        partner_id=partner_id,
        other_user_id=other_user_id,
        report_type=report_type,
        result_json=result_json
    )
    db.add(db_compatibility)
    db.commit()
    db.refresh(db_compatibility)
    return db_compatibility

def get_compatibility(db: Session, user_id: str, partner_id: Optional[str] = None, other_user_id: str = None, report_type: str = "love") -> Compatibility:
    """Get compatibility record for a specific user-partner pair or user-other_user pair scoped by report_type."""
    if partner_id:
        return db.query(Compatibility).filter(
            Compatibility.user_id == user_id,
            Compatibility.partner_id == partner_id,
            Compatibility.report_type == report_type,
        ).first()
    elif other_user_id:
        return db.query(Compatibility).filter(
            Compatibility.user_id == user_id,
            Compatibility.other_user_id == other_user_id,
            Compatibility.report_type == report_type,
        ).first()
    else:
        raise ValueError("Either partner_id or other_user_id must be provided")

def get_user_compatibilities(db: Session, user_id: str) -> list[Compatibility]:
    """Get all compatibility records for a specific user (both partner and user-user)."""
    return db.query(Compatibility).filter(
        Compatibility.user_id == user_id
    ).all()

def update_compatibility(db: Session, user_id: str, partner_id: Optional[str] = None, other_user_id: str = None, result_json: str = None, report_type: str = "love") -> Compatibility:
    """Update existing compatibility record scoped by report_type."""
    compatibility = get_compatibility(db, user_id, partner_id, other_user_id, report_type)
    if compatibility:
        compatibility.result_json = result_json
        db.commit()
        db.refresh(compatibility)
        return compatibility
    return None

def get_or_create_compatibility(db: Session, user_id: str, partner_id: Optional[str] = None, other_user_id: str = None, result_json: str = None, report_type: str = "love") -> Compatibility:
    """Get existing compatibility or create new one if result_json provided, scoped by report_type."""
    existing = get_compatibility(db, user_id, partner_id, other_user_id, report_type)
    if existing:
        return existing
    elif result_json:
        return create_compatibility(db, user_id, partner_id, other_user_id, result_json, report_type)
    return None 