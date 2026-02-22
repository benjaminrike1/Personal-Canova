import json
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.core.database import get_db, dict_from_row, dicts_from_rows

router = APIRouter()


def _parse_json_field(value):
    """Safely parse a JSON string field, returning None if invalid."""
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _weeks_ago(weeks: int) -> str:
    """Return ISO date string for N weeks ago."""
    return (date.today() - timedelta(weeks=weeks)).isoformat()


@router.get("/aerobic-efficiency")
async def aerobic_efficiency(sport: str = "Run", weeks: int = 12):
    """HR vs pace/power over time for aerobic efficiency curve.

    Returns activities with avg_hr and avg_pace (or avg_power for cycling)
    to chart aerobic efficiency trends.
    """
    cutoff = _weeks_ago(weeks)
    with get_db() as db:
        rows = db.execute(
            """SELECT id, name, start_time, sport, duration_s, distance_m,
                      avg_hr, avg_pace, gap, avg_power, avg_speed,
                      efficiency_factor, decoupling, training_load,
                      avg_weather_temp_c, avg_temp_c
               FROM activities
               WHERE sport = ? AND start_time >= ? AND avg_hr IS NOT NULL
               ORDER BY start_time ASC""",
            (sport, cutoff),
        ).fetchall()
        results = dicts_from_rows(rows)
        # Calculate efficiency metric per activity
        for r in results:
            if sport == "Run" and r.get("avg_pace") and r.get("avg_hr"):
                # Aerobic efficiency = pace per beat (lower is better for running)
                # avg_pace is s/m, convert to min/km: avg_pace * 1000 / 60
                pace_min_km = (r["avg_pace"] * 1000) / 60
                r["pace_min_km"] = round(pace_min_km, 2)
                r["efficiency"] = round(pace_min_km / r["avg_hr"] * 100, 3)
            elif sport == "Ride" and r.get("avg_power") and r.get("avg_hr"):
                # Aerobic efficiency = power per beat (higher is better for cycling)
                r["efficiency"] = round(r["avg_power"] / r["avg_hr"], 3)
        return results


@router.get("/training-load")
async def training_load(weeks: int = 12):
    """CTL, ATL, TSB curves from wellness table.

    Returns daily fitness (CTL), fatigue (ATL), and form (TSB = CTL - ATL).
    """
    cutoff = _weeks_ago(weeks)
    with get_db() as db:
        rows = db.execute(
            """SELECT date, ctl, atl, ramp_rate,
                      weight_kg, resting_hr, hrv, sleep_score, readiness
               FROM wellness
               WHERE date >= ?
               ORDER BY date ASC""",
            (cutoff,),
        ).fetchall()
        results = dicts_from_rows(rows)
        for r in results:
            ctl = r.get("ctl") or 0
            atl = r.get("atl") or 0
            r["tsb"] = round(ctl - atl, 1)
        return results


