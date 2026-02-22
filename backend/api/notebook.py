from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_entries(active_only: bool = True):
    """List coach notebook entries."""
    return []


@router.get("/{entry_id}")
async def get_entry(entry_id: int):
    """Get a single notebook entry."""
    return {}


@router.put("/{entry_id}")
async def update_entry(entry_id: int):
    """Update a notebook entry (toggle active, edit content)."""
    return {}
