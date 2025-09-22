from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from app.models import User
from datetime import datetime
import json
from typing import Optional, Dict, Any

def get_user(db: Session, user_id: str) -> User:
    """Get a user by ID."""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_id(db: Session, user_id: str) -> User:
    """Get a user by ID (alias for get_user)."""
    return get_user(db, user_id)

def get_user_by_email(db: Session, email: str) -> User:
    """Get a user by email."""
    return db.query(User).filter(User.email == email).first()

def get_user_by_username(db: Session, username: str) -> User:
    """Get a user by username (case-insensitive)."""
    return db.query(User).filter(func.lower(User.username) == func.lower(username)).first()

def get_users_by_username_pattern(db: Session, username_pattern: str, limit: int = 10) -> list[User]:
    """
    Search users by username pattern (for autocomplete/search functionality).
    
    Args:
        db: Database session
        username_pattern: Username pattern to search for (e.g., "john")
        limit: Maximum number of results to return
        
    Returns:
        List of users matching the pattern
    """
    # Filter out NULL usernames and use case-insensitive search
    return db.query(User).filter(
        User.username.isnot(None),
        func.lower(User.username).like(f"{username_pattern.lower()}%")
    ).limit(limit).all()

def is_username_available(db: Session, username: str, exclude_user_id: str = None) -> bool:
    """
    Check if a username is available (unique).
    
    This function is optimized for performance by:
    1. Using the indexed username column
    2. Using case-insensitive comparison
    3. Excluding the current user if updating
    
    Args:
        db: Database session
        username: Username to check
        exclude_user_id: User ID to exclude from the check (for updates)
        
    Returns:
        True if username is available, False otherwise
    """
    # Use case-insensitive comparison with LOWER() function for better performance
    query = db.query(User).filter(func.lower(User.username) == username.lower())
    
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)
    
    # Use first() for better performance - stops at first match
    return query.first() is None



def create_user(db: Session, user_id: str, email: str, display_name: str, state: str = "inactive") -> User:
    """
    Create a new user.
    
    Args:
        db: Database session
        user_id: User ID
        email: User email
        display_name: User display name
        state: User activation state
        
    Returns:
        Created User object
    """
    db_user = User(
        id=user_id,
        email=email,
        display_name=display_name,
        state=state
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_fields(db: Session, user: User, update_data: dict) -> User:
    """
    Update user fields with the provided data.
    
    Handles special validation for username field to ensure uniqueness.
    """
    # Handle username update with validation
    username = None
    if 'username' in update_data:
        username = update_data.pop('username')
        if username is not None:
            # Check if username is available
            if not is_username_available(db, username, exclude_user_id=user.id):
                raise ValueError(f"Username '{username}' is already taken")
    
    # Update all other fields
    for field, value in update_data.items():
        if hasattr(user, field):
            setattr(user, field, value)
    
    # Set username if it was provided
    if username is not None:
        user.username = username
    
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise ValueError(f"Username '{username}' is already taken")
    
    return user

def update_user(db: Session, user: User, update_data: dict) -> User:
    """Update a user with the provided data."""
    return update_user_fields(db, user, update_data)

def update_user_display_name(db: Session, user_id: str, display_name: str) -> User:
    """Update a user's display name."""
    db_user = get_user(db, user_id)
    if db_user:
        db_user.display_name = display_name
        db.commit()
        db.refresh(db_user)
    return db_user

# Add a function to set user state (activate)
def set_user_state(db: Session, user_id: str, state: str) -> User:
    db_user = get_user(db, user_id)
    if db_user:
        db_user.state = state
        db.commit()
        db.refresh(db_user)
    return db_user

def add_credits(db: Session, user_id: str, credits: int) -> User:
    """
    Add credits to a user's account.
    
    Args:
        db: Database session
        user_id: User ID
        credits: Number of credits to add
        
    Returns:
        Updated User object
    """
    db_user = get_user(db, user_id)
    if db_user:
        db_user.credits += credits
        db.commit()
        db.refresh(db_user)
    return db_user

def deduct_credits(db: Session, user_id: str, credits: int = 1) -> User:
    """
    Deduct credits from a user's account.
    
    Args:
        db: Database session
        user_id: User ID
        credits: Number of credits to deduct (default: 1)
        
    Returns:
        Updated User object
    """
    db_user = get_user(db, user_id)
    if db_user:
        db_user.credits = max(0, db_user.credits - credits)  # Ensure credits don't go negative
        db.commit()
        db.refresh(db_user)
    return db_user

def get_user_credits(db: Session, user_id: str) -> int:
    """
    Get the number of credits a user has.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Number of credits
    """
    db_user = get_user(db, user_id)
    if db_user:
        return db_user.credits
    return 0

def update_user_trust_analysis(db: Session, user_id: str, trust_analysis: str) -> User:
    """
    Update user's trust analysis.
    
    Args:
        db: Database session
        user_id: User ID
        trust_analysis: Trust analysis text to store
        
    Returns:
        Updated User object
    """
    db_user = get_user(db, user_id)
    if db_user:
        db_user.trust_analysis = trust_analysis
        db.commit()
        db.refresh(db_user)
    return db_user

def has_sufficient_credits(db: Session, user_id: str, required_credits: int = 1) -> bool:
    """
    Check if a user has sufficient credits.
    
    Args:
        db: Database session
        user_id: User ID
        required_credits: Number of credits required (default: 1)
        
    Returns:
        True if user has sufficient credits, False otherwise
    """
    db_user = get_user(db, user_id)
    if not db_user:
        return False
    
    # If user has unlimited chat, they don't need credits
    if db_user.has_unlimited_chat and db_user.subscription_status == "active":
        return True
    
    return db_user.credits >= required_credits

def update_user_subscription(
    db: Session, 
    user_id: str, 
    subscription_type: str, 
    subscription_status: str,
    subscription_end_date: datetime = None,
    has_unlimited_chat: bool = False
) -> User:
    """
    Update user's subscription information.
    
    Args:
        db: Database session
        user_id: User ID
        subscription_type: Type of subscription (free, unlimited_monthly, unlimited_yearly)
        subscription_status: Status of subscription (active, cancelled, expired, grace_period)
        subscription_end_date: When subscription expires
        has_unlimited_chat: Whether user has unlimited chat access
        
    Returns:
        Updated User object
    """
    db_user = get_user(db, user_id)
    if db_user:
        db_user.subscription_type = subscription_type
        db_user.subscription_status = subscription_status
        db_user.subscription_end_date = subscription_end_date
        db_user.has_unlimited_chat = has_unlimited_chat
        db_user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_user)
    return db_user

