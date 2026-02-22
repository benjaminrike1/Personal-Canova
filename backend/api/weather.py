from fastapi import APIRouter

router = APIRouter()


@router.get("/daily")
async def daily_weather(days: int = 7):
    """Get daily weather for the last N days."""
    return []


@router.post("/sync")
async def sync_weather():
    """Fetch and cache weather for recent activities and daily forecast."""
    return {"status": "ok", "synced": 0}
