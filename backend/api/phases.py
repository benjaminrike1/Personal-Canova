import sqlite3
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.database import get_db, dict_from_row, dicts_from_rows

router = APIRouter()

SportFocus = Literal["run", "bike", "triathlon", "other"]
PhaseType = Literal["base", "build", "peak", "taper", "recovery"]


class PhaseCreate(BaseModel):
    name: Optional[str] = None
    start_date: str
    end_date: Optional[str] = None
    primary_sport_focus: SportFocus
    phase_type: PhaseType
    target_race_id: Optional[int] = None
    notes: Optional[str] = None


class PhaseUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    primary_sport_focus: Optional[SportFocus] = None
    phase_type: Optional[PhaseType] = None
    target_race_id: Optional[int] = None
    notes: Optional[str] = None


@router.get("/")
async def list_phases():
    """List all training phases."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM training_phases ORDER BY start_date DESC"
        ).fetchall()
        return dicts_from_rows(rows)


@router.get("/current")
async def current_phase():
    """Get the currently active training phase.

    Active means start_date <= today and (end_date IS NULL or end_date >= today).
    """
    today = date.today().isoformat()
    with get_db() as db:
        row = db.execute(
            """SELECT * FROM training_phases
               WHERE start_date <= ?
                 AND (end_date IS NULL OR end_date >= ?)
               ORDER BY start_date DESC
               LIMIT 1""",
            (today, today),
        ).fetchone()
        if row is None:
            return None
        return dict_from_row(row)


@router.post("/")
async def create_phase(phase: PhaseCreate):
    """Create a new training phase."""
    with get_db() as db:
        try:
            cursor = db.execute(
                """INSERT INTO training_phases
                   (name, start_date, end_date, primary_sport_focus, phase_type,
                    target_race_id, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    phase.name, phase.start_date, phase.end_date,
                    phase.primary_sport_focus, phase.phase_type,
                    phase.target_race_id, phase.notes,
                ),
            )
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=400, detail=str(e))
        row = db.execute(
            "SELECT * FROM training_phases WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict_from_row(row)


@router.put("/{phase_id}")
async def update_phase(phase_id: int, phase: PhaseUpdate):
    """Update a training phase."""
    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM training_phases WHERE id = ?", (phase_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Training phase not found")

        updates = {k: v for k, v in phase.model_dump().items() if v is not None}
        if not updates:
            return dict_from_row(existing)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [phase_id]
        db.execute(
            f"UPDATE training_phases SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            values,
        )
        row = db.execute(
            "SELECT * FROM training_phases WHERE id = ?", (phase_id,)
        ).fetchone()
        return dict_from_row(row)


@router.delete("/{phase_id}")
async def delete_phase(phase_id: int):
    """Delete a training phase."""
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM training_phases WHERE id = ?", (phase_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Training phase not found")
        db.execute("DELETE FROM training_phases WHERE id = ?", (phase_id,))
        return {"deleted": True}
