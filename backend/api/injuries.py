from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_injuries(status: str | None = None):
    """List injuries, optionally filtered by status."""
    return []


@router.get("/active")
async def active_injuries():
    """Get currently active/monitoring injuries."""
    return []


@router.post("/")
async def create_injury():
    """Log a new injury."""
    return {}


@router.put("/{injury_id}")
async def update_injury(injury_id: int):
    """Update injury status or severity."""
    return {}


@router.post("/{injury_id}/update")
async def add_injury_update(injury_id: int):
    """Add a daily severity update to an injury."""
    return {}


@router.get("/{injury_id}/history")
async def injury_history(injury_id: int):
    """Get severity history for an injury."""
    return []
