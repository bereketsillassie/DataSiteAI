from fastapi import APIRouter, HTTPException
from app.chatbot.schemas import ChatRequest, ChatResponse
from app.chatbot.agent import DatacenterAssistant

router = APIRouter(prefix="/chat", tags=["AI Chatbot"])
# Initialize the assistant once so it persists
assistant = DatacenterAssistant()

@router.post("/", response_model=ChatResponse)
def chat_with_assistant(request: ChatRequest):
    try:
        # Note: No 'await' needed for the 2026 SDK standard call
        reply = assistant.generate_response(
            message=request.message, 
            history=request.history, 
            context=request.location_context
        )
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))