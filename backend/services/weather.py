"""Open-Meteo weather client — activity weather + daily weather.

Uses the free Open-Meteo API (no API key required):
  - Archive API for historical hourly data (per-activity weather)
  - Forecast API for recent / current daily summaries
  - Historical API for older daily summaries

Docs: https://open-meteo.com/en/docs
"""

import logging
from datetime import datetime, timedelta, date as date_type

import httpx

from backend.core.config import OPEN_METEO_BASE_URL
from backend.core.database import get_db, dict_from_row, dicts_from_rows

log = logging.getLogger(__name__)

# Default location: Trondheim, Norway
DEFAULT_LAT = 63.43
DEFAULT_LON = 10.40

# ---------------------------------------------------------------------------
# WMO Weather Code -> human-readable description
# https://www.nodc.noaa.gov/archive/arc0021/0002199/1.1/data/0-data/HTML/WMO-CODE/WMO4677.HTM
# ---------------------------------------------------------------------------
WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def wmo_description(code: int | None) -> str:
    """Return a human-readable description for a WMO weather code."""
    if code is None:
        return "Unknown"
    return WMO_CODES.get(code, f"Unknown ({code})")


class WeatherClient:
    """Client for the Open-Meteo API (no key required)."""

    def __init__(self, base_url: str = OPEN_METEO_BASE_URL, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Activity weather (hourly historical data for a specific timestamp)
    # ------------------------------------------------------------------

    async def get_activity_weather(
        self, lat: float, lon: float, timestamp: str
    ) -> dict:
        """Get historical weather for an activity's location and time.

        Uses the Open-Meteo Archive API to fetch hourly data for the
        specific date, then picks the hour closest to the given timestamp.

        Args:
            lat: Latitude of the activity.
            lon: Longitude of the activity.
            timestamp: ISO-8601 timestamp (e.g. '2024-06-15T08:30:00').

        Returns:
            Dict with temperature_c, feels_like_c, humidity_pct,
            wind_speed_kmh, wind_gust_kmh, wind_direction,
            precipitation_mm, weather_code, description.
        """
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
        target_hour = dt.hour

        # Decide which API to use based on how old the data is
        days_ago = (datetime.now() - dt.replace(tzinfo=None)).days
        if days_ago > 5:
            # Use archive API for older data
            url = "https://archive-api.open-meteo.com/v1/archive"
        else:
            # Use forecast API for recent data (includes last ~5 days)
            url = f"{self.base_url}/forecast"

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": date_str,
            "end_date": date_str,
            "hourly": ",".join([
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "wind_speed_10m",
                "wind_gusts_10m",
                "wind_direction_10m",
                "precipitation",
                "weather_code",
            ]),
            "timezone": "auto",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        if not times:
            log.warning(
                "No hourly data returned for lat=%.2f lon=%.2f date=%s",
                lat, lon, date_str,
            )
            return {}

        # Find the index of the closest hour
        idx = min(target_hour, len(times) - 1)

        def _val(key: str, index: int):
            arr = hourly.get(key, [])
            if index < len(arr):
                return arr[index]
            return None

        weather_code = _val("weather_code", idx)
        result = {
            "latitude": lat,
            "longitude": lon,
            "timestamp": timestamp,
            "temperature_c": _val("temperature_2m", idx),
            "feels_like_c": _val("apparent_temperature", idx),
            "humidity_pct": _val("relative_humidity_2m", idx),
            "wind_speed_kmh": _val("wind_speed_10m", idx),
            "wind_gust_kmh": _val("wind_gusts_10m", idx),
            "wind_direction": _val("wind_direction_10m", idx),
            "precipitation_mm": _val("precipitation", idx),
            "weather_code": weather_code,
            "description": wmo_description(weather_code),
        }
        return result

    # ------------------------------------------------------------------
    # Daily weather summary
    # ------------------------------------------------------------------

    async def get_daily_weather(
        self, lat: float, lon: float, date: str
    ) -> dict:
        """Get a daily weather summary for a specific date and location.

        Args:
            lat: Latitude.
            lon: Longitude.
            date: ISO date string (YYYY-MM-DD).

        Returns:
            Dict matching the daily_weather table columns.
        """
        # Decide API based on date age
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        days_ago = (date_type.today() - target_date).days

        if days_ago > 5:
            url = "https://archive-api.open-meteo.com/v1/archive"
        else:
            url = f"{self.base_url}/forecast"

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": date,
            "end_date": date,
            "daily": ",".join([
                "temperature_2m_max",
                "temperature_2m_min",
                "temperature_2m_mean",
                "apparent_temperature_max",
                "apparent_temperature_min",
                "relative_humidity_2m_mean",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
                "precipitation_sum",
                "weather_code",
                "sunrise",
                "sunset",
                "daylight_duration",
            ]),
            "timezone": "auto",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily", {})

        def _first(key: str):
            arr = daily.get(key, [])
            if arr:
                return arr[0]
            return None

        weather_code = _first("weather_code")
        sunrise_raw = _first("sunrise")
        sunset_raw = _first("sunset")
        daylight_s = _first("daylight_duration")

        # Extract HH:MM from ISO timestamps for sunrise/sunset
        sunrise = None
        if sunrise_raw:
            try:
                sunrise = datetime.fromisoformat(sunrise_raw).strftime("%H:%M")
            except (ValueError, TypeError):
                sunrise = str(sunrise_raw)

        sunset = None
        if sunset_raw:
            try:
                sunset = datetime.fromisoformat(sunset_raw).strftime("%H:%M")
            except (ValueError, TypeError):
                sunset = str(sunset_raw)

        daylight_hours = None
        if daylight_s is not None:
            daylight_hours = round(daylight_s / 3600.0, 2)

        return {
            "date": date,
            "latitude": lat,
            "longitude": lon,
            "temperature_high_c": _first("temperature_2m_max"),
            "temperature_low_c": _first("temperature_2m_min"),
            "temperature_mean_c": _first("temperature_2m_mean"),
            "feels_like_high_c": _first("apparent_temperature_max"),
            "feels_like_low_c": _first("apparent_temperature_min"),
            "humidity_mean_pct": _first("relative_humidity_2m_mean"),
            "wind_speed_max_kmh": _first("wind_speed_10m_max"),
            "wind_gust_max_kmh": _first("wind_gusts_10m_max"),
            "precipitation_sum_mm": _first("precipitation_sum"),
            "weather_code": weather_code,
            "description": wmo_description(weather_code),
            "sunrise": sunrise,
            "sunset": sunset,
            "daylight_hours": daylight_hours,
        }

    # ------------------------------------------------------------------
    # Batch daily weather (range of dates in one API call)
    # ------------------------------------------------------------------

    async def get_daily_weather_range(
        self, lat: float, lon: float, start_date: str, end_date: str
    ) -> list[dict]:
        """Get daily weather summaries for a date range in one API call.

        This is more efficient than calling get_daily_weather() in a loop.
        Automatically splits the request between archive and forecast APIs
        based on date ranges.

        Args:
            lat: Latitude.
            lon: Longitude.
            start_date: ISO date string (YYYY-MM-DD) for the range start.
            end_date: ISO date string (YYYY-MM-DD) for the range end.

        Returns:
            List of dicts, one per day, matching daily_weather table columns.
        """
        results: list[dict] = []

        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        today = date_type.today()

        # The boundary: dates more than 5 days ago use archive, rest use forecast
        archive_cutoff = today - timedelta(days=5)

        # Determine which APIs to call
        ranges_to_fetch: list[tuple[str, str, str]] = []  # (url, start, end)

        if end_dt <= archive_cutoff:
            # All dates are old enough for archive
            ranges_to_fetch.append((
                "https://archive-api.open-meteo.com/v1/archive",
                start_date,
                end_date,
            ))
        elif start_dt > archive_cutoff:
            # All dates are recent enough for forecast
            ranges_to_fetch.append((
                f"{self.base_url}/forecast",
                start_date,
                end_date,
            ))
        else:
            # Split: archive for older dates, forecast for recent
            archive_end = archive_cutoff.strftime("%Y-%m-%d")
            forecast_start = (archive_cutoff + timedelta(days=1)).strftime("%Y-%m-%d")
            ranges_to_fetch.append((
                "https://archive-api.open-meteo.com/v1/archive",
                start_date,
                archive_end,
            ))
            ranges_to_fetch.append((
                f"{self.base_url}/forecast",
                forecast_start,
                end_date,
            ))

        daily_fields = ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "relative_humidity_2m_mean",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "precipitation_sum",
            "weather_code",
            "sunrise",
            "sunset",
            "daylight_duration",
        ])

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for url, sd, ed in ranges_to_fetch:
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": sd,
                    "end_date": ed,
                    "daily": daily_fields,
                    "timezone": "auto",
                }
                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPError as exc:
                    log.error(
                        "Failed to fetch weather from %s for %s to %s: %s",
                        url, sd, ed, exc,
                    )
                    continue

                daily = data.get("daily", {})
                dates = daily.get("time", [])

                for i, d in enumerate(dates):
                    def _val(key: str, idx: int = i):
                        arr = daily.get(key, [])
                        if idx < len(arr):
                            return arr[idx]
                        return None

                    weather_code = _val("weather_code")
                    sunrise_raw = _val("sunrise")
                    sunset_raw = _val("sunset")
                    daylight_s = _val("daylight_duration")

                    sunrise = None
                    if sunrise_raw:
                        try:
                            sunrise = datetime.fromisoformat(sunrise_raw).strftime("%H:%M")
                        except (ValueError, TypeError):
                            sunrise = str(sunrise_raw)

                    sunset = None
                    if sunset_raw:
                        try:
                            sunset = datetime.fromisoformat(sunset_raw).strftime("%H:%M")
                        except (ValueError, TypeError):
                            sunset = str(sunset_raw)

                    daylight_hours = None
                    if daylight_s is not None:
                        daylight_hours = round(daylight_s / 3600.0, 2)

                    results.append({
                        "date": d,
                        "latitude": lat,
                        "longitude": lon,
                        "temperature_high_c": _val("temperature_2m_max"),
                        "temperature_low_c": _val("temperature_2m_min"),
                        "temperature_mean_c": _val("temperature_2m_mean"),
                        "feels_like_high_c": _val("apparent_temperature_max"),
                        "feels_like_low_c": _val("apparent_temperature_min"),
                        "humidity_mean_pct": _val("relative_humidity_2m_mean"),
                        "wind_speed_max_kmh": _val("wind_speed_10m_max"),
                        "wind_gust_max_kmh": _val("wind_gusts_10m_max"),
                        "precipitation_sum_mm": _val("precipitation_sum"),
                        "weather_code": weather_code,
                        "description": wmo_description(weather_code),
                        "sunrise": sunrise,
                        "sunset": sunset,
                        "daylight_hours": daylight_hours,
                    })

        return results


