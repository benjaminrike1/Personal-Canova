from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.database import get_db, dict_from_row, dicts_from_rows
from backend.services.coach import CoachEngine

router = APIRouter()


class ConversationCreate(BaseModel):
    title: str | None = None
    conversation_type: str = "general"


class MessageCreate(BaseModel):
    content: str


@router.get("/conversations")
async def list_conversations():
    """List all conversations, most recent first."""
    with get_db() as db:
        rows = db.execute(
            """SELECT c.*, COUNT(m.id) as message_count
               FROM conversations c
               LEFT JOIN messages m ON m.conversation_id = c.id
               GROUP BY c.id
               ORDER BY c.updated_at DESC"""
        ).fetchall()
        return dicts_from_rows(rows)


@router.post("/conversations")
async def create_conversation(body: ConversationCreate):
    """Start a new conversation."""
    engine = CoachEngine()
    conv_id = engine.create_conversation(
        title=body.title,
        conversation_type=body.conversation_type,
    )
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        return dict_from_row(row)


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: int):
    """Get full conversation with messages."""
    with get_db() as db:
        conv = db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise HTTPException(404, "Conversation not found")

        messages = db.execute(
            """SELECT id, role, content, created_at FROM messages
               WHERE conversation_id = ?
               ORDER BY created_at ASC""",
            (conversation_id,),
        ).fetchall()

        result = dict(conv)
        result["messages"] = dicts_from_rows(messages)
        return result


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: int, body: MessageCreate):
    """Send a message and get coach response."""
    with get_db() as db:
        conv = db.execute(
            "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if not conv:
            raise HTTPException(404, "Conversation not found")

    engine = CoachEngine()
    result = await engine.send_message(conversation_id, body.content)
    return result
