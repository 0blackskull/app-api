from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.schemas import CurrentUser, RantRequest, RantResponse
from app.crud.streak import ping_streak
from app.crud.subscription import get_active_subscription
from app.crud.user import get_user
from app.crud.rant import create_rant
from app.llm.client import LLMClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/rants", tags=["rants"])

# Initialize LLM client
llm_client = LLMClient()


@router.post("/", response_model=RantResponse)
async def submit_rant(
    rant_request: RantRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit a rant or expression and get therapeutic response.
    Streak is updated only if the content is validated as a genuine rant.
    """
    try:
        # Get user for personalization
        user = get_user(db, current_user.id)
        user_name = user.name if user and user.name else "N/A"
        
        # Analyze the rant content using LLM with personalized context
        rant_analysis = await llm_client.analyze_rant(rant_request.content, user_name)
        
        # Initialize streak variables
        streak_updated = False
        current_streak = 0
        longest_streak = 0
        
        # Only update streak if it's a valid rant
        if rant_analysis.is_valid_rant:
            # Check if user has active subscription (streak protection)
            active_subscription = get_active_subscription(db, current_user.id)
            has_subscription_protection = active_subscription is not None
            
            # Update streak with subscription protection
            streak, effective, today_local = ping_streak(db, current_user.id, has_subscription_protection)
            streak_updated = True
            current_streak = streak.current_streak
            longest_streak = streak.longest_streak
            
            logger.info(
                f"Streak updated for user {current_user.id}: "
                f"current={current_streak}, longest={longest_streak}, "
                f"subscription_protection={has_subscription_protection}"
            )

        else:
            logger.info(
                f"Rant not validated for user {current_user.id}: "
                f"type={rant_analysis.rant_type}, reason={rant_analysis.validation_reasoning}"
            )
        
        # Store the rant in the database
        rant_data = {
            "user_id": current_user.id,
            "content": rant_request.content,
            "therapist_response": rant_analysis.therapist_response,
            "is_valid_rant": rant_analysis.is_valid_rant,
            "rant_type": rant_analysis.rant_type,
            "emotional_tone": rant_analysis.emotional_tone,
            "validation_reasoning": rant_analysis.validation_reasoning,
            "streak_updated": streak_updated,
            "current_streak": current_streak,
            "longest_streak": longest_streak
        }
        
        db_rant = create_rant(db, rant_data)
        logger.info(f"Stored rant {db_rant.id} for user {current_user.id}")
        
        return RantResponse(
            rant_id=str(db_rant.id),
            therapist_response=rant_analysis.therapist_response,
            is_valid_rant=rant_analysis.is_valid_rant,
            rant_type=rant_analysis.rant_type,
            emotional_tone=rant_analysis.emotional_tone,
            validation_reasoning=rant_analysis.validation_reasoning,
            streak_updated=streak_updated,
            current_streak=current_streak,
            longest_streak=longest_streak,
            submitted_at=db_rant.submitted_at
        )
        
    except Exception as e:
        logger.exception(f"Rant submission failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process rant") 