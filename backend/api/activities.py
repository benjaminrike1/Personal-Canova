from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_activities(days: int = 14, sport: str | None = None):
    """List recent activities, optionally filtered by sport."""
    return []


@router.get("/{activity_id}")
async def get_activity(activity_id: int):
    """Get single activity with weather context."""
    return {}


@router.post("/sync")
async def sync_activities():
    """Trigger sync from Intervals.icu."""
    return {"status": "ok", "synced": 0}


@router.post("/{activity_id}/key-session")
async def tag_key_session(activity_id: int):
    """Tag an activity as a key session."""
    return {}


@router.delete("/{activity_id}/key-session")
async def untag_key_session(activity_id: int):
    """Remove key session tag from an activity."""
    return {}
