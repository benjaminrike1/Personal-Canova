from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.database import get_db, dict_from_row, dicts_from_rows

router = APIRouter()


class NotebookEntryUpdate(BaseModel):
    category: Optional[str] = None
    content: Optional[str] = None
    evidence: Optional[str] = None
    confidence: Optional[str] = None
    active: Optional[int] = None
    source_type: Optional[str] = None
    source_conversation_id: Optional[int] = None
    source_checkin_id: Optional[int] = None
    source_activity_id: Optional[int] = None


@router.get("/")
async def list_entries(active_only: bool = True):
    """List coach notebook entries, optionally only active ones."""
    with get_db() as db:
        if active_only:
            rows = db.execute(
                "SELECT * FROM coach_notebook WHERE active = 1 ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM coach_notebook ORDER BY created_at DESC"
            ).fetchall()
        return dicts_from_rows(rows)


@router.get("/{entry_id}")
async def get_entry(entry_id: int):
    """Get a single notebook entry."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM coach_notebook WHERE id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Notebook entry not found")
        return dict_from_row(row)


@router.put("/{entry_id}")
async def update_entry(entry_id: int, entry: NotebookEntryUpdate):
    """Update a notebook entry (toggle active, edit content)."""
    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM coach_notebook WHERE id = ?", (entry_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Notebook entry not found")

        updates = {k: v for k, v in entry.model_dump().items() if v is not None}
        if not updates:
            return dict_from_row(existing)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [entry_id]
        db.execute(
            f"UPDATE coach_notebook SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            values,
        )
        row = db.execute(
            "SELECT * FROM coach_notebook WHERE id = ?", (entry_id,)
        ).fetchone()
        return dict_from_row(row)
