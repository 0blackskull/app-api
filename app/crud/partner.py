from sqlalchemy.orm import Session
from app.models.partner import Partner
from app.schemas.partner import PartnerCreate

def create_partner(db: Session, partner: PartnerCreate) -> Partner:
    db_partner = Partner(
        user_id=partner.user_id,
        name=partner.name,
        gender=partner.gender,
        city_of_birth=partner.city_of_birth,
        time_of_birth=partner.time_of_birth
    )
    db.add(db_partner)
    db.commit()
    db.refresh(db_partner)
    return db_partner

def get_partners_by_user(db: Session, user_id: str, skip: int = 0, limit: int = 100):
    return db.query(Partner).filter(Partner.user_id == user_id).offset(skip).limit(limit).all()

def get_partner(db: Session, partner_id: str):
    return db.query(Partner).filter(Partner.id == partner_id).first()

def delete_partner(db: Session, partner_id: str):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if partner:
        db.delete(partner)
        db.commit()
    return partner 