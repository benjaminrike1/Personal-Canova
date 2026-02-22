from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_records(discipline: str | None = None):
    """List personal records, optionally filtered by discipline."""
    return []


@router.post("/")
async def create_record():
    """Add a personal record."""
    return {}


@router.put("/{record_id}")
async def update_record(record_id: int):
    """Update a personal record."""
    return {}


@router.delete("/{record_id}")
async def delete_record(record_id: int):
    """Remove a personal record."""
    return {"deleted": True}
