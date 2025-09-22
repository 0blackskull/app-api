from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from app.utils.logger import get_logger
import json
from fastapi.responses import JSONResponse
from uuid import UUID
from datetime import datetime, timedelta
import pytz

from app.database import get_db
from app.auth import get_current_user
from app import schemas, crud
from app.crud.user import get_user, update_user_fields, is_username_available, get_users_by_username_pattern, update_user_trust_analysis
from app.crud.friends import FriendsCRUD
from app.models import Message
from app.llm.client import LLMClient
from app.llm.schemas import CompatibilityAnalysis, DailyFacts, WeeklyHoroscope, LifeEvents
from app.agents.tools import get_panchanga, get_lat_long, get_timezone
from app.agents.astrology_utils import get_moon_sign_name
from app.schemas.compatibility import CompatibilityReport
from app.cache import get_daily_facts_from_cache, set_daily_facts_in_cache, get_weekly_horoscope_from_cache, set_weekly_horoscope_in_cache, clear_user_cache
from app.agents.astrology_utils import get_comprehensive_weekly_data
from app.services.compatibility_service import compute_ashtakoota_raw_json_for_context
from app.crud.subscription import get_active_subscription
from app.schemas.payment import SubscriptionResponse

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}}
)

logger = get_logger(__name__)

# Initialize LLM client
llm_client = LLMClient()

# Note: friendship caching helper exists in chat router; threads endpoints validate via CRUD directly

def _validate_participant_users(
    db: Session,
    current_user: schemas.CurrentUser,
    participant_user_ids: List[str]
) -> List[str]:
    """Validate participant user IDs (self or friends). Allow clearing via empty list."""
    if participant_user_ids is None:
        return []
    if len(participant_user_ids) == 0:
        return []

    valid_ids: List[str] = []
    for uid in participant_user_ids:
        suid = str(uid)
        if suid == current_user.id:
            valid_ids.append(suid)
            continue
        if crud.FriendsCRUD._are_friends(db, current_user.id, suid):
            valid_ids.append(suid)
            continue
        raise HTTPException(status_code=403, detail=f"Not authorized to include user {suid}")
    seen = set()
    unique: List[str] = []
    for x in valid_ids:
        if x not in seen:
            seen.add(x)
            unique.append(x)
    return unique

def _validate_participant_partners(
    db: Session,
    user_id: str,
    participant_partner_ids: List[str]
) -> List[str]:
    """Validate participant partner IDs belong to the user. Allow clearing via empty list."""
    if participant_partner_ids is None:
        return []
    if len(participant_partner_ids) == 0:
        return []

    valid_ids: List[str] = []
    seen: set[str] = set()
    for pid in participant_partner_ids:
        try:
            spid = str(pid)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid partner ID {pid}")
        partner = crud.get_partner(db, spid)
        if not partner or partner.user_id != user_id:
            raise HTTPException(status_code=403, detail=f"Not authorized to include partner {spid}")
        if spid not in seen:
            seen.add(spid)
            valid_ids.append(spid)
    return valid_ids

def _get_user_display_name(u) -> str:
    """Best-effort human-friendly name for a user."""
    return (getattr(u, "display_name", None) or getattr(u, "name", None) or getattr(u, "username", None) or u.id)

def _enrich_thread_with_participant_names(db: Session, thread) -> dict:
    """Build a dict for a thread including participant names for UI convenience."""
    # Start from ORM object using from_orm to respect properties
    base = schemas.ChatThread.from_orm(thread).dict()

    user_names: list[str] = []
    for uid in base.get("participant_user_ids") or []:
        friend = crud.get_user(db, uid)
        if friend:
            user_names.append(_get_user_display_name(friend))
    partner_names: list[str] = []
    for pid in base.get("participant_partner_ids") or []:
        partner = crud.get_partner(db, pid)
        if partner:
            partner_names.append(partner.name)

    base["participant_user_names"] = user_names or []
    base["participant_partner_names"] = partner_names or []
    return base

def _calculate_max_score(analysis: CompatibilityAnalysis, compatibility_type: str) -> int:
    """Calculate max_score by summing individual aspect max scores based on compatibility type."""
    if compatibility_type == 'friendship':
        # For friendship, exclude sexual_match (Yoni) which has max score 4
        return 36 - 4  # 32
    else:
        # For love compatibility, include all aspects
        return 36

