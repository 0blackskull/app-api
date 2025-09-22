from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional
import html
from app.utils.logger import get_logger
from datetime import datetime

from app.database import get_db
from app.auth import get_current_user
from app.schemas.user import CurrentUser
from app.middleware.rate_limit import limiter
from app.config import settings
from app.utils.email_sender import create_email_sender

logger = get_logger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


class HelpEmailRequest(BaseModel):
    subject: str = Field(..., min_length=5, max_length=120)
    message: str = Field(..., min_length=10, max_length=2000)
    category: Optional[str] = Field(None, pattern=r"^(billing|bug|feedback|other)$")
    platform: Optional[str] = Field(None, pattern=r"^(ios|android|web)$")
    app_version: Optional[str] = Field(None, max_length=40)


@router.post("/help-email")
@limiter.limit("3/minute;20/day")
async def send_help_email(
    body: HelpEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if not settings.SUPPORT_TO_EMAIL:
        raise HTTPException(status_code=500, detail="Support email not configured")

    subject = body.subject.strip()
    message = body.message.strip()

    # Escape user-provided content
    esc_subject = html.escape(subject)
    esc_message = html.escape(message).replace("\n", "<br/>")

    # Build simple HTML
    meta_rows = [
        ("User ID", user.id),
        ("Email", user.email or "-"),
        ("Username", user.username or "-"),
        ("Display Name", user.display_name or "-"),
        ("Platform", body.platform or "-"),
        ("App Version", body.app_version or "-"),
        ("Category", body.category or "-"),
        ("Timestamp", datetime.utcnow().isoformat() + "Z"),
    ]
    meta_html = "".join(
        f"<tr><td style='padding:4px 8px;color:#555'>{html.escape(k)}</td><td style='padding:4px 8px'><b>{html.escape(str(v))}</b></td></tr>"
        for k, v in meta_rows
    )

    html_content = f"""
    <div style='font-family:Arial,sans-serif;font-size:14px;color:#222'>
      <h2 style='margin:0 0 12px'>New Help Request</h2>
      <table style='border-collapse:collapse;margin-bottom:12px'>{meta_html}</table>
      <div style='padding:12px;border:1px solid #eee;border-radius:6px;background:#fafafa'>
        {esc_message}
      </div>
    </div>
    """

    sender = create_email_sender()
    try:
        resp = sender.send_email(
            to_email=settings.SUPPORT_TO_EMAIL,
            subject=f"[Help] {esc_subject}",
            html_content=html_content,
            reply_to=user.email if user.email else None,
            bcc=settings.SUPPORT_BCC_EMAIL or None,
        )
        return {"success": True, "provider_response": resp}
    except Exception as e:
        logger.exception("Failed to send help email: %s", e)
        raise HTTPException(status_code=500, detail="Failed to send help email") 