@router.get("/key-sessions")
async def key_session_progression(session_type: str | None = None, weeks: int = 12):
    """Key session performance trends over time.

    Joins key_sessions with activities to show progression of specific
    session types (e.g. threshold runs, long runs, FTP tests).
    """
    cutoff = _weeks_ago(weeks)
    with get_db() as db:
        if session_type:
            rows = db.execute(
                """SELECT ks.id AS key_session_id, ks.session_type, ks.tagged_by,
                          ks.performance_notes,
                          a.id AS activity_id, a.name, a.start_time, a.sport,
                          a.duration_s, a.distance_m, a.avg_hr, a.max_hr,
                          a.avg_pace, a.gap, a.avg_power, a.np,
                          a.training_load, a.intensity, a.efficiency_factor,
                          a.decoupling, a.rpe, a.feel,
                          a.interval_summary
                   FROM key_sessions ks
                   JOIN activities a ON ks.activity_id = a.id
                   WHERE ks.session_type = ? AND a.start_time >= ?
                   ORDER BY a.start_time ASC""",
                (session_type, cutoff),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT ks.id AS key_session_id, ks.session_type, ks.tagged_by,
                          ks.performance_notes,
                          a.id AS activity_id, a.name, a.start_time, a.sport,
                          a.duration_s, a.distance_m, a.avg_hr, a.max_hr,
                          a.avg_pace, a.gap, a.avg_power, a.np,
                          a.training_load, a.intensity, a.efficiency_factor,
                          a.decoupling, a.rpe, a.feel,
                          a.interval_summary
                   FROM key_sessions ks
                   JOIN activities a ON ks.activity_id = a.id
                   WHERE a.start_time >= ?
                   ORDER BY a.start_time ASC""",
                (cutoff,),
            ).fetchall()

        results = dicts_from_rows(rows)
        for r in results:
            r["interval_summary"] = _parse_json_field(r.get("interval_summary"))
            # Add pace in min/km for running sessions
            if r.get("avg_pace"):
                r["pace_min_km"] = round((r["avg_pace"] * 1000) / 60, 2)
        return results


@router.get("/zone-distribution")
async def zone_distribution(sport: str = "Run", weeks: int = 4):
    """Weekly time-in-zone distribution from activities.

    Parses hr_zone_times, pace_zone_times, and power_zone_times JSON fields
    and aggregates per week.
    """
    cutoff = _weeks_ago(weeks)
    with get_db() as db:
        rows = db.execute(
            """SELECT id, start_time, sport, duration_s,
                      hr_zone_times, pace_zone_times, power_zone_times,
                      hr_zones, pace_zones, power_zones
               FROM activities
               WHERE sport = ? AND start_time >= ?
               ORDER BY start_time ASC""",
            (sport, cutoff),
        ).fetchall()

        # Aggregate by week
        weekly = {}
        for row in rows:
            r = dict(row)
            # Determine week_start (Monday)
            try:
                activity_date = datetime.fromisoformat(r["start_time"]).date()
            except (ValueError, TypeError):
                continue
            week_start = (activity_date - timedelta(days=activity_date.weekday())).isoformat()

            if week_start not in weekly:
                weekly[week_start] = {
                    "week_start": week_start,
                    "hr_zones": [],
                    "pace_zones": [],
                    "power_zones": [],
                    "total_duration_s": 0,
                    "activity_count": 0,
                }

            weekly[week_start]["total_duration_s"] += r.get("duration_s") or 0
            weekly[week_start]["activity_count"] += 1

            # Accumulate zone times
            hr_times = _parse_json_field(r.get("hr_zone_times"))
            pace_times = _parse_json_field(r.get("pace_zone_times"))
            power_times = _parse_json_field(r.get("power_zone_times"))

            if hr_times and isinstance(hr_times, list):
                existing = weekly[week_start]["hr_zones"]
                if not existing:
                    weekly[week_start]["hr_zones"] = list(hr_times)
                else:
                    for i, val in enumerate(hr_times):
                        if i < len(existing):
                            existing[i] = (existing[i] or 0) + (val or 0)
                        else:
                            existing.append(val or 0)

            if pace_times and isinstance(pace_times, list):
                existing = weekly[week_start]["pace_zones"]
                if not existing:
                    weekly[week_start]["pace_zones"] = list(pace_times)
                else:
                    for i, val in enumerate(pace_times):
                        if i < len(existing):
                            existing[i] = (existing[i] or 0) + (val or 0)
                        else:
                            existing.append(val or 0)

            if power_times and isinstance(power_times, list):
                existing = weekly[week_start]["power_zones"]
                if not existing:
                    weekly[week_start]["power_zones"] = list(power_times)
                else:
                    for i, val in enumerate(power_times):
                        if i < len(existing):
                            existing[i] = (existing[i] or 0) + (val or 0)
                        else:
                            existing.append(val or 0)

        # Store zone boundaries from the latest activity that has them
        zone_boundaries = {"hr_zones": None, "pace_zones": None, "power_zones": None}
        for row in reversed(rows):
            r = dict(row)
            if not zone_boundaries["hr_zones"] and r.get("hr_zones"):
                zone_boundaries["hr_zones"] = _parse_json_field(r["hr_zones"])
            if not zone_boundaries["pace_zones"] and r.get("pace_zones"):
                zone_boundaries["pace_zones"] = _parse_json_field(r["pace_zones"])
            if not zone_boundaries["power_zones"] and r.get("power_zones"):
                zone_boundaries["power_zones"] = _parse_json_field(r["power_zones"])
            if all(zone_boundaries.values()):
                break

        return {
            "weeks": sorted(weekly.values(), key=lambda w: w["week_start"]),
            "zone_boundaries": zone_boundaries,
        }


@router.get("/planned-vs-actual")
async def planned_vs_actual(weeks: int = 12):
    """Planned vs actual training hours per week from the v_planned_vs_actual view."""
    cutoff = _weeks_ago(weeks)
    with get_db() as db:
        rows = db.execute(
            """SELECT * FROM v_planned_vs_actual
               WHERE week_start >= ?
               ORDER BY week_start ASC""",
            (cutoff,),
        ).fetchall()
        return dicts_from_rows(rows)


@router.get("/session-compare")
async def session_compare(activity_ids: str = ""):
    """Overlay data for selected sessions.

    Pass activity IDs as comma-separated string, e.g. ?activity_ids=1,2,3
    Returns full activity details including parsed JSON fields for comparison.
    """
    if not activity_ids:
        raise HTTPException(status_code=400, detail="Provide activity_ids as comma-separated values")

    try:
        ids = [int(x.strip()) for x in activity_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="activity_ids must be comma-separated integers")

    if not ids:
        raise HTTPException(status_code=400, detail="No valid activity IDs provided")

    placeholders = ", ".join("?" for _ in ids)
    with get_db() as db:
        rows = db.execute(
            f"SELECT * FROM activities WHERE id IN ({placeholders})",
            ids,
        ).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No activities found for the given IDs")

        results = dicts_from_rows(rows)
        for r in results:
            # Parse all JSON fields for comparison
            r["hr_zone_times"] = _parse_json_field(r.get("hr_zone_times"))
            r["pace_zone_times"] = _parse_json_field(r.get("pace_zone_times"))
            r["power_zone_times"] = _parse_json_field(r.get("power_zone_times"))
            r["hr_zones"] = _parse_json_field(r.get("hr_zones"))
            r["pace_zones"] = _parse_json_field(r.get("pace_zones"))
            r["power_zones"] = _parse_json_field(r.get("power_zones"))
            r["interval_summary"] = _parse_json_field(r.get("interval_summary"))
            # Add pace in min/km for running activities
            if r.get("avg_pace"):
                r["pace_min_km"] = round((r["avg_pace"] * 1000) / 60, 2)
        return results
