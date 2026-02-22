from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.database import get_db, dict_from_row, dicts_from_rows

router = APIRouter()


class RaceCreate(BaseModel):
    name: str
    date: str
    distance_m: Optional[float] = None
    distance_label: Optional[str] = None
    discipline: str = "running"
    priority: str = "B"
    goal_time_s: Optional[float] = None
    goal_notes: Optional[str] = None
    result_time_s: Optional[float] = None
    result_notes: Optional[str] = None
    notes: Optional[str] = None
    status: str = "upcoming"


class RaceUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[str] = None
    distance_m: Optional[float] = None
    distance_label: Optional[str] = None
    discipline: Optional[str] = None
    priority: Optional[str] = None
    goal_time_s: Optional[float] = None
    goal_notes: Optional[str] = None
    result_time_s: Optional[float] = None
    result_notes: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


@router.get("/")
async def list_races():
    """List all races, upcoming first."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM races ORDER BY date ASC"
        ).fetchall()
        return dicts_from_rows(rows)


@router.get("/next")
async def next_a_race():
    """Get next upcoming A-race with weeks-to-race."""
    today = date.today().isoformat()
    with get_db() as db:
        row = db.execute(
            """SELECT * FROM races
               WHERE priority = 'A' AND status = 'upcoming' AND date >= ?
               ORDER BY date ASC LIMIT 1""",
            (today,),
        ).fetchone()
        if row is None:
            return None
        result = dict_from_row(row)
        race_date = date.fromisoformat(result["date"])
        days_until = (race_date - date.today()).days
        result["weeks_until_race"] = round(days_until / 7, 1)
        result["days_until_race"] = days_until
        return result


@router.post("/")
async def create_race(race: RaceCreate):
    """Add a race to the calendar."""
    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO races (name, date, distance_m, distance_label, discipline,
                                  priority, goal_time_s, goal_notes, result_time_s,
                                  result_notes, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                race.name, race.date, race.distance_m, race.distance_label,
                race.discipline, race.priority, race.goal_time_s, race.goal_notes,
                race.result_time_s, race.result_notes, race.notes, race.status,
            ),
        )
        row = db.execute("SELECT * FROM races WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict_from_row(row)


@router.put("/{race_id}")
async def update_race(race_id: int, race: RaceUpdate):
    """Update a race."""
    with get_db() as db:
        existing = db.execute("SELECT * FROM races WHERE id = ?", (race_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Race not found")

        updates = {k: v for k, v in race.model_dump().items() if v is not None}
        if not updates:
            return dict_from_row(existing)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [race_id]
        db.execute(
            f"UPDATE races SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            values,
        )
        row = db.execute("SELECT * FROM races WHERE id = ?", (race_id,)).fetchone()
        return dict_from_row(row)


@router.delete("/{race_id}")
async def delete_race(race_id: int):
    """Remove a race from the calendar."""
    with get_db() as db:
        existing = db.execute("SELECT id FROM races WHERE id = ?", (race_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Race not found")
        db.execute("DELETE FROM races WHERE id = ?", (race_id,))
        return {"deleted": True}
