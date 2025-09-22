from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List
from app.models.device import Device


def register_or_update_device(
    db: Session,
    user_id: str,
    fcm_token: str,
    platform: str | None,
    app_version: str | None,
    lang: str | None,
) -> Device:
    device = db.query(Device).filter(Device.fcm_token == fcm_token).first()
    if device:
        device.user_id = user_id
        device.platform = platform
        device.app_version = app_version
        device.lang = lang
        device.push_enabled = True
        device.last_seen = func.now()
    else:
        device = Device(
            user_id=user_id,
            fcm_token=fcm_token,
            platform=platform,
            app_version=app_version,
            lang=lang,
            push_enabled=True,
        )
        db.add(device)
    db.commit()
    db.refresh(device)
    return device


def list_user_tokens(db: Session, user_id: str) -> List[str]:
    return [
        d.fcm_token
        for d in db.query(Device)
        .filter(Device.user_id == user_id, Device.push_enabled == True)
        .all()
    ]


def delete_by_token(db: Session, fcm_token: str) -> None:
    d = db.query(Device).filter(Device.fcm_token == fcm_token).first()
    if d:
        db.delete(d)
        db.commit()


def touch_heartbeat(db: Session, fcm_token: str) -> None:
    d = db.query(Device).filter(Device.fcm_token == fcm_token).first()
    if d:
        d.last_seen = func.now()
        db.commit() 