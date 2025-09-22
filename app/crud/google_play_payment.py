from sqlalchemy.orm import Session
from app.models.payment import GooglePlayPayment, PurchaseEvent
from app.schemas.payment import GooglePlayPaymentCreate
from app.crud import user as user_crud
from app.config import PRODUCT_TO_CREDITS
from typing import List, Optional
from app.utils.logger import get_logger
from datetime import datetime
from sqlalchemy import func

logger = get_logger(__name__)

def get_google_play_payment(db: Session, order_id: str) -> Optional[GooglePlayPayment]:
    """Get a Google Play payment by order ID."""
    return db.query(GooglePlayPayment).filter(GooglePlayPayment.id == order_id).first()

def get_google_play_payments_by_user(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[GooglePlayPayment]:
    """Get Google Play payments for a specific user."""
    return db.query(GooglePlayPayment).filter(
        GooglePlayPayment.user_id == user_id
    ).order_by(GooglePlayPayment.created_at.desc()).offset(skip).limit(limit).all()

def create_google_play_payment(
    db: Session, 
    user_id: str, 
    payment_data: GooglePlayPaymentCreate
) -> GooglePlayPayment:
    """Create a new Google Play payment record."""
    db_payment = GooglePlayPayment(
        id=payment_data.order_id,
        user_id=user_id,
        product_id=payment_data.product_id,
        purchase_token=payment_data.purchase_token,
        amount=payment_data.amount,
        currency=payment_data.currency,
        purchase_state=payment_data.purchase_state,
        acknowledgment_state=payment_data.acknowledgment_state,
        # Ensure NOT NULL columns are set
        purchase_type="inapp",
        consumption_state="0",
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

def update_google_play_payment_status(
    db: Session, 
    order_id: str, 
    status: str,
    acknowledgment_state: str = None,
    purchase_state: str = None
) -> Optional[GooglePlayPayment]:
    """Update Google Play payment status."""
    payment = get_google_play_payment(db, order_id)
    if not payment:
        return None
    
    payment.status = status
    if acknowledgment_state:
        payment.acknowledgment_state = acknowledgment_state
        payment.is_acknowledged = (acknowledgment_state == "acknowledged")
    if purchase_state:
        payment.purchase_state = purchase_state
    payment.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(payment)
    return payment

def acknowledge_google_play_payment(
    db: Session, 
    order_id: str, 
    purchase_token: str
) -> Optional[GooglePlayPayment]:
    """Acknowledge a Google Play payment and add credits to user."""
    payment = get_google_play_payment(db, order_id)
    if not payment or payment.purchase_token != purchase_token:
        return None
    
    # Update acknowledgment state
    payment.acknowledgment_state = "acknowledged"
    payment.is_acknowledged = True
    payment.updated_at = datetime.utcnow()
    
    # Add credits to user if this is a credit purchase
    if payment.product_id in PRODUCT_TO_CREDITS:
        credits_to_add = PRODUCT_TO_CREDITS[payment.product_id]
        user_crud.add_credits(db, payment.user_id, credits_to_add)
        logger.info(f"Added {credits_to_add} credits to user {payment.user_id} for purchase {order_id}")
    
    db.commit()
    db.refresh(payment)
    return payment

def get_pending_payments(db: Session, user_id: str) -> List[GooglePlayPayment]:
    """Get pending Google Play payments for a user."""
    return db.query(GooglePlayPayment).filter(
        GooglePlayPayment.user_id == user_id,
        GooglePlayPayment.status == "pending"
    ).all()

def get_purchase_by_token(db: Session, purchase_token: str) -> GooglePlayPayment:
    """Get Google Play payment by purchase token."""
    return db.query(GooglePlayPayment).filter(GooglePlayPayment.purchase_token == purchase_token).first()



def get_unacknowledged_payments(db: Session, user_id: str) -> List[GooglePlayPayment]:
    """Get unacknowledged Google Play payments for a user."""
    return db.query(GooglePlayPayment).filter(
        GooglePlayPayment.user_id == user_id,
        GooglePlayPayment.is_acknowledged == False
    ).all()

def get_recent_payments(db: Session, limit: int = 10) -> List[GooglePlayPayment]:
    """Get recent Google Play payments."""
    return db.query(GooglePlayPayment).order_by(
        GooglePlayPayment.created_at.desc()
    ).limit(limit).all() 

# PurchaseEvent CRUD operations
def create_purchase_event(db: Session, event_data: dict) -> PurchaseEvent:
    """Create a new purchase event record."""
    db_event = PurchaseEvent(**event_data)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

def get_purchase_event_by_message_id(db: Session, message_id: str) -> PurchaseEvent:
    """Get purchase event by Pub/Sub message ID."""
    return db.query(PurchaseEvent).filter(PurchaseEvent.message_id == message_id).first()

def get_pending_events_by_token(db: Session, purchase_token: str) -> list[PurchaseEvent]:
    """Get all pending events for a purchase token."""
    return db.query(PurchaseEvent).filter(
        PurchaseEvent.purchase_token == purchase_token,
        PurchaseEvent.status == "pending"
    ).order_by(PurchaseEvent.created_at).all()

def update_event_status(db: Session, event_id: str, status: str, user_id: str = None) -> PurchaseEvent:
    """Update the status of a purchase event"""
    event = db.query(PurchaseEvent).filter(PurchaseEvent.id == event_id).first()
    if event:
        event.status = status
        if user_id:
            event.user_id = user_id
        event.processed_at = func.now()
        db.commit()
        db.refresh(event)
    return event

def get_purchase_events_by_token(db: Session, purchase_token: str) -> list[PurchaseEvent]:
    """Get all events for a purchase token."""
    return db.query(PurchaseEvent).filter(
        PurchaseEvent.purchase_token == purchase_token
    ).order_by(PurchaseEvent.created_at).all() 