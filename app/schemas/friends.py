from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, date
from enum import Enum

class FriendRequestStatus(str, Enum):
    PENDING = "pending"

class FriendRequestBase(BaseModel):
    recipient_username: str = Field(..., description="Username of the user to send friend request to")

class FriendRequestCreate(FriendRequestBase):
    pass

class FriendRequestResponse(BaseModel):
    id: str
    requester_id: str
    recipient_id: str
    status: str  # Changed from FriendRequestStatus to str
    created_at: datetime
    requester_username: Optional[str] = None
    recipient_username: Optional[str] = None

class FriendRequestUpdate(BaseModel):
    status: str  # Changed from FriendRequestStatus to str

class FriendshipResponse(BaseModel):
    id: str
    user1_id: str
    user2_id: str
    created_at: datetime
    friend_username: Optional[str] = None
    friend_display_name: Optional[str] = None
    friend_pronouns: Optional[str] = None
    friend_current_streak: int = 0
    friend_longest_streak: int = 0
    friend_effective_streak: int = 0
    friend_last_active_local_date: Optional[date] = None

class FriendsListResponse(BaseModel):
    friends: List[FriendshipResponse]
    total_count: int
    page: int
    page_size: int

class FriendRequestsListResponse(BaseModel):
    requests: List[FriendRequestResponse]
    total_count: int
    page: int
    page_size: int

class FriendRequestStatusResponse(BaseModel):
    message: str
    status: str 