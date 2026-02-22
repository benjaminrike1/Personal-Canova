from fastapi import APIRouter

router = APIRouter()


@router.get("/current")
async def current_week():
    """Get current week's training plan."""
    return []


@router.get("/week/{week_start}")
async def get_week(week_start: str):
    """Get a specific week's plan by Monday date."""
    return []


@router.post("/")
async def create_plan_entry():
    """Add a session to the training plan."""
    return {}


@router.put("/{entry_id}")
async def update_plan_entry(entry_id: int):
    """Update a planned session."""
    return {}


@router.delete("/{entry_id}")
async def delete_plan_entry(entry_id: int):
    """Remove a planned session."""
    return {"deleted": True}


@router.get("/{entry_id}/versions")
async def plan_entry_versions(entry_id: int):
    """Get version history for a plan entry."""
    return []
