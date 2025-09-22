from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from typing import List, Optional, Tuple
from app.models.friend_request import FriendRequest
from app.models.friendship import Friendship
from app.models.user import User
from app.models.user_streak import UserStreak
from app.utils.logger import get_logger

logger = get_logger(__name__)

class FriendsCRUD:
    
    @staticmethod
    def send_friend_request(db: Session, requester_id: str, recipient_username: str) -> Optional[FriendRequest]:
        """Send a friend request to a user by username"""
        try:
            # Find recipient by username
            recipient = db.query(User).filter(User.username == recipient_username).first()
            if not recipient:
                return None
            
            # Check if recipient has a username
            if not recipient.username:
                return None
            
            # Prevent self-friend requests
            if requester_id == recipient.id:
                return None
            
            # Check if friendship already exists
            if FriendsCRUD._are_friends(db, requester_id, recipient.id):
                return None

            existing_request = db.query(FriendRequest).filter(
                and_(
                    or_(
                        and_(FriendRequest.requester_id == requester_id, FriendRequest.recipient_id == recipient.id),
                        and_(FriendRequest.requester_id == recipient.id, FriendRequest.recipient_id == requester_id)
                    ),
                    FriendRequest.status == "pending"
                )
            ).first()
            
            if existing_request:
                return None
            
            # Create new request
            friend_request = FriendRequest(
                requester_id=requester_id,
                recipient_id=recipient.id,
                status="pending"
            )
            db.add(friend_request)
            db.commit()
            db.refresh(friend_request)
            return friend_request
            
        except Exception as e:
            logger.error(f"Error sending friend request: {e}")
            db.rollback()
            return None
    
    @staticmethod
    def accept_friend_request(db: Session, user_id: str, request_id: str) -> Optional[Friendship]:
        """Accept a friend request and create a friendship."""
        # Get the friend request
        friend_request = db.query(FriendRequest).filter(FriendRequest.id == request_id).first()
        if not friend_request:
            return None
        
        # Verify the current user is the recipient
        if friend_request.recipient_id != user_id:
            return None
        
        # Verify the request is still pending
        if friend_request.status != "pending":
            return None
        
        # Create friendship (ensure user1_id < user2_id for consistency)
        user1_id, user2_id = sorted([friend_request.requester_id, friend_request.recipient_id])
        friendship = Friendship(
            user1_id=user1_id,
            user2_id=user2_id
        )
        db.add(friendship)
        
        # Delete the friend request
        db.delete(friend_request)
        
        db.commit()
        db.refresh(friendship)
        return friendship

    @staticmethod
    def reject_friend_request(db: Session, user_id: str, request_id: str) -> bool:
        """Reject a friend request."""
        # Get the friend request
        friend_request = db.query(FriendRequest).filter(FriendRequest.id == request_id).first()
        if not friend_request:
            return False
        
        # Verify the current user is the recipient
        if friend_request.recipient_id != user_id:
            return False
        
        # Delete the friend request
        db.delete(friend_request)
        db.commit()
        return True

    @staticmethod
    def cancel_friend_request(db: Session, user_id: str, request_id: str) -> bool:
        """Cancel a sent friend request."""
        # Get the friend request
        friend_request = db.query(FriendRequest).filter(FriendRequest.id == request_id).first()
        if not friend_request:
            return False
        
        # Verify the current user is the requester
        if friend_request.requester_id != user_id:
            return False
        
        # Delete the friend request
        db.delete(friend_request)
        db.commit()
        return True
    
    @staticmethod
    def get_friend_requests(db: Session, user_id: str, page: int = 1, page_size: int = 20) -> Tuple[List[FriendRequest], int]:
        """Get pending friend requests for a user"""
        try:
            query = db.query(FriendRequest).filter(
                and_(
                    FriendRequest.recipient_id == user_id,
                    FriendRequest.status == "pending"
                )
            ).options(
                joinedload(FriendRequest.requester)
            ).order_by(FriendRequest.created_at.desc())
            
            total = query.count()
            requests = query.offset((page - 1) * page_size).limit(page_size).all()
            
            return requests, total
            
        except Exception as e:
            logger.error(f"Error getting friend requests: {e}")
            return [], 0
    
    @staticmethod
    def get_sent_friend_requests(db: Session, user_id: str, page: int = 1, page_size: int = 20) -> Tuple[List[FriendRequest], int]:
        """Get sent friend requests by a user"""
        try:
            query = db.query(FriendRequest).filter(
                and_(
                    FriendRequest.requester_id == user_id,
                    FriendRequest.status == "pending"
                )
            ).options(
                joinedload(FriendRequest.recipient)
            ).order_by(FriendRequest.created_at.desc())
            
            total = query.count()
            requests = query.offset((page - 1) * page_size).limit(page_size).all()
            
            return requests, total
            
        except Exception as e:
            logger.error(f"Error getting sent friend requests: {e}")
            return [], 0
    
    @staticmethod
    def get_friends_list(db: Session, user_id: str, page: int = 1, page_size: int = 20) -> Tuple[List[Friendship], int]:
        """Get friends list for a user with streak information using single JOIN query"""
        try:
            # Create aliases for user streaks to handle both user1 and user2 streaks
            from sqlalchemy.orm import aliased
            UserStreak1 = aliased(UserStreak)
            UserStreak2 = aliased(UserStreak)
            
            # Single query with JOINs to get all data at once
            query = db.query(
                Friendship,
                UserStreak1.current_streak.label('user1_current_streak'),
                UserStreak1.longest_streak.label('user1_longest_streak'),
                UserStreak1.last_active_local_date.label('user1_last_active_date'),
                UserStreak1.timezone.label('user1_timezone'),
                UserStreak2.current_streak.label('user2_current_streak'),
                UserStreak2.longest_streak.label('user2_longest_streak'),
                UserStreak2.last_active_local_date.label('user2_last_active_date'),
                UserStreak2.timezone.label('user2_timezone')
            ).filter(
                or_(
                    Friendship.user1_id == user_id,
                    Friendship.user2_id == user_id
                )
            ).options(
                joinedload(Friendship.user1),
                joinedload(Friendship.user2)
            ).outerjoin(
                UserStreak1, Friendship.user1_id == UserStreak1.user_id
            ).outerjoin(
                UserStreak2, Friendship.user2_id == UserStreak2.user_id
            ).order_by(Friendship.created_at.desc())
            
            # Get total count from the main query (before pagination)
            total = query.count()
            
            # Get paginated results
            results = query.offset((page - 1) * page_size).limit(page_size).all()
            
            # Process results and attach streak data
            friendships = []
            for row in results:
                friendship = row[0]  # The Friendship object
                
                # Determine which user is the friend and get their streak data
                if friendship.user1_id == user_id:
                    # user2 is the friend
                    friend_streak_data = {
                        'current_streak': row.user2_current_streak,
                        'longest_streak': row.user2_longest_streak,
                        'last_active_local_date': row.user2_last_active_date,
                        'timezone': row.user2_timezone
                    }
                else:
                    # user1 is the friend
                    friend_streak_data = {
                        'current_streak': row.user1_current_streak,
                        'longest_streak': row.user1_longest_streak,
                        'last_active_local_date': row.user1_last_active_date,
                        'timezone': row.user1_timezone
                    }
                
                # Create a simple object to hold streak data
                class StreakData:
                    def __init__(self, data):
                        self.current_streak = data['current_streak']
                        self.longest_streak = data['longest_streak']
                        self.last_active_local_date = data['last_active_local_date']
                        self.timezone = data['timezone']
                
                # Attach streak data to friendship object
                if any(friend_streak_data.values()):  # Only if we have streak data
                    setattr(friendship, 'friend_streak_data', StreakData(friend_streak_data))
                else:
                    setattr(friendship, 'friend_streak_data', None)
                
                friendships.append(friendship)
            
            return friendships, total
            
        except Exception as e:
            logger.error(f"Error getting friends list: {e}")
            return [], 0
    
    @staticmethod
    def remove_friend(db: Session, user_id: str, friend_id: str) -> bool:
        """Remove a friend (unfriend)"""
        try:
            # Find friendship (ensure user1_id < user2_id)
            user1_id, user2_id = sorted([user_id, friend_id])
            friendship = db.query(Friendship).filter(
                and_(
                    Friendship.user1_id == user1_id,
                    Friendship.user2_id == user2_id
                )
            ).first()
            
            if not friendship:
                return False
            
            db.delete(friendship)
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error removing friend: {e}")
            db.rollback()
            return False
    
    @staticmethod
    def _are_friends(db: Session, user1_id: str, user2_id: str) -> bool:
        """Check if two users are friends"""
        try:
            user1_id, user2_id = sorted([user1_id, user2_id])
            friendship = db.query(Friendship).filter(
                and_(
                    Friendship.user1_id == user1_id,
                    Friendship.user2_id == user2_id
                )
            ).first()
            return friendship is not None
        except Exception as e:
            logger.error(f"Error checking friendship: {e}")
            return False

    @staticmethod
    def get_relationship_status_map(db: Session, current_user_id: str, other_user_ids: List[str]) -> dict[str, str]:
        """Return a map of other_user_id -> relationship status with current user.
        Status is one of: 'friend', 'request_sent', 'request_received', 'none'.
        """
        if not other_user_ids:
            return {}

        # Initialize all as none
        status_map: dict[str, str] = {user_id: 'none' for user_id in other_user_ids}

        try:
            # Friends
            friendships = db.query(Friendship).filter(
                or_(
                    and_(Friendship.user1_id == current_user_id, Friendship.user2_id.in_(other_user_ids)),
                    and_(Friendship.user2_id == current_user_id, Friendship.user1_id.in_(other_user_ids))
                )
            ).all()
            for fr in friendships:
                other_id = fr.user2_id if fr.user1_id == current_user_id else fr.user1_id
                status_map[other_id] = 'friend'

            # Pending requests both directions
            pending_requests = db.query(FriendRequest).filter(
                and_(
                    FriendRequest.status == 'pending',
                    or_(
                        and_(FriendRequest.requester_id == current_user_id, FriendRequest.recipient_id.in_(other_user_ids)),
                        and_(FriendRequest.recipient_id == current_user_id, FriendRequest.requester_id.in_(other_user_ids))
                    )
                )
            ).all()
            for req in pending_requests:
                if req.requester_id == current_user_id:
                    # Only set if not already friends
                    if status_map.get(req.recipient_id) != 'friend':
                        status_map[req.recipient_id] = 'request_sent'
                elif req.recipient_id == current_user_id:
                    if status_map.get(req.requester_id) != 'friend':
                        status_map[req.requester_id] = 'request_received'

            return status_map
        except Exception as e:
            logger.error(f"Error building relationship status map: {e}")
            return status_map 