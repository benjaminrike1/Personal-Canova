from datetime import date, datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.database import get_db, dict_from_row, dicts_from_rows

router = APIRouter()


class SessionRPE(BaseModel):
    activity_id: Optional[int] = None
    session_type: Optional[str] = None
    rpe: Optional[int] = None
    notes: Optional[str] = None


class CheckinCreate(BaseModel):
    date: Optional[str] = None
    type: str  # morning, evening, weekend, weekly

    # Morning fields
    sleep_quality: Optional[int] = None
    hours_slept: Optional[float] = None
    work_finish_time: Optional[str] = None
    work_stress: Optional[int] = None
    energy_level: Optional[int] = None
    motivation: Optional[int] = None
    body_weight_kg: Optional[float] = None
    injury_update: Optional[str] = None

    # Evening fields
    did_planned: Optional[str] = None
    tomorrow_objective: Optional[str] = None
    improvement: Optional[str] = None
    alcohol: Optional[int] = None
    nutrition: Optional[str] = None

    # Weekly fields
    hours_worked: Optional[float] = None
    three_improvements: Optional[str] = None
    weekly_reflection: Optional[str] = None

    # Session RPEs
    session_rpes: Optional[List[SessionRPE]] = None


class CheckinUpdate(BaseModel):
    sleep_quality: Optional[int] = None
    hours_slept: Optional[float] = None
    work_finish_time: Optional[str] = None
    work_stress: Optional[int] = None
    energy_level: Optional[int] = None
    motivation: Optional[int] = None
    body_weight_kg: Optional[float] = None
    injury_update: Optional[str] = None
    did_planned: Optional[str] = None
    tomorrow_objective: Optional[str] = None
    improvement: Optional[str] = None
    alcohol: Optional[int] = None
    nutrition: Optional[str] = None
    hours_worked: Optional[float] = None
    three_improvements: Optional[str] = None
    weekly_reflection: Optional[str] = None
    session_rpes: Optional[List[SessionRPE]] = None


MORNING_FIELDS = [
    "sleep_quality", "hours_slept", "work_finish_time", "work_stress",
    "energy_level", "motivation", "body_weight_kg", "injury_update",
]
EVENING_FIELDS = [
    "did_planned", "tomorrow_objective", "improvement", "alcohol", "nutrition",
]
WEEKEND_FIELDS = [
    "sleep_quality", "hours_slept", "energy_level",
    "improvement", "tomorrow_objective", "alcohol", "nutrition",
]
WEEKLY_FIELDS = [
    "hours_worked", "three_improvements", "weekly_reflection",
]

TYPE_FIELDS = {
    "morning": MORNING_FIELDS,
    "evening": EVENING_FIELDS,
    "weekend": WEEKEND_FIELDS,
    "weekly": WEEKLY_FIELDS,
}


def _calc_completion_pct(checkin_type: str, data: dict) -> float:
    """Calculate completion percentage based on filled fields for the checkin type."""
    fields = TYPE_FIELDS.get(checkin_type, [])
    if not fields:
        return 0.0
    filled = sum(1 for f in fields if data.get(f) is not None and data.get(f) != "")
    return round((filled / len(fields)) * 100, 1)


@router.get("/")
async def list_checkins(days: int = 14):
    """List check-ins for the last N days."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM checkins WHERE date >= ? ORDER BY date DESC, type ASC",
            (cutoff,),
        ).fetchall()
        results = dicts_from_rows(rows)
        # Attach session RPEs
        for r in results:
            rpe_rows = db.execute(
                "SELECT * FROM session_checkins WHERE checkin_id = ?", (r["id"],)
            ).fetchall()
            r["session_rpes"] = dicts_from_rows(rpe_rows)
        return results


@router.get("/today")
async def today_status():
    """Get today's check-in status for dashboard."""
    today = date.today().isoformat()
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM checkins WHERE date = ?", (today,)
        ).fetchall()
        status = {"morning": None, "evening": None, "weekend": None, "weekly": None}
        for row in rows:
            r = dict_from_row(row)
            rpe_rows = db.execute(
                "SELECT * FROM session_checkins WHERE checkin_id = ?", (r["id"],)
            ).fetchall()
            r["session_rpes"] = dicts_from_rows(rpe_rows)
            status[r["type"]] = r
        return status


