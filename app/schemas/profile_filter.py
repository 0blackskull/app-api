from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class ProfileFilter(BaseModel):
    """Common filter for chat context participants.
    - participant_user_ids: Firebase user IDs of friends to include as participants
    - participant_partner_ids: Partner record IDs (belonging to the same user) to include as participants
    """
    participant_user_ids: Optional[List[str]] = Field(
        None,
        description="Participant user IDs (friends) to include in the chat context"
    )
    participant_partner_ids: Optional[List[str]] = Field(
        None,
        description="Participant partner IDs (belonging to the user) to include in the chat context"
    )
    compatibility_type: Optional[Literal["love", "friendship"]] = Field(
        None,
        description="Compatibility type context when exactly one participant is present"
    ) 