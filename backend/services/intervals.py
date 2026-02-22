"""Intervals.icu API client — activities, wellness, athlete profile, streams."""

import base64
import json
import logging
from datetime import datetime, timedelta

import httpx

from backend.core.config import INTERVALS_ATHLETE_ID, INTERVALS_API_KEY, INTERVALS_BASE_URL
from backend.core.database import get_db, dict_from_row, dicts_from_rows

log = logging.getLogger(__name__)


def _json_or_none(val) -> str | None:
    """Serialize a value to JSON string, or return None."""
    if val is None:
        return None
    return json.dumps(val)


class IntervalsClient:
    """Client for the Intervals.icu REST API."""

    def __init__(
        self,
        athlete_id: str = INTERVALS_ATHLETE_ID,
        api_key: str = INTERVALS_API_KEY,
    ):
        self.athlete_id = athlete_id
        self.api_key = api_key
        self._auth = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()

    def _headers(self) -> dict:
        return {"Authorization": f"Basic {self._auth}"}

    def _url(self, path: str) -> str:
        return f"{INTERVALS_BASE_URL}{path}"

    # --- Raw API calls ---

    async def get_activities(self, oldest: str, newest: str) -> list[dict]:
        """Fetch activities for a date range (YYYY-MM-DD)."""
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                self._url(f"/athlete/{self.athlete_id}/activities"),
                params={"oldest": oldest, "newest": newest},
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    async def get_wellness(self, oldest: str, newest: str) -> list[dict]:
        """Fetch wellness records for a date range."""
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                self._url(f"/athlete/{self.athlete_id}/wellness"),
                params={"oldest": oldest, "newest": newest},
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    async def get_athlete(self) -> dict:
        """Fetch athlete profile with sport settings."""
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                self._url(f"/athlete/{self.athlete_id}"),
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    async def get_activity_streams(
        self,
        activity_id: str,
        types: str = "time,heartrate,watts,cadence,velocity_smooth,altitude,latlng",
    ) -> dict:
        """Fetch data streams for an activity."""
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                self._url(f"/activity/{activity_id}/streams"),
                params={"types": types},
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    async def get_power_curve(self, activity_id: str) -> list[dict]:
        """Fetch power curve for an activity."""
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                self._url(f"/activity/{activity_id}/power-curve"),
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    # --- Sync to database ---

    async def sync_activities(self, days: int = 30) -> int:
        """Sync activities from Intervals.icu to local database.

        Returns the number of newly inserted/updated activities.
        """
        newest = datetime.now().strftime("%Y-%m-%d")
        oldest = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        raw = await self.get_activities(oldest, newest)
        count = 0

        with get_db() as db:
            for act in raw:
                act_id = act.get("id")
                if not act_id:
                    continue

                gear_name = None
                gear_raw = act.get("gear")
                if isinstance(gear_raw, dict):
                    gear_name = gear_raw.get("name")

                # Map Intervals.icu fields -> our DB columns
                db.execute(
                    """INSERT INTO activities (
                        intervals_id, name, sport, sub_type, description,
                        start_time, start_time_utc,
                        duration_s, elapsed_s, recording_s, distance_m,
                        avg_hr, max_hr, avg_speed, max_speed,
                        avg_pace, gap, avg_power, np, avg_cadence,
                        elevation_gain, elevation_loss, calories,
                        training_load, atl, ctl, ftp,
                        intensity, efficiency_factor, variability_index,
                        decoupling, trimp, polarization_index,
                        perceived_exertion, rpe, session_rpe, feel,
                        avg_temp_c, avg_weather_temp_c,
                        hr_zone_times, pace_zone_times, power_zone_times,
                        hr_zones, pace_zones, power_zones,
                        interval_summary,
                        is_indoor, is_race, gear_name,
                        threshold_pace, lthr, resting_hr, weight_kg,
                        compliance, source, strava_id
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?
                    ) ON CONFLICT(intervals_id) DO UPDATE SET
                        name=excluded.name,
                        training_load=excluded.training_load,
                        atl=excluded.atl,
                        ctl=excluded.ctl,
                        perceived_exertion=excluded.perceived_exertion,
                        rpe=excluded.rpe,
                        session_rpe=excluded.session_rpe,
                        feel=excluded.feel,
                        description=excluded.description,
                        compliance=excluded.compliance,
                        interval_summary=excluded.interval_summary
                    """,
                    (
                        act_id,
                        act.get("name"),
                        act.get("type") or "Other",
                        act.get("sub_type"),
                        act.get("description"),
                        act.get("start_date_local") or act.get("start_date") or "",
                        act.get("start_date"),
                        act.get("moving_time"),
                        act.get("elapsed_time"),
                        act.get("icu_recording_time"),
                        act.get("distance") or act.get("icu_distance"),
                        act.get("average_heartrate"),
                        act.get("max_heartrate"),
                        act.get("average_speed"),
                        act.get("max_speed"),
                        act.get("pace"),
                        act.get("gap"),
                        act.get("icu_average_watts"),
                        act.get("icu_weighted_avg_watts"),
                        act.get("average_cadence"),
                        act.get("total_elevation_gain"),
                        act.get("total_elevation_loss"),
                        act.get("calories"),
                        act.get("icu_training_load"),
                        act.get("icu_atl"),
                        act.get("icu_ctl"),
                        act.get("icu_ftp"),
                        act.get("icu_intensity"),
                        act.get("icu_efficiency_factor"),
                        act.get("icu_variability_index"),
                        act.get("decoupling"),
                        act.get("trimp"),
                        act.get("polarization_index"),
                        act.get("perceived_exertion"),
                        act.get("icu_rpe"),
                        act.get("session_rpe"),
                        act.get("feel"),
                        act.get("average_temp"),
                        act.get("average_weather_temp"),
                        _json_or_none(act.get("icu_hr_zone_times")),
                        _json_or_none(act.get("pace_zone_times")),
                        _json_or_none(act.get("icu_zone_times")),
                        _json_or_none(act.get("icu_hr_zones")),
                        _json_or_none(act.get("pace_zones")),
                        _json_or_none(act.get("icu_power_zones")),
                        _json_or_none(act.get("interval_summary")),
                        1 if act.get("trainer") else 0,
                        1 if act.get("race") else 0,
                        gear_name,
                        act.get("threshold_pace"),
                        act.get("lthr"),
                        act.get("icu_resting_hr"),
                        act.get("icu_weight"),
                        act.get("compliance"),
                        act.get("source"),
                        str(act["strava_id"]) if act.get("strava_id") else None,
                    ),
                )
                count += 1

        log.info(f"Synced {count} activities from Intervals.icu")
        return count

    async def sync_wellness(self, days: int = 30) -> int:
        """Sync wellness data from Intervals.icu to local database.

        Returns the number of newly inserted/updated records.
        """
        newest = datetime.now().strftime("%Y-%m-%d")
        oldest = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        raw = await self.get_wellness(oldest, newest)
        count = 0

        with get_db() as db:
            for w in raw:
                date = w.get("id")  # wellness ID is the date string
                if not date:
                    continue

                db.execute(
                    """INSERT INTO wellness (
                        date, ctl, atl, ramp_rate,
                        weight_kg, resting_hr, hrv, hrv_sdnn,
                        sleep_seconds, sleep_score, sleep_quality, avg_sleeping_hr,
                        soreness, fatigue, stress, mood, motivation,
                        spo2, readiness, vo2max, steps, respiration
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date) DO UPDATE SET
                        ctl=excluded.ctl,
                        atl=excluded.atl,
                        ramp_rate=excluded.ramp_rate,
                        weight_kg=excluded.weight_kg,
                        resting_hr=excluded.resting_hr,
                        hrv=excluded.hrv,
                        hrv_sdnn=excluded.hrv_sdnn,
                        sleep_seconds=excluded.sleep_seconds,
                        sleep_score=excluded.sleep_score,
                        sleep_quality=excluded.sleep_quality,
                        avg_sleeping_hr=excluded.avg_sleeping_hr,
                        soreness=excluded.soreness,
                        fatigue=excluded.fatigue,
                        stress=excluded.stress,
                        mood=excluded.mood,
                        motivation=excluded.motivation,
                        spo2=excluded.spo2,
                        readiness=excluded.readiness,
                        vo2max=excluded.vo2max,
                        steps=excluded.steps,
                        respiration=excluded.respiration
                    """,
                    (
                        date,
                        w.get("ctl"),
                        w.get("atl"),
                        w.get("rampRate"),
                        w.get("weight"),
                        w.get("restingHR"),
                        w.get("hrv"),
                        w.get("hrvSDNN"),
                        w.get("sleepSecs"),
                        w.get("sleepScore"),
                        w.get("sleepQuality"),
                        w.get("avgSleepingHR"),
                        w.get("soreness"),
                        w.get("fatigue"),
                        w.get("stress"),
                        w.get("mood"),
                        w.get("motivation"),
                        w.get("spO2"),
                        w.get("readiness"),
                        w.get("vo2max"),
                        w.get("steps"),
                        w.get("respiration"),
                    ),
                )
                count += 1

        log.info(f"Synced {count} wellness records from Intervals.icu")
        return count

    async def sync_all(self, days: int = 30) -> dict:
        """Sync both activities and wellness."""
        activities = await self.sync_activities(days)
        wellness = await self.sync_wellness(days)
        return {"activities": activities, "wellness": wellness}


