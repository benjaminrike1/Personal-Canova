"""Tiered context builder for Claude API — implements the context priority system.

Tier 1 (ALWAYS included):
  - athlete_profile
  - coach_notebook (active entries)
  - active_injuries
  - training_phase (current)
  - current_week_plan
  - race_calendar (upcoming)

Tier 2 (included when budget allows):
  - recent_checkins (14 days)
  - recent_activities with weather (14 days)
  - wellness_trends (14 days)
  - work_stress_trends (14 days)
  - personal_records
  - daily_weather (7 days)

Tier 3 (first to drop):
  - conversation_history (oldest messages dropped first)
"""


class ContextBuilder:
    """Builds the context payload for Claude API calls, respecting token budgets."""

    def __init__(self, max_context_tokens: int = 180000):
        self.max_context_tokens = max_context_tokens

    async def build(self, conversation_id: int | None = None) -> dict:
        raise NotImplementedError
