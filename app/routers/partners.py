from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.partner import Partner, PartnerCreate
from app.crud import partner as partner_crud
from app.auth import get_current_user
from app.agents.tools import get_lat_long, get_timezone, get_panchanga
from app.agents.astrology_utils import get_moon_sign_name
from uuid import UUID

router = APIRouter(
    prefix="/partners",
    tags=["partners"]
)

@router.post("/", response_model=Partner)
def create_partner(
    partner: PartnerCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Override the user_id with current user to ensure security
    partner.user_id = current_user.id
    
    created_partner = partner_crud.create_partner(db=db, partner=partner)
    
    # Calculate moon sign similar to other endpoints
    try:
        lat, lon = get_lat_long(created_partner.city_of_birth)
        tz = get_timezone(lat, lon)
        birth_date = created_partner.time_of_birth.strftime('%Y-%m-%d')
        birth_time = created_partner.time_of_birth.strftime('%H:%M')
        panchanga = get_panchanga(birth_date, birth_time, tz, lon, lat)
        moon_rashi = panchanga.get('moon_rashi')
        moon_sign = get_moon_sign_name(moon_rashi)
    except Exception:
        moon_sign = None
    
    return {**created_partner.__dict__, 'moon_sign': moon_sign}

@router.get("/", response_model=List[Partner])
def get_partners_for_current_user(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    partners = partner_crud.get_partners_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    enriched_partners = []
    for partner in partners:
        try:
            lat, lon = get_lat_long(partner.city_of_birth)
            tz = get_timezone(lat, lon)
            birth_date = partner.time_of_birth.strftime('%Y-%m-%d')
            birth_time = partner.time_of_birth.strftime('%H:%M')
            panchanga = get_panchanga(birth_date, birth_time, tz, lon, lat)
            moon_rashi = panchanga.get('moon_rashi')
            moon_sign = get_moon_sign_name(moon_rashi)
        except Exception:
            moon_sign = None
        enriched_partners.append({**partner.__dict__, 'moon_sign': moon_sign})
    return enriched_partners

@router.get("/{partner_id}", response_model=Partner)
def get_partner(
    partner_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    partner = partner_crud.get_partner(db, partner_id=str(partner_id))
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    # Verify partner belongs to current user
    if partner.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Partner does not belong to current user")
    
    try:
        lat, lon = get_lat_long(partner.city_of_birth)
        tz = get_timezone(lat, lon)
        birth_date = partner.time_of_birth.strftime('%Y-%m-%d')
        birth_time = partner.time_of_birth.strftime('%H:%M')
        panchanga = get_panchanga(birth_date, birth_time, tz, lon, lat)
        moon_rashi = panchanga.get('moon_rashi')
        moon_sign = get_moon_sign_name(moon_rashi)
    except Exception:
        moon_sign = None
    return {**partner.__dict__, 'moon_sign': moon_sign}

@router.delete("/{partner_id}", response_model=Partner)
def delete_partner(
    partner_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    partner = partner_crud.get_partner(db, partner_id=str(partner_id))
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    # Verify partner belongs to current user
    if partner.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Partner does not belong to current user")
    
    deleted_partner = partner_crud.delete_partner(db, partner_id=str(partner_id))
    return deleted_partner 