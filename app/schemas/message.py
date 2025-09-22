from pydantic import BaseModel
from datetime import datetime

class Message(BaseModel):
    id: str
    user_id: str
    thread_id: str
    role: str
    query: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True 