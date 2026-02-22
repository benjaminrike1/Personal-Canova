"""Weather API routes — daily weather retrieval and sync trigger."""

from fastapi import APIRouter, HTTPException

from backend.services.weather import (
    get_daily_weather_from_db,
    sync_daily_weather,
)

router = APIRouter()


@router.get("/daily")
async def daily_weather(days: int = 7):
    """Get daily weather for the last N days from the database.

    Query params:
        days: Number of days to look back (default 7).

    Returns:
        List of daily weather records ordered by date descending.
    """
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=400,
            detail="days must be between 1 and 365",
        )
    return get_daily_weather_from_db(days=days)


@router.post("/sync")
async def sync_weather(days: int = 7):
    """Trigger weather sync for the athlete's home location.

    Fetches daily weather from Open-Meteo for the last N days and
    stores results in the daily_weather table with UPSERT semantics.

    The athlete's location is read from athlete_profile. If no profile
    exists, defaults to Trondheim, Norway (63.43, 10.40).

    Query params:
        days: Number of days to sync (default 7).

    Returns:
        Status and count of days synced.
    """
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=400,
            detail="days must be between 1 and 365",
        )
    try:
        count = await sync_daily_weather(days=days)
        return {"status": "ok", "synced": count}
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Weather sync failed: {exc}",
        )
