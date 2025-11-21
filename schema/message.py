from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class MessageSchema(BaseModel):
    id: int
    chat_id: int
    sender: str
    type: str
    content: str
    timestamp: datetime

    class Config:
        from_attributes = True