def get_user_subscription_info(db: Session, user_id: str) -> dict:
    """
    Get user's subscription information.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Dictionary with subscription information
    """
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    return {
        "subscription_type": db_user.subscription_type,
        "subscription_status": db_user.subscription_status,
        "subscription_end_date": db_user.subscription_end_date,
        "has_unlimited_chat": db_user.has_unlimited_chat,
        "credits": db_user.credits
    }

def can_user_chat(db: Session, user_id: str) -> bool:
    """
    Check if a user can chat (has credits or unlimited access).
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        True if user can chat, False otherwise
    """
    db_user = get_user(db, user_id)
    if not db_user:
        return False
    
    # Check if user has unlimited chat access
    if db_user.subscription_status == "active":
        return True
    
    # Check if user has credits (> 0 to allow users with exactly 0 credits)
    return db_user.credits > 0

def reset_user_to_free_plan(db: Session, user_id: str) -> User:
    """
    Reset user to free plan (remove subscription benefits).
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Updated User object
    """
    return update_user_subscription(
        db=db,
        user_id=user_id,
        subscription_type="free",
        subscription_status="inactive",
        subscription_end_date=datetime.utcnow(),
        has_unlimited_chat=False
    )

# User data functions (consolidated from previous profile.py)
def get_user_life_events(db: Session, user_id: str) -> Optional[Dict[str, Any]]:
    """Get life events JSON data for a user."""
    db_user = get_user(db, user_id)
    if db_user and db_user.life_events_json:
        try:
            return json.loads(db_user.life_events_json)
        except json.JSONDecodeError:
            return None
    return None

def save_user_life_events(db: Session, user_id: str, life_events_data: Dict[str, Any]) -> User:
    """Save life events JSON data for a user."""
    db_user = get_user(db, user_id)
    if db_user:
        db_user.life_events_json = json.dumps(life_events_data)
        db.commit()
        db.refresh(db_user)
    return db_user 