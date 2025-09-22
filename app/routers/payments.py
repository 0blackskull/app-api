from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import json
import base64
from typing import Dict, Any, Optional
from app.utils.logger import get_logger
from datetime import datetime

from app.database import get_db
from app.crud import user as user_crud
from app.crud.google_play_payment import (
    get_purchase_by_token, create_google_play_payment,
    create_purchase_event, get_purchase_event_by_message_id,
    get_pending_events_by_token, update_event_status
)
from app.config import PRODUCT_TO_CREDITS, GOOGLE_PLAY_PACKAGE_NAME
from app.llm.client import google_play_client
from app.schemas.payment import (
    GooglePlayPaymentCreate, VerifyPayload, VerifyResponse
)
from app.auth import get_current_user
from app import schemas
from app.crud.subscription import get_active_subscription, update_subscription_status

logger = get_logger(__name__)

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    responses={404: {"description": "Not found"}}
)

@router.post("/google-play")
async def handle_google_play_notification(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Google Play Real-time Developer Notifications (RTDN).
    
    This endpoint:
    1. Validates the incoming Pub/Sub message
    2. Stores the RTDN event
    3. Processes immediately if user is resolvable
    4. Returns success immediately (required for Pub/Sub)
    """
    try:
        # Parse the Pub/Sub message
        body = await request.body()
        pubsub_message = json.loads(body)
        
        logger.info(f"Received Google Play notification: {pubsub_message}")
        
        # Validate Pub/Sub message structure
        if not _is_valid_pubsub_message(pubsub_message):
            logger.error("Invalid Pub/Sub message format")
            raise HTTPException(status_code=400, detail="Invalid message format")
        
        # Decode the notification data
        notification = _decode_notification(pubsub_message)
        if not notification:
            logger.error("Failed to decode notification")
            raise HTTPException(status_code=400, detail="Invalid notification data")
        
        # Extract message ID for deduplication
        message_id = pubsub_message.get("message", {}).get("messageId")
        if not message_id:
            logger.error("Missing message ID in Pub/Sub message")
            raise HTTPException(status_code=400, detail="Missing message ID")
        
        # Check if we've already processed this message
        existing_event = get_purchase_event_by_message_id(db, message_id)
        if existing_event:
            logger.info(f"Message {message_id} already processed, skipping")
            return {"status": "already_processed"}
        
        # Extract purchase token and event type
        purchase_token = _extract_purchase_token(notification)
        event_type = _extract_event_type(notification)
        
        if not purchase_token:
            logger.error("Could not extract purchase token from notification")
            raise HTTPException(status_code=400, detail="Invalid notification: missing purchase token")
        
        # Store the RTDN event
        event_data = {
            "message_id": message_id,
            "purchase_token": purchase_token,
            "product_id": _extract_product_id(notification),
            "event_type": event_type,
            "status": "pending",
            "raw_payload": notification
        }
        
        purchase_event = create_purchase_event(db, event_data)
        logger.info(f"Stored RTDN event {message_id} for token {purchase_token}")
        
        # Try to resolve user and process immediately if possible
        user_id = _get_user_id_from_notification(notification)
        
        # If user_id missing and this is a subscription notification, try fetching from Play
        if not user_id and "subscriptionNotification" in notification:
            try:
                sub_token = notification["subscriptionNotification"].get("purchaseToken")
                if sub_token:
                    sub_info = google_play_client.get_subscription_info(
                        GOOGLE_PLAY_PACKAGE_NAME, sub_token
                    )
                    ext_ids = (sub_info or {}).get("externalAccountIdentifiers", {})
                    fetched_user_id = ext_ids.get("obfuscatedExternalAccountId")
                    if fetched_user_id:
                        user_id = fetched_user_id
                        logger.info(f"Resolved user_id from Play for RTDN: {user_id}")
            except Exception as e:
                logger.warning(f"Failed to resolve user_id from Play for RTDN: {e}")
        
        if user_id:
            # Update event with user_id and process
            update_event_status(db, purchase_event.id, "processing", user_id)
            await _process_event_sync(db, purchase_event, notification)
            logger.info(f"Processed RTDN event {message_id} immediately for user {user_id}")
        else:
            logger.info(f"RTDN event {message_id} stored as pending, waiting for verify call")
        
        return {"status": "success"}
        
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in request body")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception:
        logger.exception(f"Error handling Google Play notification")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/google-play/verify", response_model=VerifyResponse)
async def verify_google_play_purchase(
    payload: VerifyPayload,
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify a Google Play purchase and process any pending RTDN events.
    
    This endpoint:
    1. Validates the purchase with Google Play Developer API
    2. Creates/updates purchase mapping
    3. Processes any pending RTDN events for this token
    4. Grants entitlements based on current state
    """
    try:
        # Validate with Google Play Developer API
        purchase_info = await _validate_with_play_api(payload.purchase_token, payload.product_id)
        if not purchase_info:
            raise HTTPException(status_code=400, detail="Invalid purchase token or product")
        
        # Derive fields from Google Play response
        order_id = purchase_info.get("orderId") or f"token:{payload.purchase_token}"
        purchase_state_num = purchase_info.get("purchaseState", 0)
        ack_state_num = purchase_info.get("acknowledgementState", 0)
        consumption_state_num = purchase_info.get("consumptionState", 0)
        purchase_state_map = {0: "purchased", 1: "cancelled", 2: "pending"}
        purchase_state = purchase_state_map.get(purchase_state_num, "pending")
        acknowledgment_state = "acknowledged" if ack_state_num == 1 else "not_acknowledged"
        amount = 0
        currency = "INR"
        
        # Upsert purchase mapping
        existing = get_purchase_by_token(db, payload.purchase_token)
        if existing:
            existing.user_id = current_user.id
            existing.product_id = payload.product_id
            existing.amount = amount
            existing.currency = currency
            existing.purchase_state = purchase_state
            existing.acknowledgment_state = acknowledgment_state
            existing.is_acknowledged = (ack_state_num == 1)
            # Persist consumption state if provided by Play
            if consumption_state_num in (0, 1):
                existing.consumption_state = str(consumption_state_num)
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            logger.info(f"Updated existing purchase mapping for token {payload.purchase_token}")
        else:
            # Create new mapping record
            payment_data = GooglePlayPaymentCreate(
                product_id=payload.product_id,
                purchase_token=payload.purchase_token,
                order_id=order_id,
                user_id=current_user.id,
                amount=amount,
                currency=currency,
                purchase_state=purchase_state,
                acknowledgment_state=acknowledgment_state
            )
            created = create_google_play_payment(db, current_user.id, payment_data)
            # Update ack/consumption flags from Play
            created.is_acknowledged = (ack_state_num == 1)
            if consumption_state_num in (0, 1):
                created.consumption_state = str(consumption_state_num)
            created.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(created)
            logger.info(f"Created new purchase mapping for token {payload.purchase_token}")
        
        # Process any pending RTDN events for this token
        pending_events = get_pending_events_by_token(db, payload.purchase_token)
        credits_added = 0
        subscription_activated = False
        
        for event in pending_events:
            # Update event with user_id
            update_event_status(db, event.id, "processing", current_user.id)
            
            # Process the event
            result = await _process_event_sync(db, event, event.raw_payload)
            if result:
                if result.get("credits_added"):
                    credits_added += result["credits_added"]
                if result.get("subscription_activated"):
                    subscription_activated = True
            
            # Mark event as processed
            update_event_status(db, event.id, "processed")
        
        # If no pending events, process current purchase
        if not pending_events:
            result = await _process_current_purchase(
                db=db,
                user_id=current_user.id,
                product_id=payload.product_id,
                purchase_info=purchase_info,
                purchase_token=payload.purchase_token,
            )
            if result:
                if result.get("credits_added"):
                    credits_added += result["credits_added"]
                if result.get("subscription_activated"):
                    subscription_activated = True
        
        # Acknowledge the purchase with Play only if needed (device may have already acknowledged)
        if payload.product_id in PRODUCT_TO_CREDITS:
            if ack_state_num == 0:
                await _acknowledge_purchase(payload.purchase_token, payload.product_id)
        else:
            # Subscription - optionally guard by checking subscription ack state if available
            await _acknowledge_purchase(payload.purchase_token, payload.product_id)
        
        return VerifyResponse(
            status="verified",
            credits_added=credits_added if credits_added > 0 else None,
            subscription_activated=subscription_activated,
            message=f"Purchase verified successfully. Credits added: {credits_added}, Subscription activated: {subscription_activated}"
        )
        
    except Exception as e:
        logger.exception(f"Error verifying purchase")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

# Cancel Google Play subscription (stop auto-renew)
@router.post("/google-play/cancel")
async def cancel_google_play_subscription(
    current_user: schemas.CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel the user's active Google Play subscription (turn off auto-renew).
    Access remains until the current period end.
    """
    try:
        # Find active subscription for the user
        sub = get_active_subscription(db, current_user.id)
        if not sub:
            raise HTTPException(status_code=404, detail="No active subscription found")

        subscription_id = sub.product_id  # sku
        purchase_token = sub.purchase_token

        if not subscription_id or not purchase_token:
            raise HTTPException(status_code=400, detail="Subscription data incomplete")

        # Call Google Play API to cancel
        ok = google_play_client.cancel_subscription(
            GOOGLE_PLAY_PACKAGE_NAME, subscription_id, purchase_token
        )
        if not ok:
            raise HTTPException(status_code=502, detail="Failed to cancel subscription on Google Play")

        # Update local subscription status to cancelled; keep end_time
        updated = update_subscription_status(db, sub.id, status="cancelled") or sub

        # Determine access until end_time if available
        end_dt = None
        try:
            if updated and getattr(updated, "end_time", None):
                end_ms = int(updated.end_time)
                end_dt = datetime.utcfromtimestamp(end_ms / 1000.0)
        except Exception:
            end_dt = None

        has_access = False
        if end_dt:
            has_access = end_dt > datetime.utcnow()

        # Update user flags: status cancelled; preserve unlimited access until expiry if applicable
        user_crud.update_user_subscription(
            db=db,
            user_id=current_user.id,
            subscription_type="free" if not has_access else "free",
            subscription_status="cancelled",
            subscription_end_date=end_dt,
            has_unlimited_chat=has_access
        )

        return {"status": "cancelled", "access_until": end_dt.isoformat() if end_dt else None}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error cancelling Google Play subscription")
        raise HTTPException(status_code=500, detail="Internal server error")

# Helper functions
def _is_valid_pubsub_message(message: Dict[str, Any]) -> bool:
    """Validate Pub/Sub message structure."""
    return (
        isinstance(message, dict) and
        "message" in message and
        isinstance(message["message"], dict) and
        "data" in message["message"]
    )

def _decode_notification(pubsub_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Decode the base64-encoded notification data from Pub/Sub message."""
    try:
        encoded_data = pubsub_message["message"]["data"]
        decoded_data = base64.b64decode(encoded_data).decode('utf-8')
        notification = json.loads(decoded_data)
        logger.info(f"Decoded notification: {notification}")
        return notification
    except Exception as e:
        logger.error(f"Error decoding notification: {e}")
        return None

def _extract_purchase_token(notification: Dict[str, Any]) -> Optional[str]:
    """Extract purchase token from RTDN notification."""
    # Try subscription notification
    if "subscriptionNotification" in notification:
        return notification["subscriptionNotification"].get("purchaseToken")
    
    # Try one-time product notification
    if "oneTimeProductNotification" in notification:
        return notification["oneTimeProductNotification"].get("purchaseToken")
    
    # Try voided purchase notification (refunds/cancellations)
    if "voidedPurchaseNotification" in notification:
        return notification["voidedPurchaseNotification"].get("purchaseToken")
    
    # Try other notification types that might contain purchase tokens
    for key, value in notification.items():
        if isinstance(value, dict) and "purchaseToken" in value:
            return value.get("purchaseToken")
    
    return None

def _extract_event_type(notification: Dict[str, Any]) -> str:
    """Extract event type from RTDN notification."""
    if "subscriptionNotification" in notification:
        return f"subscription_{notification['subscriptionNotification'].get('notificationType', 'unknown')}"
    elif "oneTimeProductNotification" in notification:
        return f"product_{notification['oneTimeProductNotification'].get('notificationType', 'unknown')}"
    elif "voidedPurchaseNotification" in notification:
        return f"voided_{notification['voidedPurchaseNotification'].get('productType', 'unknown')}"
    
    # Try to detect other notification types
    for key, value in notification.items():
        if isinstance(value, dict) and "notificationType" in value:
            return f"{key}_{value.get('notificationType', 'unknown')}"
    
    return "unknown"

def _extract_product_id(notification: Dict[str, Any]) -> Optional[str]:
    """Extract product ID from RTDN notification."""
    if "oneTimeProductNotification" in notification:
        return notification["oneTimeProductNotification"].get("sku")
    # Also handle subscription notifications
    if "subscriptionNotification" in notification:
        return notification["subscriptionNotification"].get("subscriptionId")
    # Handle voided purchase notifications
    if "voidedPurchaseNotification" in notification:
        return notification["voidedPurchaseNotification"].get("sku")
    return None

def _get_user_id_from_notification(notification: Dict[str, Any]) -> Optional[str]:
    """Extract user ID from RTDN notification if available."""
    # Check for obfuscatedExternalAccountId in various locations
    if "subscriptionNotification" in notification:
        sub_notification = notification["subscriptionNotification"]
        if "obfuscatedExternalAccountId" in sub_notification:
            return sub_notification["obfuscatedExternalAccountId"]
    
    if "oneTimeProductNotification" in notification:
        product_notification = notification["oneTimeProductNotification"]
        if "obfuscatedExternalAccountId" in product_notification:
            return product_notification["obfuscatedExternalAccountId"]
    
    if "voidedPurchaseNotification" in notification:
        voided_notification = notification["voidedPurchaseNotification"]
        if "obfuscatedExternalAccountId" in voided_notification:
            return voided_notification["obfuscatedExternalAccountId"]
    
    if "obfuscatedExternalAccountId" in notification:
        return notification["obfuscatedExternalAccountId"]
    
    return None

async def _validate_with_play_api(purchase_token: str, product_id: str) -> Optional[Dict[str, Any]]:
    """Validate purchase with Google Play Developer API."""
    try:
        logger.error(f"Validating purchase with Google Play API for token {purchase_token} and product {product_id}")
        # Try to get product info first
        product_info = google_play_client.get_product_info(
            GOOGLE_PLAY_PACKAGE_NAME, product_id, purchase_token
        )
        if product_info:
            logger.error(f"Product info: {product_info}")
            return product_info
        # If not a product, try subscription
        subscription_info = google_play_client.get_subscription_info(
            GOOGLE_PLAY_PACKAGE_NAME, purchase_token
        )
        if subscription_info:
            logger.error(f"Subscription info: {subscription_info}")
            return subscription_info
        
        logger.error(f"Could not validate purchase token {purchase_token} with Google Play API")
        return None
        
    except Exception as e:
        logger.error(f"Error validating with Google Play API: {e}")
        return None

async def _process_event_sync(db: Session, event: Any, notification: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process RTDN event synchronously."""
    try:
        event_type = event.event_type
        
        if event_type.startswith("product_"):
            return await _handle_product_event(db, event, notification)
        elif event_type.startswith("subscription_"):
            return await _handle_subscription_event(db, event, notification)
        elif event_type.startswith("voided_"):
            return await _handle_voided_purchase_event(db, event, notification)
        else:
            logger.warning(f"Unknown event type: {event_type}")
            return None
            
    except Exception as e:
        logger.error(f"Error processing event {event.id}: {e}")
        return None

async def _handle_product_event(db: Session, event: Any, notification: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle one-time product events."""
    try:
        if not event.user_id:
            logger.warning(f"Product event {event.id} has no user_id, skipping")
            return None
        
        product_id = event.product_id
        if not product_id:
            logger.warning(f"Product event {event.id} has no product_id, skipping")
            return None
        
        # Idempotency: if we already processed this token, skip granting again
        payment = get_purchase_by_token(db, event.purchase_token)
        if payment and payment.status == "completed":
            logger.info(f"Payment already processed for token {event.purchase_token}, skipping credit grant")
            return None
        
        # Get current state from Google Play API
        purchase_info = google_play_client.get_product_info(
            GOOGLE_PLAY_PACKAGE_NAME, product_id, event.purchase_token
        )
        
        if not purchase_info:
            logger.warning(f"Could not get product info for event {event.id}")
            return None
        
        purchase_state = purchase_info.get("purchaseState", 0)
        acknowledgment_state = purchase_info.get("acknowledgementState", 0)
        
        if purchase_state == 0 and acknowledgment_state == 0:  # Purchased, not acknowledged
            # Add credits if it's a credit product
            if product_id in PRODUCT_TO_CREDITS:
                credits = PRODUCT_TO_CREDITS[product_id]
                user_crud.add_credits(db, event.user_id, credits)
                logger.info(f"Added {credits} credits to user {event.user_id}")
                
                # Mark completed locally to prevent double credit on retries
                if payment:
                    payment.status = "completed"
                    payment.acknowledgment_state = "acknowledged"
                    payment.is_acknowledged = True
                    payment.updated_at = datetime.utcnow()
                    db.commit()
                    db.refresh(payment)
                
                # Acknowledge the purchase on Play
                google_play_client.acknowledge_product(
                    GOOGLE_PLAY_PACKAGE_NAME, product_id, event.purchase_token
                )
                
                return {"credits_added": credits}
        
        return None
        
    except Exception as e:
        logger.error(f"Error handling product event {event.id}: {e}")
        return None

async def _handle_subscription_event(db: Session, event: Any, notification: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle subscription events."""
    try:
        if not event.user_id:
            logger.warning(f"Subscription event {event.id} has no user_id, skipping")
            return None
        
        # Prefer direct handling via RTDN notificationType when available
        type_code = None
        if "subscriptionNotification" in notification:
            type_code = notification["subscriptionNotification"].get("notificationType")
        
        # Map key RTDN types to actions to avoid relying solely on API fetch
        if type_code in (2, 4):  # RENEWED or PURCHASED
            user_crud.update_user_subscription(
                db=db,
                user_id=event.user_id,
                subscription_type="monthly",  # Consider mapping from subscriptionId
                subscription_status="active",
                has_unlimited_chat=True
            )
            logger.info(f"Activated subscription for user {event.user_id} via RTDN type {type_code}")
            return {"subscription_activated": True}
        elif type_code in (3, 13):  # CANCELED or EXPIRED
            user_crud.update_user_subscription(
                db=db,
                user_id=event.user_id,
                subscription_type="free",
                subscription_status="inactive",
                has_unlimited_chat=False
            )
            logger.info(f"Deactivated subscription for user {event.user_id} via RTDN type {type_code}")
            return {"subscription_deactivated": True}
        
        # Fallback to querying current state when type not explicitly handled
        subscription_info = google_play_client.get_subscription_info(
            GOOGLE_PLAY_PACKAGE_NAME, event.purchase_token
        )
        
        if not subscription_info:
            logger.warning(f"Could not get subscription info for event {event.id}")
            return None
        
        subscription_state = subscription_info.get("subscriptionState", "UNKNOWN")
        
        if subscription_state == "SUBSCRIPTION_STATE_ACTIVE":
            user_crud.update_user_subscription(
                db=db,
                user_id=event.user_id,
                subscription_type="monthly",  # You might want to extract this from product_id
                subscription_status="active",
                has_unlimited_chat=True
            )
            logger.info(f"Activated subscription for user {event.user_id}")
            return {"subscription_activated": True}
        elif subscription_state in ["SUBSCRIPTION_STATE_CANCELED", "SUBSCRIPTION_STATE_EXPIRED"]:
            user_crud.update_user_subscription(
                db=db,
                user_id=event.user_id,
                subscription_type="free",
                subscription_status="inactive",
                has_unlimited_chat=False
            )
            logger.info(f"Deactivated subscription for user {event.user_id}")
            return {"subscription_deactivated": True}
        
        return None
        
    except Exception as e:
        logger.error(f"Error handling subscription event {event.id}: {e}")
        return None

async def _handle_voided_purchase_event(db: Session, event: Any, notification: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle voided purchase events (refunds/cancellations)."""
    try:
        if not event.user_id:
            logger.warning(f"Voided purchase event {event.id} has no user_id, skipping")
            return None
        
        # Get the purchase token from the event
        purchase_token = event.purchase_token
        if not purchase_token:
            logger.warning(f"Voided purchase event {event.id} has no purchase_token, skipping")
            return None
        
        # Get the product ID from the event
        product_id = event.product_id
        if not product_id:
            logger.warning(f"Voided purchase event {event.id} has no product_id, skipping")
            return None
        
        # Check if this is a subscription or one-time product
        if product_id in PRODUCT_TO_CREDITS:
            # One-time product - check if it was already processed
            payment = get_purchase_by_token(db, purchase_token)
            if payment and payment.status == "completed":
                # Revert the credits that were added
                credits_to_remove = PRODUCT_TO_CREDITS[product_id]
                user_crud.deduct_credits(db, event.user_id, credits_to_remove)
                logger.info(f"Removed {credits_to_remove} credits for user {event.user_id} due to voided purchase")
                
                # Update payment status
                payment.status = "refunded"
                payment.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(payment)
                
                return {"credits_removed": credits_to_remove}
        else:
            # Subscription - deactivate it
            user_crud.update_user_subscription(
                db=db,
                user_id=event.user_id,
                subscription_type="free",
                subscription_status="cancelled",
                has_unlimited_chat=False
            )
            logger.info(f"Deactivated subscription for user {event.user_id} due to voided purchase")
            
            return {"subscription_deactivated": True}
        
        return None
        
    except Exception as e:
        logger.error(f"Error handling voided purchase event {event.id}: {e}")
        return None

async def _process_current_purchase(db: Session, user_id: str, product_id: str, purchase_info: Dict[str, Any], purchase_token: str) -> Optional[Dict[str, Any]]:
    """Process current purchase if no pending events."""
    try:
        # Idempotency: if we already processed this token, skip granting again
        payment = get_purchase_by_token(db, purchase_token)
        if payment and payment.status == "completed":
            logger.info(f"Payment already processed for token {purchase_token}, skipping credit grant")
            return None
        
        # Handle based on product type
        if product_id in PRODUCT_TO_CREDITS:
            # One-time credit purchase
            credits = PRODUCT_TO_CREDITS[product_id]
            user_crud.add_credits(db, user_id, credits)
            logger.info(f"Added {credits} credits to user {user_id}")
            
            # Mark completed locally to prevent double credit on retries
            if payment:
                payment.status = "completed"
                payment.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(payment)
            
            return {"credits_added": credits}
        else:
            # Subscription purchase
            user_crud.update_user_subscription(
                db=db,
                user_id=user_id,
                subscription_type="monthly",  # Extract from product_id
                subscription_status="active",
                has_unlimited_chat=True
            )
            logger.info(f"Activated subscription for user {user_id}")
            return {"subscription_activated": True}
        
    except Exception as e:
        logger.error(f"Error processing current purchase: {e}")
        return None

async def _acknowledge_purchase(purchase_token: str, product_id: str):
    """Acknowledge purchase with Google Play."""
    try:
        if product_id in PRODUCT_TO_CREDITS:
            # One-time product
            google_play_client.acknowledge_product(
                GOOGLE_PLAY_PACKAGE_NAME, product_id, purchase_token
            )
        else:
            # Subscription - extract subscription ID from product_id
            subscription_id = product_id  # You might need to map this differently
            google_play_client.acknowledge_subscription(
                GOOGLE_PLAY_PACKAGE_NAME, subscription_id, purchase_token
            )
        
        logger.info(f"Acknowledged purchase for token {purchase_token}")
        
    except Exception as e:
        logger.error(f"Error acknowledging purchase: {e}") 