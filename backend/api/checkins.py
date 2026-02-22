from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_checkins(days: int = 14):
    """List check-ins for the last N days."""
    return []


@router.get("/today")
async def today_status():
    """Get today's check-in status for dashboard."""
    return {"morning": None, "evening": None, "weekend": None, "weekly": None}


@router.post("/")
async def create_checkin():
    """Submit a check-in (morning/evening/weekend/weekly)."""
    return {}


@router.put("/{checkin_id}")
async def update_checkin(checkin_id: int):
    """Update a partial check-in."""
    return {}
