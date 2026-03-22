from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str 
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    location_context: Optional[dict] = None 

class ChatResponse(BaseModel):
    reply: str