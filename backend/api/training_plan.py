import json
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.database import get_db, dict_from_row, dicts_from_rows

router = APIRouter()


class PlanEntryCreate(BaseModel):
    week_start: str
    day_of_week: int  # 0=Monday
    session_order: int = 1
    session_type: str
    target_duration_s: Optional[float] = None
    target_intensity: Optional[str] = None
    key_objective: Optional[str] = None
    is_key_session: int = 0
    is_rest_day: int = 0


class PlanEntryUpdate(BaseModel):
    week_start: Optional[str] = None
    day_of_week: Optional[int] = None
    session_order: Optional[int] = None
    session_type: Optional[str] = None
    target_duration_s: Optional[float] = None
    target_intensity: Optional[str] = None
    key_objective: Optional[str] = None
    is_key_session: Optional[int] = None
    is_rest_day: Optional[int] = None
    completed: Optional[int] = None
    actual_activity_id: Optional[int] = None
    deviation_notes: Optional[str] = None
    change_reason: Optional[str] = None
    changed_by: Optional[str] = "coach"


def _get_monday(d: date) -> date:
    """Return the Monday (ISO weekday 1) of the week containing d."""
    return d - timedelta(days=d.weekday())


@router.get("/current")
async def current_week():
    """Get current week's training plan (Monday-Sunday)."""
    monday = _get_monday(date.today()).isoformat()
    with get_db() as db:
        rows = db.execute(
            """SELECT * FROM training_plan
               WHERE week_start = ?
               ORDER BY day_of_week ASC, session_order ASC""",
            (monday,),
        ).fetchall()
        return dicts_from_rows(rows)


@router.get("/week/{week_start}")
async def get_week(week_start: str):
    """Get a specific week's plan by Monday date."""
    with get_db() as db:
        rows = db.execute(
            """SELECT * FROM training_plan
               WHERE week_start = ?
               ORDER BY day_of_week ASC, session_order ASC""",
            (week_start,),
        ).fetchall()
        return dicts_from_rows(rows)


@router.post("/")
async def create_plan_entry(entry: PlanEntryCreate):
    """Add a session to the training plan."""
    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO training_plan
               (week_start, day_of_week, session_order, session_type,
                target_duration_s, target_intensity, key_objective,
                is_key_session, is_rest_day)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.week_start, entry.day_of_week, entry.session_order,
                entry.session_type, entry.target_duration_s, entry.target_intensity,
                entry.key_objective, entry.is_key_session, entry.is_rest_day,
            ),
        )
        row = db.execute(
            "SELECT * FROM training_plan WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict_from_row(row)


@router.put("/{entry_id}")
async def update_plan_entry(entry_id: int, entry: PlanEntryUpdate):
    """Update a planned session. Creates a version entry before applying changes."""
    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM training_plan WHERE id = ?", (entry_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Plan entry not found")

        existing_dict = dict_from_row(existing)

        # Separate change_reason and changed_by from the DB update fields
        change_reason = entry.change_reason
        changed_by = entry.changed_by or "coach"
        updates = {
            k: v for k, v in entry.model_dump().items()
            if v is not None and k not in ("change_reason", "changed_by")
        }

        if not updates:
            return existing_dict

        # Create version snapshot before updating
        current_version = existing_dict["version"]
        snapshot = {
            k: existing_dict[k] for k in [
                "week_start", "day_of_week", "session_order", "session_type",
                "target_duration_s", "target_intensity", "key_objective",
                "is_key_session", "is_rest_day", "completed",
                "actual_activity_id", "deviation_notes",
            ]
        }
        db.execute(
            """INSERT INTO training_plan_versions
               (plan_entry_id, version, previous_data, change_reason, changed_by)
               VALUES (?, ?, ?, ?, ?)""",
            (entry_id, current_version, json.dumps(snapshot), change_reason, changed_by),
        )

        # Bump version and apply updates
        updates["version"] = current_version + 1
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [entry_id]
        db.execute(
            f"UPDATE training_plan SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            values,
        )

        row = db.execute(
            "SELECT * FROM training_plan WHERE id = ?", (entry_id,)
        ).fetchone()
        return dict_from_row(row)


@router.delete("/{entry_id}")
async def delete_plan_entry(entry_id: int):
    """Remove a planned session."""
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM training_plan WHERE id = ?", (entry_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Plan entry not found")
        db.execute("DELETE FROM training_plan WHERE id = ?", (entry_id,))
        return {"deleted": True}


@router.get("/{entry_id}/versions")
async def plan_entry_versions(entry_id: int):
    """Get version history for a plan entry."""
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM training_plan WHERE id = ?", (entry_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Plan entry not found")

        rows = db.execute(
            """SELECT * FROM training_plan_versions
               WHERE plan_entry_id = ?
               ORDER BY version ASC""",
            (entry_id,),
        ).fetchall()
        results = dicts_from_rows(rows)
        # Parse the JSON previous_data field
        for r in results:
            if r.get("previous_data"):
                r["previous_data"] = json.loads(r["previous_data"])
        return results
