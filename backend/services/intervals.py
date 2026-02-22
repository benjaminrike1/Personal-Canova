"""Intervals.icu API client — activities, wellness, fitness curves."""


class IntervalsClient:
    """Client for the Intervals.icu REST API."""

    def __init__(self, athlete_id: str, api_key: str):
        self.athlete_id = athlete_id
        self.api_key = api_key

    async def get_activities(self, oldest: str, newest: str) -> list[dict]:
        raise NotImplementedError

    async def get_wellness(self, oldest: str, newest: str) -> list[dict]:
        raise NotImplementedError

    async def get_activity_streams(self, activity_id: str) -> dict:
        raise NotImplementedError
