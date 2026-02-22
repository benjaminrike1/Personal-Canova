from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.database import get_db, dict_from_row, dicts_from_rows

router = APIRouter()


class InjuryCreate(BaseModel):
    body_part: str
    description: str
    onset_date: str
    severity: int
    status: str = "active"
    notes: Optional[str] = None


class InjuryUpdate(BaseModel):
    body_part: Optional[str] = None
    description: Optional[str] = None
    onset_date: Optional[str] = None
    severity: Optional[int] = None
    status: Optional[str] = None
    resolved_date: Optional[str] = None
    notes: Optional[str] = None


class InjuryUpdateEntry(BaseModel):
    date: Optional[str] = None
    severity: int
    notes: Optional[str] = None


@router.get("/")
async def list_injuries(status: str | None = None):
    """List injuries, optionally filtered by status."""
    with get_db() as db:
        if status:
            rows = db.execute(
                "SELECT * FROM injuries WHERE status = ? ORDER BY onset_date DESC",
                (status,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM injuries ORDER BY onset_date DESC"
            ).fetchall()
        return dicts_from_rows(rows)


@router.get("/active")
async def active_injuries():
    """Get currently active/monitoring injuries."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM injuries WHERE status IN ('active', 'monitoring') ORDER BY severity DESC"
        ).fetchall()
        return dicts_from_rows(rows)


@router.post("/")
async def create_injury(injury: InjuryCreate):
    """Log a new injury."""
    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO injuries (body_part, description, onset_date, severity, status, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                injury.body_part, injury.description, injury.onset_date,
                injury.severity, injury.status, injury.notes,
            ),
        )
        row = db.execute("SELECT * FROM injuries WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict_from_row(row)


@router.put("/{injury_id}")
async def update_injury(injury_id: int, injury: InjuryUpdate):
    """Update injury status or severity."""
    with get_db() as db:
        existing = db.execute("SELECT * FROM injuries WHERE id = ?", (injury_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Injury not found")

        updates = {k: v for k, v in injury.model_dump().items() if v is not None}
        if not updates:
            return dict_from_row(existing)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [injury_id]
        db.execute(
            f"UPDATE injuries SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            values,
        )
        row = db.execute("SELECT * FROM injuries WHERE id = ?", (injury_id,)).fetchone()
        return dict_from_row(row)


@router.post("/{injury_id}/update")
async def add_injury_update(injury_id: int, entry: InjuryUpdateEntry):
    """Add a daily severity update to an injury."""
    with get_db() as db:
        existing = db.execute("SELECT id FROM injuries WHERE id = ?", (injury_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Injury not found")

        update_date = entry.date or date.today().isoformat()
        cursor = db.execute(
            """INSERT INTO injury_updates (injury_id, date, severity, notes)
               VALUES (?, ?, ?, ?)""",
            (injury_id, update_date, entry.severity, entry.notes),
        )
        # Also update the injury's current severity
        db.execute(
            "UPDATE injuries SET severity = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            (entry.severity, injury_id),
        )
        row = db.execute("SELECT * FROM injury_updates WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict_from_row(row)


@router.get("/{injury_id}/history")
async def injury_history(injury_id: int):
    """Get severity history for an injury."""
    with get_db() as db:
        existing = db.execute("SELECT id FROM injuries WHERE id = ?", (injury_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Injury not found")

        rows = db.execute(
            "SELECT * FROM injury_updates WHERE injury_id = ? ORDER BY date ASC",
            (injury_id,),
        ).fetchall()
        return dicts_from_rows(rows)
