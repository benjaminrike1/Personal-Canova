from fastapi import APIRouter, HTTPException

from backend.core.database import get_db
from backend.services.intervals import (
    IntervalsClient,
    get_recent_activities,
    get_activity_by_id,
)

router = APIRouter()


@router.get("/")
async def list_activities(days: int = 14, sport: str | None = None, limit: int = 50):
    """List recent activities, optionally filtered by sport."""
    return get_recent_activities(days=days, sport=sport, limit=limit)


@router.get("/{activity_id}")
async def get_activity(activity_id: int):
    """Get single activity with all data."""
    act = get_activity_by_id(activity_id)
    if not act:
        raise HTTPException(404, "Activity not found")
    return act


@router.post("/sync")
async def sync_activities(days: int = 30):
    """Trigger sync from Intervals.icu."""
    client = IntervalsClient()
    result = await client.sync_all(days=days)
    return {"status": "ok", **result}


@router.post("/{activity_id}/key-session")
async def tag_key_session(activity_id: int, session_type: str = "general"):
    """Tag an activity as a key session."""
    act = get_activity_by_id(activity_id)
    if not act:
        raise HTTPException(404, "Activity not found")

    with get_db() as db:
        db.execute(
            """INSERT INTO key_sessions (activity_id, session_type)
               VALUES (?, ?)
               ON CONFLICT(activity_id) DO UPDATE SET session_type=excluded.session_type""",
            (activity_id, session_type),
        )
    return {"tagged": True, "activity_id": activity_id, "session_type": session_type}


@router.delete("/{activity_id}/key-session")
async def untag_key_session(activity_id: int):
    """Remove key session tag from an activity."""
    with get_db() as db:
        db.execute("DELETE FROM key_sessions WHERE activity_id = ?", (activity_id,))
    return {"untagged": True, "activity_id": activity_id}
