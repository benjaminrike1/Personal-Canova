from fastapi import APIRouter

router = APIRouter()


@router.get("/aerobic-efficiency")
async def aerobic_efficiency(sport: str = "Run", weeks: int = 12):
    """HR vs pace/power over time for aerobic efficiency curve."""
    return []


@router.get("/training-load")
async def training_load(weeks: int = 12):
    """CTL, ATL, TSB curves with key session markers."""
    return []


@router.get("/key-sessions")
async def key_session_progression(session_type: str | None = None, weeks: int = 12):
    """Key session performance trends over time."""
    return []


@router.get("/zone-distribution")
async def zone_distribution(sport: str = "Run", weeks: int = 4):
    """Weekly time-in-zone bar chart data."""
    return []


@router.get("/planned-vs-actual")
async def planned_vs_actual(weeks: int = 12):
    """Planned vs actual training hours per week."""
    return []


@router.get("/session-compare")
async def session_compare(activity_ids: str = ""):
    """Overlay data for selected sessions."""
    return []
