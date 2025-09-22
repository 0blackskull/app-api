from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class DeviceBase(BaseModel):
    fcm_token: str
    platform: Optional[str] = None
    app_version: Optional[str] = None
    lang: Optional[str] = None
    push_enabled: bool = True

class DeviceCreate(DeviceBase):
    user_id: str

class Device(DeviceBase):
    id: str
    user_id: str
    last_seen: datetime
    created_at: datetime

    class Config:
        from_attributes = True

# Legacy schemas needed by the devices router
class DeviceRegisterRequest(BaseModel):
    fcm_token: str
    platform: Optional[str] = None
    app_version: Optional[str] = None
    lang: Optional[str] = None

class DeviceHeartbeatRequest(BaseModel):
    fcm_token: str

class DeviceResponse(BaseModel):
    id: str
    user_id: str
    platform: Optional[str] = None
    app_version: Optional[str] = None
    lang: Optional[str] = None
    push_enabled: bool = True 