# ======================================================================
# Database helpers
# ======================================================================

def _get_athlete_location() -> tuple[float, float]:
    """Read athlete's home location from athlete_profile, defaulting to Trondheim."""
    try:
        with get_db() as db:
            row = db.execute(
                "SELECT location_lat, location_lon FROM athlete_profile WHERE id = 1"
            ).fetchone()
            if row and row["location_lat"] is not None and row["location_lon"] is not None:
                return (row["location_lat"], row["location_lon"])
    except Exception:
        # Table may not exist yet (pre-init), fall through to default
        pass
    return (DEFAULT_LAT, DEFAULT_LON)


def upsert_daily_weather(weather: dict) -> None:
    """Insert or update a single daily weather record."""
    with get_db() as db:
        db.execute(
            """INSERT INTO daily_weather (
                date, latitude, longitude,
                temperature_high_c, temperature_low_c, temperature_mean_c,
                feels_like_high_c, feels_like_low_c,
                humidity_mean_pct,
                wind_speed_max_kmh, wind_gust_max_kmh,
                precipitation_sum_mm,
                weather_code, description,
                sunrise, sunset, daylight_hours
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                temperature_high_c=excluded.temperature_high_c,
                temperature_low_c=excluded.temperature_low_c,
                temperature_mean_c=excluded.temperature_mean_c,
                feels_like_high_c=excluded.feels_like_high_c,
                feels_like_low_c=excluded.feels_like_low_c,
                humidity_mean_pct=excluded.humidity_mean_pct,
                wind_speed_max_kmh=excluded.wind_speed_max_kmh,
                wind_gust_max_kmh=excluded.wind_gust_max_kmh,
                precipitation_sum_mm=excluded.precipitation_sum_mm,
                weather_code=excluded.weather_code,
                description=excluded.description,
                sunrise=excluded.sunrise,
                sunset=excluded.sunset,
                daylight_hours=excluded.daylight_hours
            """,
            (
                weather["date"],
                weather["latitude"],
                weather["longitude"],
                weather.get("temperature_high_c"),
                weather.get("temperature_low_c"),
                weather.get("temperature_mean_c"),
                weather.get("feels_like_high_c"),
                weather.get("feels_like_low_c"),
                weather.get("humidity_mean_pct"),
                weather.get("wind_speed_max_kmh"),
                weather.get("wind_gust_max_kmh"),
                weather.get("precipitation_sum_mm"),
                weather.get("weather_code"),
                weather.get("description"),
                weather.get("sunrise"),
                weather.get("sunset"),
                weather.get("daylight_hours"),
            ),
        )


