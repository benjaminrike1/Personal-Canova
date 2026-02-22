from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.database import get_db, dict_from_row, dicts_from_rows

router = APIRouter()


class RecordCreate(BaseModel):
    discipline: str
    event: str
    value: float
    value_unit: str
    date_achieved: Optional[str] = None
    source: Optional[str] = "manual"
    notes: Optional[str] = None
    activity_id: Optional[str] = None


class RecordUpdate(BaseModel):
    discipline: Optional[str] = None
    event: Optional[str] = None
    value: Optional[float] = None
    value_unit: Optional[str] = None
    date_achieved: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    activity_id: Optional[str] = None


@router.get("/")
async def list_records(discipline: str | None = None):
    """List personal records, optionally filtered by discipline."""
    with get_db() as db:
        if discipline:
            rows = db.execute(
                "SELECT * FROM personal_records WHERE discipline = ? ORDER BY event ASC, date_achieved DESC",
                (discipline,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM personal_records ORDER BY discipline ASC, event ASC, date_achieved DESC"
            ).fetchall()
        return dicts_from_rows(rows)


@router.post("/")
async def create_record(record: RecordCreate):
    """Add a personal record."""
    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO personal_records
               (discipline, event, value, value_unit, date_achieved, source, notes, activity_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.discipline, record.event, record.value, record.value_unit,
                record.date_achieved, record.source, record.notes, record.activity_id,
            ),
        )
        row = db.execute(
            "SELECT * FROM personal_records WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict_from_row(row)


@router.put("/{record_id}")
async def update_record(record_id: int, record: RecordUpdate):
    """Update a personal record."""
    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM personal_records WHERE id = ?", (record_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Personal record not found")

        updates = {k: v for k, v in record.model_dump().items() if v is not None}
        if not updates:
            return dict_from_row(existing)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [record_id]
        db.execute(
            f"UPDATE personal_records SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            values,
        )
        row = db.execute(
            "SELECT * FROM personal_records WHERE id = ?", (record_id,)
        ).fetchone()
        return dict_from_row(row)


@router.delete("/{record_id}")
async def delete_record(record_id: int):
    """Remove a personal record."""
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM personal_records WHERE id = ?", (record_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Personal record not found")
        db.execute("DELETE FROM personal_records WHERE id = ?", (record_id,))
        return {"deleted": True}
