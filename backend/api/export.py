from fastapi import APIRouter

router = APIRouter()


@router.get("/checkins")
async def export_checkins():
    """Export all check-ins as CSV."""
    return {}


@router.get("/activities")
async def export_activities():
    """Export all activities as CSV."""
    return {}


@router.get("/notebook")
async def export_notebook():
    """Export coach notebook entries as CSV."""
    return {}
