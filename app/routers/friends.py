from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user
from app.crud.friends import FriendsCRUD
from app.crud.streak import compute_effective_streak
from app.schemas.friends import (
    FriendRequestCreate, FriendRequestResponse, FriendshipResponse, FriendsListResponse, FriendRequestsListResponse,
    FriendRequestStatusResponse
)
from app.models.user import User
from app.utils.logger import get_logger
from datetime import datetime, timezone as dt_timezone
import pytz

logger = get_logger(__name__)

router = APIRouter(prefix="/friends", tags=["friends"])

@router.post("/request", response_model=FriendRequestResponse)
async def send_friend_request(
    request: FriendRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a friend request to another user by username"""
    try:
        # Check if current user has a username set
        if not current_user.username:
            raise HTTPException(
                status_code=400,
                detail="You must set a username before sending friend requests. Please update your account first."
            )
        
        friend_request = FriendsCRUD.send_friend_request(
            db, current_user.id, request.recipient_username
        )
        
        if not friend_request:
            raise HTTPException(
                status_code=400,
                detail="Unable to send friend request. User not found, user doesn't have a username set, already friends, or request already exists."
            )
        
        # Load user data for response and get recipient's actual username
        db.refresh(friend_request)
        recipient = db.query(User).filter(User.id == friend_request.recipient_id).first()
        
        return FriendRequestResponse(
            id=friend_request.id,
            requester_id=friend_request.requester_id,
            recipient_id=friend_request.recipient_id,
            status=friend_request.status,
            created_at=friend_request.created_at,
            requester_username=current_user.username,
            recipient_username=recipient.username if recipient else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_friend_request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/request/{request_id}/accept", response_model=FriendRequestStatusResponse)
async def accept_friend_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept a friend request"""
    try:
        friendship = FriendsCRUD.accept_friend_request(db, current_user.id, request_id)
        
        if not friendship:
            raise HTTPException(
                status_code=404,
                detail="Friend request not found or already processed"
            )
        
        # Load user data for response
        db.refresh(friendship)
        friend_id = friendship.user2_id if friendship.user1_id == current_user.id else friendship.user1_id
        
        # Get friend's user info
        friend = db.query(User).filter(User.id == friend_id).first()
        
        return FriendRequestStatusResponse(
            message="Friend request accepted successfully",
            status="accepted"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in accept_friend_request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/request/{request_id}/reject", response_model=FriendRequestStatusResponse)
async def reject_friend_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reject a friend request"""
    try:
        success = FriendsCRUD.reject_friend_request(db, current_user.id, request_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Friend request not found or already processed"
            )
        
        return FriendRequestStatusResponse(
            message="Friend request rejected successfully",
            status="rejected"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reject_friend_request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/request/{request_id}", response_model=FriendRequestStatusResponse)
async def cancel_friend_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a sent friend request"""
    try:
        success = FriendsCRUD.cancel_friend_request(db, current_user.id, request_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Friend request not found or already processed"
            )
        
        return FriendRequestStatusResponse(
            message="Friend request cancelled successfully",
            status="cancelled"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in cancel_friend_request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/requests", response_model=FriendRequestsListResponse)
async def get_friend_requests(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get pending friend requests for the current user"""
    try:
        requests, total = FriendsCRUD.get_friend_requests(db, current_user.id, page, page_size)
        
        return FriendRequestsListResponse(
            requests=[
                FriendRequestResponse(
                    id=req.id,
                    requester_id=req.requester_id,
                    recipient_id=req.recipient_id,
                    status=req.status,
                    created_at=req.created_at,
                    requester_username=req.requester.username if req.requester else None,
                    recipient_username=current_user.username
                ) for req in requests
            ],
            total_count=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error in get_friend_requests: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/requests/sent", response_model=FriendRequestsListResponse)
async def get_sent_friend_requests(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get sent friend requests by the current user"""
    try:
        requests, total = FriendsCRUD.get_sent_friend_requests(db, current_user.id, page, page_size)
        
        return FriendRequestsListResponse(
            requests=[
                FriendRequestResponse(
                    id=req.id,
                    requester_id=req.requester_id,
                    recipient_id=req.recipient_id,
                    status=req.status,
                    created_at=req.created_at,
                    requester_username=current_user.username,
                    recipient_username=req.recipient.username if req.recipient else None
                ) for req in requests
            ],
            total_count=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error in get_sent_friend_requests: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/list", response_model=FriendsListResponse)
async def get_friends_list(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search_username: str | None = Query(None, description="Optional search on friend's username"),
    search_display_name: str | None = Query(None, description="Optional search on friend's display name"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get friends list for the current user with streak information and optional username and display name search"""
    try:
        friendships, total = FriendsCRUD.get_friends_list(db, current_user.id, page, page_size)
        
        # Helper function to get today's date in a timezone
        def _get_today_in_tz(tz_name: str) -> datetime.date:
            now_utc = datetime.now(dt_timezone.utc)
            tz = pytz.timezone(tz_name)
            now_local = now_utc.astimezone(tz)
            return now_local.date()
        
        items = []
        for friendship in friendships:
            friend_user = friendship.user2 if friendship.user1_id == current_user.id else friendship.user1
            # Apply optional filters
            if search_username and friend_user and friend_user.username:
                if search_username.lower() not in friend_user.username.lower():
                    continue
            if search_display_name and friend_user and friend_user.display_name:
                if search_display_name.lower() not in friend_user.display_name.lower():
                    continue
            
            # Get streak information for the friend
            friend_streak = getattr(friendship, 'friend_streak_data', None)
            friend_current_streak = 0
            friend_longest_streak = 0
            friend_effective_streak = 0
            friend_last_active_local_date = None
            
            if friend_streak:
                friend_current_streak = friend_streak.current_streak or 0
                friend_longest_streak = friend_streak.longest_streak or 0
                friend_last_active_local_date = friend_streak.last_active_local_date
                
                # Compute effective streak (assuming no subscription protection for friends)
                if friend_streak.timezone and friend_streak.last_active_local_date:
                    try:
                        today_local = _get_today_in_tz(friend_streak.timezone)
                        friend_effective_streak = compute_effective_streak(
                            friend_current_streak,
                            friend_last_active_local_date,
                            today_local,
                            has_subscription_protection=False  # We don't know friend's subscription status
                        )
                    except Exception as e:
                        logger.warning(f"Error computing effective streak for friend {friend_user.id}: {e}")
                        friend_effective_streak = friend_current_streak
                else:
                    friend_effective_streak = friend_current_streak
            
            items.append(
                FriendshipResponse(
                    id=friendship.id,
                    user1_id=friendship.user1_id,
                    user2_id=friendship.user2_id,
                    created_at=friendship.created_at,
                    friend_username=(
                        friendship.user2.username if friendship.user1_id == current_user.id 
                        else friendship.user1.username
                    ),
                    friend_display_name=(
                        friendship.user2.display_name if friendship.user1_id == current_user.id 
                        else friendship.user1.display_name
                    ),
                    friend_pronouns=(
                        friendship.user2.pronouns if friendship.user1_id == current_user.id
                        else friendship.user1.pronouns
                    ),
                    friend_current_streak=friend_current_streak,
                    friend_longest_streak=friend_longest_streak,
                    friend_effective_streak=friend_effective_streak,
                    friend_last_active_local_date=friend_last_active_local_date
                )
            )
        
        return FriendsListResponse(
            friends=items,
            total_count=len(items) if (search_username or search_display_name) else total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error in get_friends_list: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{friend_username}", response_model=FriendRequestStatusResponse)
async def remove_friend(
    friend_username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a friend (unfriend) by username"""
    try:
        # Find friend by username
        friend = db.query(User).filter(User.username == friend_username).first()
        if not friend:
            raise HTTPException(status_code=404, detail="User not found")
        
        success = FriendsCRUD.remove_friend(db, current_user.id, friend.id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Friendship not found")
        
        return FriendRequestStatusResponse(
            message="Friend removed successfully",
            status="removed"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_friend: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") 