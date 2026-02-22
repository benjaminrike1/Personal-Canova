from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.database import get_db, dict_from_row, dicts_from_rows

router = APIRouter()


class ProfileCreate(BaseModel):
    name: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    years_experience: Optional[int] = None
    training_background: Optional[str] = None
    what_worked: Optional[str] = None
    what_didnt_work: Optional[str] = None
    current_goals: Optional[str] = None
    weekly_hours_target_low: Optional[float] = 10.0
    weekly_hours_target_high: Optional[float] = 15.0
    work_hours_baseline: Optional[float] = 60.0
    work_finish_time_baseline: Optional[str] = "22:00"
    intervals_athlete_id: Optional[str] = None
    onboarding_complete: Optional[int] = 0
    timezone: Optional[str] = "Europe/Amsterdam"
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    years_experience: Optional[int] = None
    training_background: Optional[str] = None
    what_worked: Optional[str] = None
    what_didnt_work: Optional[str] = None
    current_goals: Optional[str] = None
    weekly_hours_target_low: Optional[float] = None
    weekly_hours_target_high: Optional[float] = None
    work_hours_baseline: Optional[float] = None
    work_finish_time_baseline: Optional[str] = None
    intervals_athlete_id: Optional[str] = None
    onboarding_complete: Optional[int] = None
    timezone: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None


@router.get("/profile")
async def get_profile():
    """Get the athlete profile."""
    with get_db() as db:
        row = db.execute("SELECT * FROM athlete_profile WHERE id = 1").fetchone()
        if row is None:
            return None
        return dict_from_row(row)


@router.post("/profile")
async def create_profile(profile: ProfileCreate):
    """Create athlete profile (onboarding)."""
    with get_db() as db:
        # Check if profile already exists
        existing = db.execute("SELECT id FROM athlete_profile WHERE id = 1").fetchone()
        if existing is not None:
            raise HTTPException(status_code=400, detail="Profile already exists. Use PUT to update.")

        db.execute(
            """INSERT INTO athlete_profile
               (id, name, date_of_birth, gender, height_cm, weight_kg,
                years_experience, training_background, what_worked, what_didnt_work,
                current_goals, weekly_hours_target_low, weekly_hours_target_high,
                work_hours_baseline, work_finish_time_baseline,
                intervals_athlete_id, onboarding_complete, timezone,
                location_lat, location_lon)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile.name, profile.date_of_birth, profile.gender,
                profile.height_cm, profile.weight_kg, profile.years_experience,
                profile.training_background, profile.what_worked, profile.what_didnt_work,
                profile.current_goals, profile.weekly_hours_target_low,
                profile.weekly_hours_target_high, profile.work_hours_baseline,
                profile.work_finish_time_baseline, profile.intervals_athlete_id,
                profile.onboarding_complete, profile.timezone,
                profile.location_lat, profile.location_lon,
            ),
        )
        row = db.execute("SELECT * FROM athlete_profile WHERE id = 1").fetchone()
        return dict_from_row(row)


@router.put("/profile")
async def update_profile(profile: ProfileUpdate):
    """Update athlete profile."""
    with get_db() as db:
        existing = db.execute("SELECT * FROM athlete_profile WHERE id = 1").fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Profile not found. Use POST to create.")

        updates = {k: v for k, v in profile.model_dump().items() if v is not None}
        if not updates:
            return dict_from_row(existing)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values())
        db.execute(
            f"UPDATE athlete_profile SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = 1",
            values,
        )
        row = db.execute("SELECT * FROM athlete_profile WHERE id = 1").fetchone()
        return dict_from_row(row)


@router.get("/onboarding-status")
async def onboarding_status():
    """Check if onboarding is complete."""
    with get_db() as db:
        row = db.execute(
            "SELECT onboarding_complete FROM athlete_profile WHERE id = 1"
        ).fetchone()
        if row is None:
            return {"complete": False, "profile_exists": False}
        return {"complete": bool(row["onboarding_complete"]), "profile_exists": True}
