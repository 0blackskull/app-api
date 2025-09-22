from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime

# Google Play Billing schemas
class GooglePlayPaymentCreate(BaseModel):
    """Schema for creating a Google Play payment record."""
    product_id: str = Field(..., description="Google Play product ID (e.g., credits_3, credits_5)")
    purchase_token: str = Field(..., description="Google Play purchase token")
    order_id: str = Field(..., description="Google Play order ID")
    user_id: str = Field(..., description="User ID who made the purchase")
    amount: int = Field(..., description="Purchase amount in smallest currency unit")
    currency: str = Field(default="INR", description="Currency code")
    purchase_state: str = Field(default="pending", description="Google Play purchase state")
    acknowledgment_state: str = Field(default="not_acknowledged", description="Google Play acknowledgment state")

    @field_validator('purchase_state')
    @classmethod
    def validate_purchase_state(cls, v):
        """Validate purchase state."""
        valid_states = ['pending', 'purchased', 'cancelled']
        if v not in valid_states:
            raise ValueError(f'Invalid purchase_state. Must be one of: {valid_states}')
        return v

class GooglePlayPaymentResponse(BaseModel):
    """Schema for Google Play payment response."""
    id: str
    user_id: str
    product_id: str
    purchase_token: str
    amount: int
    currency: str
    status: str
    purchase_state: str
    acknowledgment_state: str
    is_acknowledged: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GooglePlayPaymentAcknowledge(BaseModel):
    """Schema for acknowledging a Google Play payment."""
    order_id: str = Field(..., description="Google Play order ID")
    purchase_token: str = Field(..., description="Google Play purchase token")
    product_id: str = Field(..., description="Google Play product ID (credits_3, credits_5, unlimited_monthly, unlimited_yearly)")

class SubscriptionCreate(BaseModel):
    """Schema for creating a Google Play subscription record."""
    product_id: str = Field(..., description="Google Play subscription product ID (e.g., unlimited_monthly, unlimited_yearly)")
    purchase_token: str = Field(..., description="Google Play purchase token")
    subscription_id: str = Field(..., description="Google Play subscription ID")
    status: str = Field(default="active", description="Subscription status")
    purchase_state: str = Field(default="pending", description="Google Play purchase state")
    start_time: Optional[int] = Field(None, description="Subscription start time (milliseconds since epoch)")
    end_time: Optional[int] = Field(None, description="Subscription end time (milliseconds since epoch)")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["active", "cancelled", "expired", "grace_period"]
        if v not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        return v

    @field_validator('purchase_state')
    @classmethod
    def validate_purchase_state(cls, v):
        valid_states = ["pending", "purchased", "cancelled", "failed"]
        if v not in valid_states:
            raise ValueError(f"Invalid purchase_state. Must be one of: {valid_states}")
        return v

class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""
    id: str
    user_id: str
    product_id: str
    purchase_token: str
    status: str
    purchase_state: str
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    acknowledgment_state: str
    is_acknowledged: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SubscriptionAcknowledge(BaseModel):
    """Schema for acknowledging a Google Play subscription."""
    subscription_id: str = Field(..., description="Google Play subscription ID")
    purchase_token: str = Field(..., description="Google Play purchase token")

class PurchaseHistoryResponse(BaseModel):
    """Schema for purchase history response."""
    google_play_payments: list[GooglePlayPaymentResponse]
    subscriptions: list[SubscriptionResponse]
    total_count: int

class CreditBalanceResponse(BaseModel):
    """Schema for credit balance response."""
    credits: int
    has_unlimited_chat: bool
    subscription_type: str
    subscription_status: str
    subscription_end_date: Optional[datetime] = None

# RTDN Event schemas
class RTDNPayload(BaseModel):
    """Schema for RTDN event data."""
    message_id: str = Field(..., description="Pub/Sub message ID for deduplication")
    purchase_token: str = Field(..., description="Google Play purchase token")
    product_id: Optional[str] = Field(None, description="Google Play product ID")
    event_type: str = Field(..., description="Type of RTDN event")
    raw_data: Dict[str, Any] = Field(..., description="Full RTDN payload")

class PurchaseEventResponse(BaseModel):
    """Schema for purchase event response."""
    id: int
    message_id: str
    purchase_token: str
    user_id: Optional[str]
    product_id: Optional[str]
    event_type: str
    status: str
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True

# Verify endpoint schemas
class VerifyPayload(BaseModel):
    """Schema for verify endpoint payload. Only include essential fields from client."""
    product_id: str = Field(..., description="Google Play product ID")
    purchase_token: str = Field(..., description="Google Play purchase token")

class VerifyResponse(BaseModel):
    """Schema for verify endpoint response."""
    status: str = Field(..., description="Verification status")
    credits_added: Optional[int] = Field(None, description="Credits added to user account")
    subscription_activated: Optional[bool] = Field(None, description="Whether subscription was activated")
    message: str = Field(..., description="Response message")

 