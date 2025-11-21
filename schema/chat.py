from pydantic import BaseModel
from datetime import datetime

class ChatSchema(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime
    title: str
    
    class Config:
        from_attributes = True