# --- Convenience query functions ---


def get_recent_activities(
    days: int = 14, sport: str | None = None, limit: int = 50
) -> list[dict]:
    """Get recent activities from the local database."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
    with get_db() as db:
        if sport:
            rows = db.execute(
                """SELECT * FROM activities
                   WHERE start_time >= ? AND sport = ?
                   ORDER BY start_time DESC LIMIT ?""",
                (cutoff, sport, limit),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT * FROM activities
                   WHERE start_time >= ?
                   ORDER BY start_time DESC LIMIT ?""",
                (cutoff, limit),
            ).fetchall()
        return dicts_from_rows(rows)


def get_activity_by_id(activity_id: int) -> dict | None:
    """Get a single activity by local DB id."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM activities WHERE id = ?", (activity_id,)
        ).fetchone()
        return dict_from_row(row)


def get_recent_wellness(days: int = 14) -> list[dict]:
    """Get recent wellness records."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM wellness WHERE date >= ? ORDER BY date DESC",
            (cutoff,),
        ).fetchall()
        return dicts_from_rows(rows)


def get_fitness_summary() -> dict | None:
    """Get latest CTL/ATL/TSB from wellness."""
    with get_db() as db:
        row = db.execute(
            "SELECT ctl, atl, (ctl - atl) as tsb, ramp_rate FROM wellness ORDER BY date DESC LIMIT 1"
        ).fetchone()
        return dict_from_row(row)
