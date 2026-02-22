from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_phases():
    """List all training phases."""
    return []


@router.get("/current")
async def current_phase():
    """Get the currently active training phase."""
    return None


@router.post("/")
async def create_phase():
    """Create a new training phase."""
    return {}


@router.put("/{phase_id}")
async def update_phase(phase_id: int):
    """Update a training phase."""
    return {}


@router.delete("/{phase_id}")
async def delete_phase(phase_id: int):
    """Delete a training phase."""
    return {"deleted": True}
