from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.auth import get_current_user
from app.schemas.user import CurrentUser

router = APIRouter(
    prefix="/credits",
    tags=["credits"],
    responses={404: {"description": "Not found"}}
)

@router.get("/balance")
async def get_credit_balance(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the current credit balance for the authenticated user.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Current credit balance
    """
    credits = crud.get_user_credits(db, current_user.id)
    return {"credits": credits}
