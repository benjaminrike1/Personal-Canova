from fastapi import APIRouter

router = APIRouter()


@router.get("/conversations")
async def list_conversations():
    """List all conversations."""
    return []


@router.post("/conversations")
async def create_conversation():
    """Start a new conversation."""
    return {}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: int):
    """Get full conversation with messages."""
    return {}


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: int):
    """Send a message and get coach response."""
    return {}