def upsert_activity_weather(activity_id: int, weather: dict) -> None:
    """Insert or update weather cache for an activity."""
    with get_db() as db:
        db.execute(
            """INSERT INTO weather_cache (
                activity_id, latitude, longitude, timestamp,
                temperature_c, feels_like_c, humidity_pct,
                wind_speed_kmh, wind_gust_kmh, wind_direction,
                precipitation_mm, weather_code, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(activity_id) DO UPDATE SET
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                timestamp=excluded.timestamp,
                temperature_c=excluded.temperature_c,
                feels_like_c=excluded.feels_like_c,
                humidity_pct=excluded.humidity_pct,
                wind_speed_kmh=excluded.wind_speed_kmh,
                wind_gust_kmh=excluded.wind_gust_kmh,
                wind_direction=excluded.wind_direction,
                precipitation_mm=excluded.precipitation_mm,
                weather_code=excluded.weather_code,
                description=excluded.description
            """,
            (
                activity_id,
                weather.get("latitude"),
                weather.get("longitude"),
                weather.get("timestamp"),
                weather.get("temperature_c"),
                weather.get("feels_like_c"),
                weather.get("humidity_pct"),
                weather.get("wind_speed_kmh"),
                weather.get("wind_gust_kmh"),
                weather.get("wind_direction"),
                weather.get("precipitation_mm"),
                weather.get("weather_code"),
                weather.get("description"),
            ),
        )


