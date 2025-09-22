from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.schemas.device import DeviceRegisterRequest, DeviceHeartbeatRequest, DeviceResponse
from app.crud.device import register_or_update_device, delete_by_token, list_user_tokens, touch_heartbeat

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/register", response_model=DeviceResponse)
async def register_device(
    body: DeviceRegisterRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    d = register_or_update_device(
        db,
        current_user.id,
        body.fcm_token,
        body.platform,
        body.app_version,
        body.lang,
    )
    return DeviceResponse(
        id=d.id,
        user_id=d.user_id,
        platform=d.platform,
        app_version=d.app_version,
        lang=d.lang,
        push_enabled=d.push_enabled,
    )


@router.delete("/unregister")
async def unregister_device(
    fcm_token: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    delete_by_token(db, fcm_token)
    return {"status": "ok"}


@router.post("/heartbeat")
async def heartbeat(
    body: DeviceHeartbeatRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    touch_heartbeat(db, body.fcm_token)
    return {"status": "ok"}


@router.get("", response_model=list[str])
async def my_tokens(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return list_user_tokens(db, current_user.id) 