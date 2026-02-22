"""Open-Meteo weather client — activity weather + daily weather."""


class WeatherClient:
    """Client for the Open-Meteo API (no key required)."""

    async def get_activity_weather(self, lat: float, lon: float, timestamp: str) -> dict:
        raise NotImplementedError

    async def get_daily_weather(self, lat: float, lon: float, date: str) -> dict:
        raise NotImplementedError
