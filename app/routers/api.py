from fastapi import APIRouter, Depends
from app.auth import get_current_user
from app.config import settings
from app import schemas

router = APIRouter()

@router.get("/public")
async def public_route():
    """
    Public endpoint that doesn't require authentication.
    """
    return {"message": "This is a public endpoint"}

@router.get("/protected")
async def protected_route(user: schemas.CurrentUser = Depends(get_current_user)):
    """
    Protected endpoint that requires Firebase authentication.
    
    Args:
        user: The authenticated Firebase user
    """
    return {
        "message": "This is a protected endpoint",
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name
    } 