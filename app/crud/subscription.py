from sqlalchemy.orm import Session
from app.models.payment import Subscription
from app.schemas.payment import SubscriptionCreate
from app.crud import user as user_crud
from typing import List, Optional
from app.utils.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)

def get_subscription(db: Session, subscription_id: str) -> Optional[Subscription]:
    """Get a subscription by ID."""
    return db.query(Subscription).filter(Subscription.id == subscription_id).first()

def get_subscriptions_by_user(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[Subscription]:
    """Get subscriptions for a specific user."""
    return db.query(Subscription).filter(
        Subscription.user_id == user_id
    ).order_by(Subscription.created_at.desc()).offset(skip).limit(limit).all()

def get_active_subscription(db: Session, user_id: str) -> Optional[Subscription]:
    """Get the active subscription for a user."""
    return db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status.in_(["active", "grace_period"])
    ).first()

def create_subscription(
    db: Session, 
    user_id: str, 
    subscription_data: SubscriptionCreate
) -> Subscription:
    """Create a new subscription record."""
    db_subscription = Subscription(
        id=subscription_data.subscription_id,
        user_id=user_id,
        product_id=subscription_data.product_id,
        purchase_token=subscription_data.purchase_token,
        status=subscription_data.status,
        purchase_state=subscription_data.purchase_state,
        start_time=subscription_data.start_time,
        end_time=subscription_data.end_time
    )
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

def update_subscription_status(
    db: Session, 
    subscription_id: str, 
    status: str,
    acknowledgment_state: str = None,
    end_time: int = None
) -> Optional[Subscription]:
    """Update subscription status."""
    subscription = get_subscription(db, subscription_id)
    if not subscription:
        return None
    
    subscription.status = status
    if acknowledgment_state:
        subscription.acknowledgment_state = acknowledgment_state
        subscription.is_acknowledged = (acknowledgment_state == "acknowledged")
    if end_time:
        subscription.end_time = end_time
    subscription.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(subscription)
    return subscription

def acknowledge_subscription(
    db: Session, 
    subscription_id: str, 
    purchase_token: str
) -> Optional[Subscription]:
    """Acknowledge a subscription and update user subscription status."""
    subscription = get_subscription(db, subscription_id)
    if not subscription or subscription.purchase_token != purchase_token:
        return None
    
    # Update acknowledgment state
    subscription.acknowledgment_state = "acknowledged"
    subscription.is_acknowledged = True
    subscription.updated_at = datetime.utcnow()
    
    # Update user subscription status
    user_crud.update_user_subscription(
        db=db,
        user_id=subscription.user_id,
        subscription_type=subscription.product_id,
        subscription_status=subscription.status,
        subscription_end_date=datetime.fromtimestamp(subscription.end_time / 1000) if subscription.end_time else None,
        has_unlimited_chat=True
    )
    
    logger.info(f"Updated subscription status for user {subscription.user_id} to {subscription.status}")
    
    db.commit()
    db.refresh(subscription)
    return subscription

def cancel_subscription(db: Session, subscription_id: str) -> Optional[Subscription]:
    """Cancel a subscription."""
    subscription = get_subscription(db, subscription_id)
    if not subscription:
        return None
    
    subscription.status = "cancelled"
    subscription.updated_at = datetime.utcnow()
    
    # Update user subscription status
    user_crud.update_user_subscription(
        db=db,
        user_id=subscription.user_id,
        subscription_type="free",
        subscription_status="cancelled",
        subscription_end_date=datetime.fromtimestamp(subscription.end_time / 1000) if subscription.end_time else None,
        has_unlimited_chat=False
    )
    
    logger.info(f"Cancelled subscription {subscription_id} for user {subscription.user_id}")
    
    db.commit()
    db.refresh(subscription)
    return subscription

def expire_subscription(db: Session, subscription_id: str) -> Optional[Subscription]:
    """Mark a subscription as expired."""
    subscription = get_subscription(db, subscription_id)
    if not subscription:
        return None
    
    subscription.status = "expired"
    subscription.updated_at = datetime.utcnow()
    
    # Update user subscription status
    user_crud.update_user_subscription(
        db=db,
        user_id=subscription.user_id,
        subscription_type="free",
        subscription_status="expired",
        subscription_end_date=datetime.utcnow(),
        has_unlimited_chat=False
    )
    
    logger.info(f"Expired subscription {subscription_id} for user {subscription.user_id}")
    
    db.commit()
    db.refresh(subscription)
    return subscription

def get_subscription_by_token(db: Session, purchase_token: str) -> Optional[Subscription]:
    """Get a subscription by purchase token."""
    return db.query(Subscription).filter(
        Subscription.purchase_token == purchase_token
    ).first()

def get_expired_subscriptions(db: Session) -> List[Subscription]:
    """Get all expired subscriptions."""
    return db.query(Subscription).filter(
        Subscription.status == "expired"
    ).all()

def get_subscriptions_needing_renewal(db: Session) -> List[Subscription]:
    """Get subscriptions that need renewal (within 7 days of expiry)."""
    # Convert 7 days to milliseconds
    seven_days_ms = 7 * 24 * 60 * 60 * 1000
    current_time_ms = int(datetime.utcnow().timestamp() * 1000)
    renewal_threshold = current_time_ms + seven_days_ms
    
    return db.query(Subscription).filter(
        Subscription.status == "active",
        Subscription.end_time <= renewal_threshold
    ).all() 