def _add_max_score_to_analysis(analysis: CompatibilityAnalysis, compatibility_type: str) -> CompatibilityAnalysis:
    """Add max_score field to analysis before sending response."""
    max_score = _calculate_max_score(analysis, compatibility_type)
    
    # Create a copy of the analysis with max_score added
    analysis_dict = analysis.dict()
    analysis_dict['max_score'] = max_score
    
    # Recalculate overall_match_percentage based on actual max_score
    if max_score > 0:
        analysis_dict['overall_match_percentage'] = (analysis_dict['total_score'] / max_score) * 100
    
    return CompatibilityAnalysis(**analysis_dict)

@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the current user's information"""
    db_user = get_user(db, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.get("/me/subscription")
async def get_current_user_active_subscription(
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return the current user's active subscription (if any) with product details.
    """
    sub = get_active_subscription(db, current_user.id)
    if not sub:
        return {"active_subscription": None}
    return {"active_subscription": SubscriptionResponse.from_orm(sub)}

@router.patch("/me", response_model=schemas.UserResponse)
async def update_user_info(
    user_update: schemas.UserUpdate,
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the current user's information"""
    # Get current user from database
    db_user = get_user(db, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Extract update data from request
    update_data = user_update.dict(exclude_unset=True)
    
    # Check if genz_style_enabled is being changed
    genz_style_changed = False
    if 'genz_style_enabled' in update_data:
        current_genz_style = getattr(db_user, 'genz_style_enabled', False)
        new_genz_style = update_data['genz_style_enabled']
        genz_style_changed = current_genz_style != new_genz_style
        logger.info(f"GenZ style change detected for user {current_user.id}: {current_genz_style} -> {new_genz_style}")
    
    # Update user data (including username validation)
    if update_data:
        try:
            db_user = update_user_fields(db, db_user, update_data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except IntegrityError:
            raise HTTPException(status_code=400, detail="Update failed due to constraint violation")
    
    # Clear all user cache if GenZ style was changed
    if genz_style_changed:
        logger.info(f"Clearing all cache for user {current_user.id} due to GenZ style change")
        cache_cleared = clear_user_cache(current_user.id)
        if cache_cleared:
            logger.info(f"Successfully cleared cache for user {current_user.id}")
        else:
            logger.warning(f"Failed to clear cache for user {current_user.id}")
    
    # Get the updated user
    db_user = get_user(db, current_user.id)
    return db_user

@router.get("/check-username")
async def check_username_availability(
    username: str,
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if a username is available"""
    is_available = is_username_available(db, username, exclude_user_id=None)
    return {"username": username, "available": is_available}

@router.get("/search-username")
async def search_users_by_username(
    username_pattern: str,
    limit: int = 10,
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search users by username pattern (for autocomplete/search)"""
    if len(username_pattern) < 2:
        raise HTTPException(status_code=400, detail="Username pattern must be at least 2 characters")
    
    users = get_users_by_username_pattern(db, username_pattern, limit=min(limit, 50))

    # Exclude current user from results if present
    users = [u for u in users if u.id != current_user.id]

    other_user_ids = [u.id for u in users]
    status_map = FriendsCRUD.get_relationship_status_map(db, current_user.id, other_user_ids)

    return {
        "users": [
            {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "relationship_status": status_map.get(user.id, "none")
            }
            for user in users
        ]
    }

# User-related endpoints

@router.get("/me/messages", response_model=List[schemas.Message])
async def get_user_messages(
    skip: int = Query(0, description="Number of messages to skip", ge=0),
    limit: int = Query(20, description="Maximum number of messages to return", ge=1, le=100),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get messages for the current user.
    
    Args:
        skip: Number of messages to skip for pagination
        limit: Maximum number of messages to return
        current_user: The authenticated user
        db: Database session
        
    Returns:
        List of messages ordered by creation date (oldest first)
    """
    
    # Get messages using the user_id directly
    messages = db.query(Message).filter(
        Message.user_id == current_user.id
    ).order_by(Message.created_at.desc()).offset(skip).limit(limit).all()
    
    return messages

@router.get("/me/threads/{thread_id}/messages", response_model=List[schemas.Message])
async def get_user_thread_messages(
    thread_id: UUID = Path(..., description="The ID of the thread"),
    skip: int = Query(0, description="Number of messages to skip", ge=0),
    limit: int = Query(20, description="Maximum number of messages to return", ge=1, le=100),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get messages for a specific thread belonging to the current user.
    
    Args:
        thread_id: The ID of the thread
        skip: Number of messages to skip for pagination
        limit: Maximum number of messages to return
        current_user: The authenticated user
        db: Database session
        
    Returns:
        List of messages in the thread ordered by creation date (newest first)
    """
    
    # Verify thread belongs to current user and get messages
    thread = crud.get_chat_thread(db, str(thread_id), current_user.id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    messages = crud.get_thread_messages(db, str(thread_id), skip, limit)
    return messages

async def _calculate_compatibility(
    db: Session,
    user: schemas.UserResponse,
    other_person_name: str,
    other_person_gender: str,
    other_person_birth_date: str,
    other_person_birth_time: str,
    other_person_city: str,
    user_id: str,
    partner_id: str = None,
    other_user_id: str = None,
    compatibility_type: str = "love",
) -> CompatibilityAnalysis:
    """Calculate compatibility between user and another person"""
    
    # Check for cached compatibility first
    existing_compatibility = crud.get_compatibility(db, user_id, partner_id, other_user_id, compatibility_type)
    if existing_compatibility:
        try:
            cached_analysis = json.loads(existing_compatibility.result_json)
            return CompatibilityAnalysis(**cached_analysis)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Corrupted compatibility cache for user {user_id}: {e}")
    
    # Get user's birth details
    if not user.time_of_birth or not user.city_of_birth:
        raise HTTPException(
            status_code=400, 
            detail="User birth information is incomplete. Please update your birth time and city."
        )
    
    user_birth_date = user.time_of_birth.strftime('%Y-%m-%d')
    user_birth_time = user.time_of_birth.strftime('%H:%M')
    
    # Get coordinates for both cities
    try:
        user_lat, user_lon = get_lat_long(user.city_of_birth)
        other_lat, other_lon = get_lat_long(other_person_city)
    except Exception as e:
        logger.error(f"Error getting coordinates: {e}")
        raise HTTPException(status_code=400, detail="Could not determine location for one or both users.")
    
    # Get timezones
    user_tz = get_timezone(user_lat, user_lon)
    other_tz = get_timezone(other_lat, other_lon)
    
    # Calculate compatibility using ashtakoota
    try:
        # Get astrological details for both users using panchanga
        user_details = get_panchanga(
            birth_date=user_birth_date,
            birth_time=user_birth_time,
            timezone=user_tz,
            longitude=user_lon,
            latitude=user_lat,
        )
        
        other_details = get_panchanga(
            birth_date=other_person_birth_date,
            birth_time=other_person_birth_time,
            timezone=other_tz,
            longitude=other_lon,
            latitude=other_lat,
        )
        
        # Calculate compatibility using the astrological parameters
        user_gender = user.gender or "unknown"
        other_gender = other_person_gender
        
        # Determine boy/girl roles for compatibility calculation
        if (compatibility_type == 'love' and 
            user_gender in {'male', 'female'} and 
            other_gender in {'male', 'female'} and 
            user_gender != other_gender):
            # Heterosexual love compatibility
            if user_gender == 'male':
                boy_rashi, boy_nak, boy_pada = user_details['moon_rashi'], user_details['nakshatra'], user_details['pada']
                girl_rashi, girl_nak, girl_pada = other_details['moon_rashi'], other_details['nakshatra'], other_details['pada']
            else:
                boy_rashi, boy_nak, boy_pada = other_details['moon_rashi'], other_details['nakshatra'], other_details['pada']
                girl_rashi, girl_nak, girl_pada = user_details['moon_rashi'], user_details['nakshatra'], user_details['pada']
        else:
            # Same gender or friendship: use first person as boy, second as girl for calculation
            boy_rashi, boy_nak, boy_pada = user_details['moon_rashi'], user_details['nakshatra'], user_details['pada']
            girl_rashi, girl_nak, girl_pada = other_details['moon_rashi'], other_details['nakshatra'], other_details['pada']
        
        # Import compatibility_ashtakoota here to avoid circular imports
        from app.agents.tools import compatibility_ashtakoota
        
        ashtakoota_result = compatibility_ashtakoota(
            boy_rashi=boy_rashi,
            boy_nakshatra=boy_nak,
            boy_pada=boy_pada,
            girl_rashi=girl_rashi,
            girl_nakshatra=girl_nak,
            girl_pada=girl_pada
        )
        
        # Generate detailed analysis using LLM
        llm_client = LLMClient()
        
        # Get detailed compatibility analysis from LLM
        analysis = await llm_client.analyze_compatibility(
            analysis_data=ashtakoota_result,
            person1_name=user.name or "User",
            person2_name=other_person_name,
            person1_details={
                "moon_rashi": user_details['moon_rashi'],
                "nakshatra": user_details['nakshatra'],
                "pada": user_details['pada']
            },
            person2_details={
                "moon_rashi": other_details['moon_rashi'],
                "nakshatra": other_details['nakshatra'],
                "pada": other_details['pada']
            },
            person1_gender=user.gender,
            person2_gender=other_person_gender,
            compatibility_type=compatibility_type
        )
        
        # Save to cache
        result_json = analysis.model_dump_json()
        result = crud.update_compatibility(db, user_id, partner_id, other_user_id, result_json, compatibility_type)
        if not result:  # If update failed (returned None), try to create
            try:
                result = crud.create_compatibility(db, user_id, partner_id, other_user_id, result_json, compatibility_type)
                if result:
                    logger.info(f"Successfully created compatibility for user {user_id}")
                else:
                    logger.error(f"Failed to create compatibility for user {user_id} - returned None")
            except Exception as e:
                logger.exception(f"Failed to save compatibility result for user {user_id}: {e}")
        else:
            logger.info(f"Successfully updated compatibility for user {user_id}")
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error calculating compatibility: {e}")
        raise HTTPException(status_code=500, detail="Error calculating compatibility")

@router.get("/me/compatibility/{partner_id}", response_model=CompatibilityAnalysis)
async def get_user_compatibility(
    partner_id: UUID = Path(..., description="The ID of the partner to analyze compatibility with"),
    compatibility_type: str = Query("love", description="Type of compatibility analysis", regex="^(love|friendship)$"),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get astrological compatibility analysis between current user and a partner.
    Checks cache first, calculates and saves if not found.
    """
    # Get current user
    user = crud.get_user(db, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get partner details
    partner = crud.get_partner(db, str(partner_id))
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    # Verify partner belongs to current user
    if partner.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Partner does not belong to current user")

    analysis = await _calculate_compatibility(
        db, user, partner.name, partner.gender, partner.time_of_birth.strftime('%Y-%m-%d'), 
        partner.time_of_birth.strftime('%H:%M'), partner.city_of_birth, current_user.id, 
        str(partner_id), compatibility_type=compatibility_type
    )
    
    if compatibility_type == 'friendship':
        data = analysis.dict()
        if 'sexual_match' in data:
            del data['sexual_match']
        if 'attraction_match' in data:
            data['dominance_match'] = data['attraction_match']
            del data['attraction_match']
        
        # Add max_score for friendship compatibility
        data['max_score'] = _calculate_max_score(analysis, compatibility_type)
        
        # Recalculate overall_match_percentage based on actual max_score
        if data['max_score'] > 0:
            data['overall_match_percentage'] = (data['total_score'] / data['max_score']) * 100
        
        return JSONResponse(content=data)
    return _add_max_score_to_analysis(analysis, compatibility_type)

@router.get("/me/compatibility-with-user/{other_user_id}", response_model=CompatibilityAnalysis)
async def get_user_compatibility_with_user(
    other_user_id: str = Path(..., description="The ID of the other user to analyze compatibility with"),
    compatibility_type: str = Query("love", description="Type of compatibility analysis", regex="^(love|friendship)$"),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get astrological compatibility analysis between current user and another user.
    Both users must be friends for this compatibility analysis to be performed.
    Checks cache first, calculates and saves if not found.
    """
    # Get current user
    user = crud.get_user(db, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify that users are friends
    if not crud.FriendsCRUD._are_friends(db, current_user.id, other_user_id):
        raise HTTPException(
            status_code=403, 
            detail="Compatibility analysis is only available between friends. Please send a friend request first."
        )

    # Get the other user
    other_user = crud.get_user(db, other_user_id)
    if not other_user:
        raise HTTPException(status_code=404, detail="Other user not found")
    
    # Check if other user has required data
    if not other_user.name or not other_user.time_of_birth or not other_user.city_of_birth:
        raise HTTPException(status_code=400, detail="Other user's information is incomplete")
    
    analysis = await _calculate_compatibility(
        db, user, other_user.name, other_user.gender, 
        other_user.time_of_birth.strftime('%Y-%m-%d'), 
        other_user.time_of_birth.strftime('%H:%M'), 
        other_user.city_of_birth, current_user.id, 
        other_user_id=other_user_id, compatibility_type=compatibility_type
    )
    
    if compatibility_type == 'friendship':
        data = analysis.dict()
        if 'sexual_match' in data:
            del data['sexual_match']
        if 'attraction_match' in data:
            data['dominance_match'] = data['attraction_match']
            del data['attraction_match']
        
        # Add max_score for friendship compatibility
        data['max_score'] = _calculate_max_score(analysis, compatibility_type)
        
        # Recalculate overall_match_percentage based on actual max_score
        if data['max_score'] > 0:
            data['overall_match_percentage'] = (data['total_score'] / data['max_score']) * 100
        
        return JSONResponse(content=data)
    return _add_max_score_to_analysis(analysis, compatibility_type)

@router.get("/me/compatibility-reports", response_model=List[CompatibilityReport])
async def get_user_compatibility_reports(
    skip: int = Query(0, description="Number of reports to skip", ge=0),
    limit: int = Query(20, description="Maximum number of reports to return", ge=1, le=100),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all compatibility reports for the current user.
    Returns both partner and user-to-user compatibility reports with analysis.
    """
    # Get user
    user = crud.get_user(db, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all compatibility records for this user
    compatibilities = crud.get_user_compatibilities(db, current_user.id)
    
    reports = []
    for compatibility in compatibilities:
        try:
            # Parse the stored analysis
            analysis_data = json.loads(compatibility.result_json)
            analysis = CompatibilityAnalysis(**analysis_data)
            
            # Add max_score based on the stored compatibility type
            analysis = _add_max_score_to_analysis(analysis, compatibility.report_type)
            
            # Build report based on whether it's partner or user compatibility
            if compatibility.partner_id:
                # Partner compatibility
                partner = crud.get_partner(db, str(compatibility.partner_id))
                if partner:
                    report = CompatibilityReport(
                        id=compatibility.id,
                        partner_id=compatibility.partner_id,
                        other_user_id=None,
                        partner_name=partner.name,
                        partner_gender=partner.gender,
                        other_user_name=None,
                        other_user_gender=None,
                        created_at=compatibility.created_at,
                        updated_at=compatibility.updated_at,
                        analysis=analysis
                    )
                    reports.append(report)
            elif compatibility.other_user_id:
                # User-to-user compatibility
                # Check if users are still friends
                if crud.FriendsCRUD._are_friends(db, current_user.id, compatibility.other_user_id):
                    other_user = crud.get_user(db, compatibility.other_user_id)
                else:
                    # Users are no longer friends, get basic info
                    other_user = crud.get_user(db, compatibility.other_user_id)
                
                if other_user:
                    report = CompatibilityReport(
                        id=compatibility.id,
                        partner_id=None,
                        other_user_id=compatibility.other_user_id,
                        partner_name=None,
                        partner_gender=None,
                        other_user_name=other_user.name,
                        other_user_gender=other_user.gender,
                        created_at=compatibility.created_at,
                        updated_at=compatibility.updated_at,
                        analysis=analysis
                    )
                    reports.append(report)
        
        except (json.JSONDecodeError, ValueError) as e:
            # Skip corrupted compatibility data
            logger.warning(f"Corrupted compatibility data for user {current_user.id}, compatibility {compatibility.id}: {e}")
            continue
        except Exception as e:
            # Log error but continue with other reports
            logger.error(f"Error processing compatibility report for user {current_user.id}, compatibility {compatibility.id}: {e}")
            continue
    
    # Apply pagination
    return reports[skip:skip + limit]

@router.get("/me/partners", response_model=List[schemas.Partner])
async def get_user_partners(
    skip: int = Query(0, description="Number of partners to skip", ge=0),
    limit: int = Query(20, description="Maximum number of partners to return", ge=1, le=100),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all partners for the current user.
    
    Args:
        skip: Number of partners to skip for pagination
        limit: Maximum number of partners to return
        current_user: The authenticated user
        db: Database session
        
    Returns:
        List of partners with enriched moon sign information
    """
    
    # Get partners for current user
    partners = crud.get_partners_by_user(db, current_user.id, skip=skip, limit=limit)
    
    # Enrich with moon sign information
    enriched_partners = []
    for partner in partners:
        partner_dict = {
            "id": partner.id,
            "user_id": partner.user_id,
            "name": partner.name,
            "gender": partner.gender,
            "city_of_birth": partner.city_of_birth,
            "time_of_birth": partner.time_of_birth,
            "created_at": partner.created_at,
            "updated_at": partner.updated_at,
        }
        
        # Calculate moon sign
        try:
            lat, lon = get_lat_long(partner.city_of_birth)
            tz = get_timezone(lat, lon)
            birth_date = partner.time_of_birth.strftime('%Y-%m-%d')
            birth_time = partner.time_of_birth.strftime('%H:%M')
            panchanga = get_panchanga(birth_date, birth_time, tz, lon, lat)
            moon_rashi = panchanga.get('moon_rashi')
            moon_sign = get_moon_sign_name(moon_rashi)
            partner_dict["moon_sign"] = moon_sign
        except Exception:
            partner_dict["moon_sign"] = None
            
        enriched_partners.append(partner_dict)
    
    return enriched_partners 

@router.get("/me/daily-facts", response_model=DailyFacts)
async def get_user_daily_facts(
    day: str = Query("today", description="Which day to get facts for: yesterday, today, tomorrow, or all", regex="^(yesterday|today|tomorrow|all)$"),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get daily astrological facts for the current user.
    Cached until next IST day for performance.
    """
    user = crud.get_user(db, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.time_of_birth or not user.city_of_birth:
        raise HTTPException(status_code=400, detail="User birth time and city are required for daily facts")
    
    try:
        if day == "all":
            # Get facts for yesterday, today, and tomorrow
            # Get location data for the user
            lat, lon = get_lat_long(user.city_of_birth)
            tz = get_timezone(lat, lon)
            ist = pytz.timezone('Asia/Kolkata')
            
            # Create location object with latitude and longitude
            class LocationData:
                def __init__(self, latitude, longitude):
                    self.latitude = latitude
                    self.longitude = longitude
            
            location = LocationData(lat, lon)
            
            facts = await llm_client.get_multi_day_facts(user_data=user.__dict__, location=location, ist=ist)
            return facts
        else:
            # Get facts for specific day
            ist = pytz.timezone('Asia/Kolkata')
            if day == "yesterday":
                target_date = datetime.now(ist) - timedelta(days=1)
            elif day == "tomorrow":
                target_date = datetime.now(ist) + timedelta(days=1)
            else:  # today
                target_date = datetime.now(ist)
            
            # Check cache first
            cached_facts = get_daily_facts_from_cache(user.id, target_date.strftime('%Y-%m-%d'))
            if cached_facts:
                # Convert cached dict back to Pydantic object
                return DailyFacts(**cached_facts)
            
            # Get location data for calculations
            lat, lon = get_lat_long(user.city_of_birth)
            tz = get_timezone(lat, lon)
            
            # Create location object with latitude and longitude
            class LocationData:
                def __init__(self, latitude, longitude):
                    self.latitude = latitude
                    self.longitude = longitude
            
            location = LocationData(lat, lon)
            
            # Generate facts with lucky number and timing calculations
            facts = await llm_client.get_daily_facts_for_date(user_data=user.__dict__, target_date=target_date, location=location, ist=ist)
            
            # Cache the results
            set_daily_facts_in_cache(user.id, target_date.strftime('%Y-%m-%d'), facts)
            
            return facts
            
    except Exception as e:
        logger.error(f"Error getting daily facts: {e}")
        raise HTTPException(status_code=500, detail="Error generating daily facts")

@router.post("/me/charts", response_model=dict)
async def get_user_charts(
    chart_names: List[str] = Query(..., description="List of chart names to generate (e.g., ['D1','D9'])"),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get divisional charts for the current user.
    Supported charts: D1, D2, D3, D4, D5, D6, D7, D8, D9, D10, D11, D12, D16, D20, D24, D27, D30, D40, D45, D60
    """
    user = crud.get_user(db, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.time_of_birth or not user.city_of_birth:
        raise HTTPException(status_code=400, detail="User birth time and city are required for charts")
    
    try:
        # Validate chart names
        valid_charts = ['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10', 'D11', 'D12', 'D16', 'D20', 'D24', 'D27', 'D30', 'D40', 'D45', 'D60']
        invalid_charts = [name for name in chart_names if name not in valid_charts]
        if invalid_charts:
            raise HTTPException(status_code=400, detail=f"Invalid chart names: {invalid_charts}. Valid charts: {valid_charts}")
        
        # Get location data
        lat, lon = get_lat_long(user.city_of_birth)
        tz = get_timezone(lat, lon)
        
        # Generate charts
        charts = {}
        for chart_name in chart_names:
            try:
                # This would call the actual chart generation logic
                # For now, returning placeholder
                charts[chart_name] = {
                    "chart_type": chart_name,
                    "user_id": user.id,
                    "generated_at": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Error generating {chart_name} chart: {e}")
                charts[chart_name] = {"error": f"Failed to generate {chart_name} chart"}
        
        return charts
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating charts: {e}")
        raise HTTPException(status_code=500, detail="Error generating charts")

@router.get("/me/life-events", response_model=LifeEvents)
async def get_user_life_events(
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get significant life events for the current user.
    Cached for 24 hours for performance.
    """
    user = crud.get_user(db, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.time_of_birth or not user.city_of_birth:
        raise HTTPException(status_code=400, detail="User birth time and city are required for life events")
    
    try:
        # Check if user already has life events
        if user.life_events_json:
            try:
                # Parse existing life events
                existing_events = json.loads(user.life_events_json)
                return LifeEvents(**existing_events)
            except (json.JSONDecodeError, ValueError):
                # Invalid JSON, regenerate
                pass
        
        # Generate new life events
        life_events = await llm_client.generate_life_events(user_data=user.__dict__)
        
        # Save to user
        crud.save_user_life_events(db, user.id, life_events.dict())
        
        return life_events
        
    except Exception as e:
        logger.error(f"Error getting life events: {e}")
        raise HTTPException(status_code=500, detail="Error generating life events")

@router.get("/me/weekly-horoscope", response_model=WeeklyHoroscope)
async def get_user_weekly_horoscope(
    week_start_date: str = Query(..., description="Start date of the week (YYYY-MM-DD)"),
    week_end_date: str = Query(..., description="End date of the week (YYYY-MM-DD)"),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get weekly horoscope predictions for the current user.
    Cached for the week duration for performance.
    """
    user = crud.get_user(db, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.time_of_birth or not user.city_of_birth:
        raise HTTPException(status_code=400, detail="User birth time and city are required for weekly horoscope")
    
    try:
        # Validate dates
        try:
            start_date = datetime.strptime(week_start_date, '%Y-%m-%d')
            end_date = datetime.strptime(week_end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        if start_date >= end_date:
            raise HTTPException(status_code=400, detail="Start date must be before end date")
        
        # Check cache first
        cached_horoscope = get_weekly_horoscope_from_cache(user.id, week_start_date)
        if cached_horoscope:
            # Convert cached dict back to Pydantic object
            return WeeklyHoroscope(**cached_horoscope)
        
        # Get comprehensive weekly data
        weekly_data = get_comprehensive_weekly_data(
            user, start_date, end_date, 
            get_lat_long, get_timezone
        )
        
        # Generate horoscope
        horoscope = await llm_client.get_weekly_horoscope(
            user_data=user.__dict__,
            week_start_date=week_start_date,
            week_end_date=week_end_date,
            dasha_data=weekly_data.get('dasha_data'),
            transit_data=weekly_data.get('transit_data'),
            moon_movements=weekly_data.get('moon_movements')
        )
        
        # Cache the results
        set_weekly_horoscope_in_cache(user.id, week_start_date, horoscope)
        
        return horoscope
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting weekly horoscope: {e}")
        raise HTTPException(status_code=500, detail="Error generating weekly horoscope")

@router.get("/me/threads", response_model=List[schemas.ChatThread])
async def get_user_threads(
    skip: int = Query(0, description="Number of threads to skip", ge=0),
    limit: int = Query(20, description="Maximum number of threads to return", ge=1, le=100),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List threads for the current user, newest first, with pagination."""
    threads = crud.get_user_threads(db, current_user.id, skip, limit)
    # Enrich with participant names
    return [_enrich_thread_with_participant_names(db, t) for t in threads]

@router.post("/me/threads", response_model=schemas.ChatThread)
async def create_chat_thread(
    thread: schemas.ChatThreadCreate,
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new thread; optional participants are validated and saved."""

    participant_uids: List[str] = []
    if thread.participant_user_ids is not None:
        participant_uids = _validate_participant_users(db, current_user, thread.participant_user_ids)

    participant_pids: List[str] = []
    if thread.participant_partner_ids is not None:
        participant_pids = _validate_participant_partners(db, current_user.id, thread.participant_partner_ids)

    # Validate compatibility_type if participants are specified
    compatibility_data = None
    if (len(participant_uids) > 0 or len(participant_pids) > 0) and thread.compatibility_type:
        if len(participant_uids) + len(participant_pids) != 1:
            raise HTTPException(
                status_code=400, 
                detail="compatibility_type is only allowed when exactly one participant is specified"
            )
        
        # Get compatibility data for context
        if len(participant_uids) == 1:
            other_user = crud.get_user(db, participant_uids[0])
            if not other_user:
                raise HTTPException(status_code=404, detail="Participant user not found")
            
            # Verify friendship
            if not crud.FriendsCRUD._are_friends(db, current_user.id, participant_uids[0]):
                raise HTTPException(status_code=403, detail="Can only create compatibility threads with friends")
            
            # Get compatibility data
            compatibility_data = compute_ashtakoota_raw_json_for_context(
                db, current_user.id, [participant_uids[0]], [], thread.compatibility_type
            )
        else:  # participant_partner_ids == 1
            partner = crud.get_partner(db, participant_pids[0])
            if not partner:
                raise HTTPException(status_code=404, detail="Participant partner not found")
            
            # Get compatibility data
            compatibility_data = compute_ashtakoota_raw_json_for_context(
                db, current_user.id, [], [participant_pids[0]], thread.compatibility_type
            )

    # Create thread
    created_thread = crud.create_chat_thread(
        db=db,
        user_id=current_user.id,
        title=thread.title,
        participant_user_ids=participant_uids,
        participant_partner_ids=participant_pids,
        compatibility_type=thread.compatibility_type,
        ashtakoota_raw_json=compatibility_data
    )
    return _enrich_thread_with_participant_names(db, created_thread)

@router.get("/me/threads/{thread_id}", response_model=schemas.ChatThread)
async def get_chat_thread(
    thread_id: UUID = Path(..., description="The ID of the thread to retrieve"),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific chat thread by ID."""
    thread = crud.get_chat_thread(db, str(thread_id), current_user.id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # Verify thread ownership
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this thread")
    
    return _enrich_thread_with_participant_names(db, thread)

@router.patch("/me/threads/{thread_id}", response_model=schemas.ChatThread)
async def update_chat_thread(
    thread_update: schemas.ChatThreadUpdate,
    thread_id: UUID = Path(..., description="The ID of the thread to update"),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a chat thread (title, participants, compatibility_type)."""
    thread = crud.get_chat_thread(db, str(thread_id), current_user.id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # Verify thread ownership
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this thread")
    
    # Validate participants if being updated
    if thread_update.participant_user_ids is not None:
        thread_update.participant_user_ids = _validate_participant_users(
            db, current_user, thread_update.participant_user_ids
        )
    
    if thread_update.participant_partner_ids is not None:
        thread_update.participant_partner_ids = _validate_participant_partners(
            db, current_user.id, thread_update.participant_partner_ids
        )
    
    # Validate compatibility_type if participants are specified
    if (thread_update.participant_user_ids is not None or thread_update.participant_partner_ids is not None) and thread_update.compatibility_type:
        total_participants = len(thread_update.participant_user_ids or []) + len(thread_update.participant_partner_ids or [])
        if total_participants != 1:
            raise HTTPException(
                status_code=400, 
                detail="compatibility_type is only allowed when exactly one participant is specified"
            )
    
    # Update thread
    update_data = thread_update.dict(exclude_unset=True)
    updated_thread = crud.update_chat_thread(db, str(thread_id), current_user.id, **update_data)
    return _enrich_thread_with_participant_names(db, updated_thread)

@router.delete("/me/threads/{thread_id}")
async def delete_chat_thread(
    thread_id: UUID = Path(..., description="The ID of the thread to delete"),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a chat thread and all its messages."""
    thread = crud.get_chat_thread(db, str(thread_id), current_user.id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # Verify thread ownership
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this thread")
    
    crud.delete_chat_thread(db, str(thread_id), current_user.id)
    return {"message": "Thread deleted successfully"}

@router.get("/me/threads/{thread_id}/message-count")
async def get_thread_message_count(
    thread_id: UUID = Path(..., description="The ID of the thread to count messages for"),
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the message count for a specific thread."""
    thread = crud.get_chat_thread(db, str(thread_id), current_user.id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # Verify thread ownership
    if thread.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this thread")
    
    count = crud.get_thread_message_count(db, str(thread_id), current_user.id)
    return {"thread_id": str(thread_id), "message_count": count}

@router.post("/me/trust-behavior-analysis")
async def get_trust_behavior_analysis(
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get or generate trust behavior analysis for the current user"""
    
    # Check if user already has analysis
    user = crud.get_user(db, current_user.id)
    if user.trust_analysis:
        return {"analysis": user.trust_analysis}
    
    # Check if user has birth data
    if not user.time_of_birth or not user.city_of_birth:
        raise HTTPException(
            status_code=400, 
            detail="Birth data (time and city) is required to generate trust analysis"
        )
    
    # Prepare birth data for LLM
    birth_data = {
        "date": user.time_of_birth.strftime("%Y-%m-%d") if user.time_of_birth else "N/A",
        "time": user.time_of_birth.strftime("%H:%M") if user.time_of_birth else "N/A",
        "place": user.city_of_birth or "N/A"
    }
    
    # Generate analysis using LLM
    trust_analysis = await llm_client.generate_trust_analysis(birth_data)
    
    # Save to database
    update_user_trust_analysis(db, current_user.id, trust_analysis)
    
    return {"analysis": trust_analysis} 