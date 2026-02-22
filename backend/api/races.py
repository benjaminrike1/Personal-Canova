from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_races():
    """List all races, upcoming first."""
    return []


@router.get("/next")
async def next_a_race():
    """Get next upcoming A-race with weeks-to-race."""
    return None


@router.post("/")
async def create_race():
    """Add a race to the calendar."""
    return {}


@router.put("/{race_id}")
async def update_race(race_id: int):
    """Update a race."""
    return {}


@router.delete("/{race_id}")
async def delete_race(race_id: int):
    """Remove a race from the calendar."""
    return {"deleted": True}
