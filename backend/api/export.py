import csv
import io
from datetime import date, datetime, timedelta

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.core.database import get_db, dicts_from_rows

router = APIRouter()


def _rows_to_csv(rows: list[dict]) -> str:
    """Convert a list of dicts to a CSV string."""
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _csv_response(csv_content: str, filename: str) -> StreamingResponse:
    """Create a StreamingResponse for CSV download."""
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/checkins")
async def export_checkins():
    """Export all check-ins as CSV."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM checkins ORDER BY date DESC, type ASC"
        ).fetchall()
        data = dicts_from_rows(rows)

    if not data:
        return _csv_response("", "checkins.csv")

    csv_content = _rows_to_csv(data)
    return _csv_response(csv_content, "checkins.csv")


@router.get("/activities")
async def export_activities():
    """Export all activities as CSV."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM activities ORDER BY start_time DESC"
        ).fetchall()
        data = dicts_from_rows(rows)

    if not data:
        return _csv_response("", "activities.csv")

    csv_content = _rows_to_csv(data)
    return _csv_response(csv_content, "activities.csv")


@router.get("/notebook")
async def export_notebook():
    """Export coach notebook entries as CSV."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM coach_notebook ORDER BY created_at DESC"
        ).fetchall()
        data = dicts_from_rows(rows)

    if not data:
        return _csv_response("", "notebook.csv")

    csv_content = _rows_to_csv(data)
    return _csv_response(csv_content, "notebook.csv")
