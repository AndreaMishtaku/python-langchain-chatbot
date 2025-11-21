from typing import Optional
from pydantic import BaseModel, Field
from assets.enum import InteractionType

class ChatRequest(BaseModel):
    prompt: str = Field(...,  min_length=1)
    chat_id: Optional[str] = None
    output_type: Optional[InteractionType] = InteractionType.TEXT