@router.post("/")
async def create_checkin(checkin: CheckinCreate):
    """Submit a check-in (morning/evening/weekend/weekly)."""
    checkin_date = checkin.date or date.today().isoformat()
    data = checkin.model_dump()
    data["date"] = checkin_date

    completion_pct = _calc_completion_pct(checkin.type, data)
    completed = 1 if completion_pct == 100.0 else 0

    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO checkins (date, type, completed, completion_pct,
                sleep_quality, hours_slept, work_finish_time, work_stress,
                energy_level, motivation, body_weight_kg, injury_update,
                did_planned, tomorrow_objective, improvement, alcohol, nutrition,
                hours_worked, three_improvements, weekly_reflection)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                checkin_date, checkin.type, completed, completion_pct,
                checkin.sleep_quality, checkin.hours_slept, checkin.work_finish_time,
                checkin.work_stress, checkin.energy_level, checkin.motivation,
                checkin.body_weight_kg, checkin.injury_update,
                checkin.did_planned, checkin.tomorrow_objective, checkin.improvement,
                checkin.alcohol, checkin.nutrition,
                checkin.hours_worked, checkin.three_improvements, checkin.weekly_reflection,
            ),
        )
        checkin_id = cursor.lastrowid

        # Insert session RPEs if provided
        if checkin.session_rpes:
            for sr in checkin.session_rpes:
                db.execute(
                    """INSERT INTO session_checkins (checkin_id, activity_id, session_type, rpe, notes)
                       VALUES (?, ?, ?, ?, ?)""",
                    (checkin_id, sr.activity_id, sr.session_type, sr.rpe, sr.notes),
                )

        # Auto-insert work_log from morning checkins
        if checkin.type == "morning" and (checkin.work_finish_time or checkin.work_stress):
            db.execute(
                """INSERT OR REPLACE INTO work_log (date, finish_time, stress_level, source_checkin_id)
                   VALUES (?, ?, ?, ?)""",
                (checkin_date, checkin.work_finish_time, checkin.work_stress, checkin_id),
            )

        row = db.execute("SELECT * FROM checkins WHERE id = ?", (checkin_id,)).fetchone()
        result = dict_from_row(row)
        rpe_rows = db.execute(
            "SELECT * FROM session_checkins WHERE checkin_id = ?", (checkin_id,)
        ).fetchall()
        result["session_rpes"] = dicts_from_rows(rpe_rows)
        return result


@router.put("/{checkin_id}")
async def update_checkin(checkin_id: int, checkin: CheckinUpdate):
    """Update a partial check-in."""
    with get_db() as db:
        existing = db.execute("SELECT * FROM checkins WHERE id = ?", (checkin_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Check-in not found")

        existing_dict = dict_from_row(existing)
        updates = {k: v for k, v in checkin.model_dump().items()
                   if v is not None and k != "session_rpes"}

        if updates:
            # Merge with existing to recalculate completion
            merged = {**existing_dict, **updates}
            completion_pct = _calc_completion_pct(existing_dict["type"], merged)
            completed = 1 if completion_pct == 100.0 else 0
            updates["completion_pct"] = completion_pct
            updates["completed"] = completed

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [checkin_id]
            db.execute(f"UPDATE checkins SET {set_clause} WHERE id = ?", values)

        # Update session RPEs if provided
        if checkin.session_rpes is not None:
            db.execute("DELETE FROM session_checkins WHERE checkin_id = ?", (checkin_id,))
            for sr in checkin.session_rpes:
                db.execute(
                    """INSERT INTO session_checkins (checkin_id, activity_id, session_type, rpe, notes)
                       VALUES (?, ?, ?, ?, ?)""",
                    (checkin_id, sr.activity_id, sr.session_type, sr.rpe, sr.notes),
                )

        row = db.execute("SELECT * FROM checkins WHERE id = ?", (checkin_id,)).fetchone()
        result = dict_from_row(row)
        rpe_rows = db.execute(
            "SELECT * FROM session_checkins WHERE checkin_id = ?", (checkin_id,)
        ).fetchall()
        result["session_rpes"] = dicts_from_rows(rpe_rows)
        return result