def get_daily_weather_from_db(days: int = 7) -> list[dict]:
    """Retrieve the last N days of daily weather from the database."""
    cutoff = (date_type.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM daily_weather WHERE date >= ? ORDER BY date DESC",
            (cutoff,),
        ).fetchall()
        return dicts_from_rows(rows)


# ======================================================================
# Sync function — called from API or scheduler
# ======================================================================

async def sync_daily_weather(days: int = 7) -> int:
    """Fetch daily weather for the athlete's home location for the last N days.

    Reads the athlete's location from athlete_profile (defaults to Trondheim).
    Stores results into daily_weather with UPSERT semantics.

    Returns the number of days synced.
    """
    lat, lon = _get_athlete_location()

    end_date = date_type.today().strftime("%Y-%m-%d")
    start_date = (date_type.today() - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    log.info(
        "Syncing daily weather for lat=%.2f lon=%.2f from %s to %s",
        lat, lon, start_date, end_date,
    )

    client = WeatherClient()
    weather_days = await client.get_daily_weather_range(lat, lon, start_date, end_date)

    count = 0
    for day_data in weather_days:
        try:
            upsert_daily_weather(day_data)
            count += 1
        except Exception:
            log.exception("Failed to upsert daily weather for %s", day_data.get("date"))

    log.info("Synced %d days of daily weather", count)
    return count
