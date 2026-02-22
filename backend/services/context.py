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

import json
from datetime import date, datetime, timedelta

from backend.core.database import get_db


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return len(text) // 4


def _format_duration(seconds: float | None) -> str:
    if not seconds:
        return "-"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def _format_pace_s_per_km(speed_mps: float | None) -> str:
    """Convert m/s to min:sec/km."""
    if not speed_mps or speed_mps <= 0:
        return "-"
    s_per_km = 1000 / speed_mps
    m = int(s_per_km // 60)
    s = int(s_per_km % 60)
    return f"{m}:{s:02d}/km"


class ContextBuilder:
    """Builds the context payload for Claude API calls, respecting token budgets."""

    def __init__(self, max_context_tokens: int = 160000):
        self.max_context_tokens = max_context_tokens

    def build_system_prompt(self, conversation_id: int | None = None) -> str:
        """Build the full system prompt with all available context."""
        sections = []

        # Core identity
        sections.append(self._core_identity())

        # Tier 1: Always included
        sections.append(self._athlete_profile())
        sections.append(self._coach_notebook())
        sections.append(self._active_injuries())
        sections.append(self._training_phase())
        sections.append(self._current_week_plan())
        sections.append(self._race_calendar())

        # Tier 2: Budget permitting
        tier2_sections = [
            self._recent_checkins(),
            self._recent_activities(),
            self._wellness_trends(),
            self._work_stress_trends(),
            self._personal_records(),
            self._daily_weather(),
        ]

        # Estimate tokens used so far
        tier1_text = "\n\n".join(s for s in sections if s)
        used = _estimate_tokens(tier1_text)
        budget = self.max_context_tokens - 20000  # reserve for conversation + response

        for section in tier2_sections:
            if not section:
                continue
            section_tokens = _estimate_tokens(section)
            if used + section_tokens < budget:
                sections.append(section)
                used += section_tokens

        # Behavior instructions (always at end)
        sections.append(self._behavior_instructions())

        return "\n\n".join(s for s in sections if s)

    def get_conversation_messages(
        self, conversation_id: int, max_messages: int = 50
    ) -> list[dict]:
        """Get conversation history as Claude API message format."""
        with get_db() as db:
            rows = db.execute(
                """SELECT role, content FROM messages
                   WHERE conversation_id = ? AND role IN ('user', 'assistant')
                   ORDER BY created_at ASC LIMIT ?""",
                (conversation_id, max_messages),
            ).fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]

    # --- Tier 1: Always included ---

    def _core_identity(self) -> str:
        today = date.today()
        weekday = today.strftime("%A")
        return f"""You are a personal endurance coach — knowledgeable, direct, and pragmatic.
You coach ONE athlete. All the data below is about YOUR athlete.

Today is {today.isoformat()} ({weekday}).

Your coaching philosophy:
- Training is a stress-recovery-adaptation cycle. You manage the stress side; the athlete manages the recovery side. Your job is to ensure the right dose of stress at the right time.
- Consistency beats heroics. A solid week of 90% effort is better than one great session followed by injury.
- You respect the athlete's work-life constraints. A late work night means tomorrow's hard session should move. This is not weakness — it's intelligent periodization.
- You interpret data in context. A dropping CTL during a run-focus phase after triathlon season is expected. A high ATL with poor sleep and high work stress is a red flag.
- You are honest and direct. If the athlete is overreaching, you say so. If they're sandbagging, you say so.
- You think in terms of the current training phase, the next A-race, and long-term athletic development.
- You track aerobic efficiency (HR:pace coupling), key session progression, and injury patterns over time.
- When making plan adjustments, you explain WHY, referencing specific data."""

    def _athlete_profile(self) -> str:
        with get_db() as db:
            row = db.execute("SELECT * FROM athlete_profile WHERE id = 1").fetchone()
            if not row:
                return "## Athlete Profile\nNo profile yet — onboarding not complete."

            p = dict(row)
            parts = ["## Athlete Profile"]
            parts.append(f"Name: {p['name']}")
            if p.get("date_of_birth"):
                age = (date.today() - date.fromisoformat(p["date_of_birth"])).days // 365
                parts.append(f"Age: {age} (DOB: {p['date_of_birth']})")
            if p.get("gender"):
                parts.append(f"Gender: {p['gender']}")
            if p.get("weight_kg"):
                parts.append(f"Weight: {p['weight_kg']}kg")
            if p.get("height_cm"):
                parts.append(f"Height: {p['height_cm']}cm")
            if p.get("years_experience"):
                parts.append(f"Experience: {p['years_experience']} years")
            parts.append(f"Weekly training target: {p.get('weekly_hours_target_low', '?')}-{p.get('weekly_hours_target_high', '?')} hours")
            parts.append(f"Typical work finish: {p.get('work_finish_time_baseline', '?')}")
            parts.append(f"Normal weekly work hours: {p.get('work_hours_baseline', '?')}")
            if p.get("training_background"):
                parts.append(f"Training background: {p['training_background']}")
            if p.get("what_worked"):
                parts.append(f"What has worked: {p['what_worked']}")
            if p.get("what_didnt_work"):
                parts.append(f"What hasn't worked: {p['what_didnt_work']}")
            if p.get("current_goals"):
                parts.append(f"Current goals: {p['current_goals']}")
            return "\n".join(parts)

    def _coach_notebook(self) -> str:
        with get_db() as db:
            rows = db.execute(
                """SELECT category, content, confidence FROM coach_notebook
                   WHERE active = 1 ORDER BY category, created_at DESC"""
            ).fetchall()
            if not rows:
                return "## Coach's Notebook\nNo observations yet."

            parts = ["## Coach's Notebook (Active Observations)"]
            for r in rows:
                conf = f" [{r['confidence']}]" if r["confidence"] != "medium" else ""
                parts.append(f"- [{r['category'].upper()}]{conf} {r['content']}")
            return "\n".join(parts)

    def _active_injuries(self) -> str:
        with get_db() as db:
            rows = db.execute(
                """SELECT i.id, i.body_part, i.description, i.severity, i.status, i.onset_date
                   FROM injuries i WHERE i.status IN ('active', 'monitoring')
                   ORDER BY i.severity DESC"""
            ).fetchall()
            if not rows:
                return "## Injuries\nNo active injuries."

            parts = ["## Active Injuries"]
            for r in rows:
                days = (date.today() - date.fromisoformat(r["onset_date"])).days
                parts.append(
                    f"- {r['body_part']} ({r['status']}, severity {r['severity']}/10, "
                    f"onset {days} days ago): {r['description']}"
                )

                update = db.execute(
                    """SELECT severity, notes, date FROM injury_updates
                       WHERE injury_id = ?
                       ORDER BY date DESC LIMIT 1""",
                    (r["id"],),
                ).fetchone()
                if update:
                    parts.append(
                        f"  Latest update ({update['date']}): severity {update['severity']}/10"
                        + (f" — {update['notes']}" if update.get("notes") else "")
                    )
            return "\n".join(parts)

    def _training_phase(self) -> str:
        today_str = date.today().isoformat()
        with get_db() as db:
            row = db.execute(
                """SELECT * FROM training_phases
                   WHERE start_date <= ? AND (end_date IS NULL OR end_date >= ?)
                   ORDER BY start_date DESC LIMIT 1""",
                (today_str, today_str),
            ).fetchone()
            if not row:
                return "## Training Phase\nNo active training phase defined."

            p = dict(row)
            parts = ["## Current Training Phase"]
            parts.append(f"Phase: {p.get('name', p['phase_type'].title())} ({p['phase_type']})")
            parts.append(f"Sport focus: {p['primary_sport_focus']}")
            parts.append(f"Started: {p['start_date']}")
            if p.get("end_date"):
                parts.append(f"Ends: {p['end_date']}")
            if p.get("notes"):
                parts.append(f"Notes: {p['notes']}")
            if p.get("target_race_id"):
                race = db.execute(
                    "SELECT name, date FROM races WHERE id = ?", (p["target_race_id"],)
                ).fetchone()
                if race:
                    parts.append(f"Target race: {race['name']} ({race['date']})")
            return "\n".join(parts)

    def _current_week_plan(self) -> str:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        week_start = monday.isoformat()

        with get_db() as db:
            rows = db.execute(
                """SELECT tp.*, a.name as actual_name, a.duration_s as actual_duration,
                          a.avg_hr as actual_hr, a.training_load as actual_load
                   FROM training_plan tp
                   LEFT JOIN activities a ON tp.actual_activity_id = a.id
                   WHERE tp.week_start = ?
                   ORDER BY tp.day_of_week, tp.session_order""",
                (week_start,),
            ).fetchall()
            if not rows:
                return "## This Week's Plan\nNo plan defined for this week."

            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            parts = [f"## This Week's Training Plan (w/c {week_start})"]

            current_day = -1
            for r in rows:
                dow = r["day_of_week"]
                if dow != current_day:
                    current_day = dow
                    day_date = monday + timedelta(days=dow)
                    is_past = day_date < today
                    is_today = day_date == today
                    marker = " (TODAY)" if is_today else (" (done)" if is_past else "")
                    parts.append(f"\n**{day_names[dow]}{marker}**")

                if r["is_rest_day"]:
                    parts.append("  REST DAY")
                    continue

                key = " [KEY]" if r["is_key_session"] else ""
                duration = _format_duration(r["target_duration_s"])
                line = f"  {r['session_type']}{key} — {duration}"
                if r.get("target_intensity"):
                    line += f" @ {r['target_intensity']}"
                if r.get("key_objective"):
                    line += f" | {r['key_objective']}"

                if r["completed"] and r.get("actual_name"):
                    actual_dur = _format_duration(r.get("actual_duration"))
                    line += f"\n    Done: {r['actual_name']} ({actual_dur})"
                    if r.get("actual_hr"):
                        line += f", avg HR {r['actual_hr']:.0f}"

                if r.get("deviation_notes"):
                    line += f"\n    Deviation: {r['deviation_notes']}"

                parts.append(line)

            return "\n".join(parts)

    def _race_calendar(self) -> str:
        today_str = date.today().isoformat()
        with get_db() as db:
            rows = db.execute(
                """SELECT * FROM races WHERE date >= ? AND status = 'upcoming'
                   ORDER BY date ASC LIMIT 10""",
                (today_str,),
            ).fetchall()
            if not rows:
                return "## Race Calendar\nNo upcoming races."

            parts = ["## Upcoming Races"]
            for r in rows:
                days_until = (date.fromisoformat(r["date"]) - date.today()).days
                weeks = days_until // 7
                parts.append(
                    f"- [{r['priority']}] {r['name']} — {r['date']} "
                    f"({r.get('distance_label', '?')}, {r.get('discipline', '?')}) "
                    f"— {weeks} weeks / {days_until} days away"
                )
                if r.get("goal_notes"):
                    parts.append(f"  Goal: {r['goal_notes']}")
                if r.get("goal_time_s"):
                    parts.append(f"  Target time: {_format_duration(r['goal_time_s'])}")
            return "\n".join(parts)

    # --- Tier 2: Included when budget allows ---

    def _recent_checkins(self) -> str:
        cutoff = (date.today() - timedelta(days=14)).isoformat()
        with get_db() as db:
            rows = db.execute(
                """SELECT * FROM checkins WHERE date >= ? AND completed = 1
                   ORDER BY date DESC, type""",
                (cutoff,),
            ).fetchall()
            if not rows:
                return ""

            parts = ["## Recent Check-ins (14 days)"]
            for r in rows:
                line = f"**{r['date']} {r['type']}**: "
                fields = []
                if r.get("sleep_quality"):
                    fields.append(f"sleep={r['sleep_quality']}/10")
                if r.get("hours_slept"):
                    fields.append(f"{r['hours_slept']}h sleep")
                if r.get("energy_level"):
                    fields.append(f"energy={r['energy_level']}/10")
                if r.get("work_stress"):
                    fields.append(f"work_stress={r['work_stress']}/10")
                if r.get("motivation"):
                    fields.append(f"motivation={r['motivation']}/10")
                if r.get("did_planned"):
                    fields.append(f"planned={r['did_planned']}")
                if r.get("nutrition"):
                    fields.append(f"nutrition={r['nutrition']}")
                if r.get("alcohol"):
                    fields.append("alcohol=yes")
                if r.get("injury_update"):
                    fields.append(f"injury: {r['injury_update']}")
                if r.get("improvement"):
                    fields.append(f"improve: {r['improvement']}")
                if r.get("tomorrow_objective"):
                    fields.append(f"tomorrow: {r['tomorrow_objective']}")
                if r.get("weekly_reflection"):
                    fields.append(f"reflection: {r['weekly_reflection'][:200]}")
                line += ", ".join(fields) if fields else "(no data)"
                parts.append(line)
            return "\n".join(parts)

    def _recent_activities(self) -> str:
        cutoff = (date.today() - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00")
        with get_db() as db:
            rows = db.execute(
                """SELECT a.*, ks.session_type as key_session_type,
                          wc.temperature_c as weather_temp, wc.description as weather_desc
                   FROM activities a
                   LEFT JOIN key_sessions ks ON ks.activity_id = a.id
                   LEFT JOIN weather_cache wc ON wc.activity_id = a.id
                   WHERE a.start_time >= ?
                   ORDER BY a.start_time DESC""",
                (cutoff,),
            ).fetchall()
            if not rows:
                return ""

            parts = ["## Recent Activities (14 days)"]
            for r in rows:
                dist_km = (r["distance_m"] or 0) / 1000
                dur = _format_duration(r["duration_s"])
                pace = _format_pace_s_per_km(r["avg_speed"])
                line = (
                    f"- {r['start_time'][:10]} {r['sport']} \"{r.get('name', '')}\" "
                    f"— {dist_km:.1f}km, {dur}"
                )
                if r["avg_hr"]:
                    line += f", HR {r['avg_hr']:.0f}"
                if r.get("avg_speed") and r["sport"] == "Run":
                    line += f", pace {pace}"
                if r.get("np"):
                    line += f", NP {r['np']:.0f}W"
                elif r.get("avg_power"):
                    line += f", {r['avg_power']:.0f}W"
                if r.get("training_load"):
                    line += f", load {r['training_load']:.0f}"
                if r.get("key_session_type"):
                    line += f" [KEY: {r['key_session_type']}]"
                if r.get("decoupling") is not None:
                    line += f", decouple {r['decoupling']:.1f}%"
                if r.get("weather_temp") is not None:
                    line += f", {r['weather_temp']:.0f}°C"
                    if r.get("weather_desc"):
                        line += f" ({r['weather_desc']})"

                if r.get("interval_summary"):
                    try:
                        intervals = json.loads(r["interval_summary"])
                        if intervals:
                            line += f"\n  Intervals: {'; '.join(str(i) for i in intervals[:3])}"
                    except (json.JSONDecodeError, TypeError):
                        pass

                parts.append(line)
            return "\n".join(parts)

    def _wellness_trends(self) -> str:
        cutoff = (date.today() - timedelta(days=14)).isoformat()
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM wellness WHERE date >= ? ORDER BY date DESC",
                (cutoff,),
            ).fetchall()
            if not rows:
                return ""

            parts = ["## Wellness Trends (14 days)"]
            parts.append("Date       | CTL   | ATL   | TSB   | Ramp  | HRV  | RHR | Sleep | Weight")
            parts.append("---------- | ----- | ----- | ----- | ----- | ---- | --- | ----- | ------")
            for r in rows:
                ctl = r["ctl"] or 0
                atl = r["atl"] or 0
                tsb = ctl - atl
                sleep_h = f"{(r['sleep_seconds'] or 0) / 3600:.1f}h"
                hrv = f"{r['hrv']:.0f}" if r.get("hrv") else "-"
                rhr = f"{r['resting_hr']:.0f}" if r.get("resting_hr") else "-"
                wt = f"{r['weight_kg']:.1f}" if r.get("weight_kg") else "-"
                ramp = f"{r['ramp_rate']:+.1f}" if r.get("ramp_rate") else "-"
                parts.append(
                    f"{r['date']} | {ctl:5.1f} | {atl:5.1f} | {tsb:+5.1f} | {ramp:>5s} | {hrv:>4s} | {rhr:>3s} | {sleep_h:>5s} | {wt:>6s}"
                )
            return "\n".join(parts)

    def _work_stress_trends(self) -> str:
        cutoff = (date.today() - timedelta(days=14)).isoformat()
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM work_log WHERE date >= ? ORDER BY date DESC",
                (cutoff,),
            ).fetchall()
            if not rows:
                return ""

            parts = ["## Work Stress (14 days)"]
            for r in rows:
                finish = r.get("finish_time") or "?"
                stress = r.get("stress_level") or "?"
                hours = f"{r['hours_worked']:.0f}h" if r.get("hours_worked") else ""
                parts.append(f"- {r['date']}: finished {finish}, stress {stress}/10 {hours}")
            return "\n".join(parts)

    def _personal_records(self) -> str:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM personal_records ORDER BY discipline, event"
            ).fetchall()
            if not rows:
                return ""

            parts = ["## Personal Records"]
            for r in rows:
                if r["value_unit"] == "seconds":
                    val = _format_duration(r["value"])
                else:
                    val = f"{r['value']}{r['value_unit']}"
                line = f"- {r['discipline']} {r['event']}: {val}"
                if r.get("date_achieved"):
                    line += f" ({r['date_achieved']})"
                parts.append(line)
            return "\n".join(parts)

    def _daily_weather(self) -> str:
        cutoff = (date.today() - timedelta(days=7)).isoformat()
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM daily_weather WHERE date >= ? ORDER BY date DESC",
                (cutoff,),
            ).fetchall()
            if not rows:
                return ""

            parts = ["## Weather (7 days)"]
            for r in rows:
                desc = r.get("description") or "?"
                high = f"{r['temperature_high_c']:.0f}" if r.get("temperature_high_c") is not None else "?"
                low = f"{r['temperature_low_c']:.0f}" if r.get("temperature_low_c") is not None else "?"
                wind = f"{r['wind_speed_max_kmh']:.0f}km/h" if r.get("wind_speed_max_kmh") else "?"
                precip = f"{r['precipitation_sum_mm']:.1f}mm" if r.get("precipitation_sum_mm") else "0mm"
                parts.append(f"- {r['date']}: {desc}, {low}-{high}°C, wind {wind}, precip {precip}")
            return "\n".join(parts)

    # --- Behavior instructions ---

    def _behavior_instructions(self) -> str:
        return """## How to Respond

When the athlete messages you:
1. ALWAYS reference their actual data. Never make generic statements when you have specific numbers.
2. When suggesting plan changes, explain WHY using their data (CTL trend, sleep pattern, work stress, injury status).
3. If you notice something concerning (injury worsening, chronic poor sleep, overreaching), flag it proactively even if they didn't ask.
4. Keep responses concise and actionable. Lead with the key insight, then supporting data.
5. When asked about a training session, consider: the plan for today, yesterday's load, sleep quality, work stress, injury status, weather, and phase goals.
6. Use their name occasionally but don't be sycophantic.
7. If they ask you to adjust the plan, think about the WHOLE week — moving one session affects the others.
8. Track aerobic efficiency trends: if HR:pace is decoupling more than usual, that's a flag.
9. After meaningful conversations where you learn something new about the athlete (preferences, patterns, responses to training), note these as coach_notebook entries by including a JSON block:
```notebook
{"category": "pattern|observation|preference|risk|strength", "content": "The observation", "confidence": "low|medium|high"}
```
10. If the conversation warrants a plan adjustment, include:
```plan_adjustment
{"entry_id": N, "changes": {"field": "new_value"}, "reason": "Why this change"}
```"""
