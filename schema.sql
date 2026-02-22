-- Coach App — Full Database Schema
-- SQLite with strict typing where possible
-- All timestamps stored as ISO 8601 UTC strings
-- All distances in meters, durations in seconds, weights in kg

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- ATHLETE PROFILE (single row — one athlete app)
-- ============================================================
CREATE TABLE IF NOT EXISTS athlete_profile (
    id              INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    name            TEXT NOT NULL,
    date_of_birth   TEXT,                          -- ISO date
    gender          TEXT,                          -- M/F/Other
    height_cm       REAL,
    weight_kg       REAL,
    years_experience INTEGER,
    training_background TEXT,                      -- free text from onboarding
    what_worked     TEXT,                          -- free text: what has worked
    what_didnt_work TEXT,                          -- free text: what hasn't worked
    current_goals   TEXT,                          -- free text
    weekly_hours_target_low  REAL DEFAULT 10.0,    -- target range low
    weekly_hours_target_high REAL DEFAULT 15.0,    -- target range high
    work_hours_baseline      REAL DEFAULT 60.0,    -- normal weekly work hours
    work_finish_time_baseline TEXT DEFAULT '22:00', -- typical finish time
    intervals_athlete_id     TEXT,                 -- Intervals.icu athlete ID
    onboarding_complete      INTEGER DEFAULT 0,    -- boolean
    timezone        TEXT DEFAULT 'Europe/Amsterdam',
    location_lat    REAL,                          -- home location for weather
    location_lon    REAL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ============================================================
-- PERSONAL RECORDS & BENCHMARKS
-- ============================================================
CREATE TABLE IF NOT EXISTS personal_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discipline      TEXT NOT NULL,                 -- 'running' / 'cycling'
    event           TEXT NOT NULL,                 -- '5k', '10k', 'half_marathon', 'marathon', 'ftp', custom
    value           REAL NOT NULL,                 -- seconds for running, watts for FTP
    value_unit      TEXT NOT NULL,                 -- 'seconds' / 'watts' / 'w_kg'
    date_achieved   TEXT,                          -- ISO date
    source          TEXT,                          -- 'manual' / 'detected' / 'race'
    notes           TEXT,
    activity_id     TEXT,                          -- link to activity if detected
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_pr_discipline ON personal_records(discipline);
CREATE INDEX IF NOT EXISTS idx_pr_event ON personal_records(event);

-- ============================================================
-- RACE CALENDAR
-- ============================================================
CREATE TABLE IF NOT EXISTS races (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    date            TEXT NOT NULL,                 -- ISO date
    distance_m      REAL,                          -- distance in meters
    distance_label  TEXT,                          -- human label: '10k', 'half marathon', etc.
    discipline      TEXT NOT NULL DEFAULT 'running', -- 'running' / 'cycling' / 'triathlon'
    priority        TEXT NOT NULL CHECK (priority IN ('A', 'B', 'C')),
    goal_time_s     REAL,                          -- target time in seconds
    goal_notes      TEXT,                          -- e.g. "sub-40 10k"
    result_time_s   REAL,                          -- actual result (filled post-race)
    result_notes    TEXT,
    notes           TEXT,                          -- narrative race analysis: conditions, how it went, lessons learned
    status          TEXT NOT NULL DEFAULT 'upcoming' CHECK (status IN ('upcoming', 'completed', 'dns', 'dnf', 'cancelled')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_races_date ON races(date);
CREATE INDEX IF NOT EXISTS idx_races_priority ON races(priority);

-- ============================================================
-- TRAINING PHASES
-- ============================================================
-- The current active phase is always injected into coaching context.
-- Critical for interpreting CTL correctly when sport focus shifts —
-- a dropping CTL during a run-focus block after a triathlon period
-- is expected and should not trigger concern.
CREATE TABLE IF NOT EXISTS training_phases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT,                          -- e.g. "Marathon base build", "Tri season"
    start_date      TEXT NOT NULL,                 -- ISO date
    end_date        TEXT,                          -- ISO date, NULL = open-ended / current
    primary_sport_focus TEXT NOT NULL CHECK (primary_sport_focus IN ('run', 'bike', 'triathlon', 'other')),
    phase_type      TEXT NOT NULL CHECK (phase_type IN ('base', 'build', 'peak', 'taper', 'recovery')),
    target_race_id  INTEGER REFERENCES races(id),  -- optional link to target A-race
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_phases_dates ON training_phases(start_date, end_date);

-- ============================================================
-- ACTIVITIES (synced from Intervals.icu)
-- ============================================================
CREATE TABLE IF NOT EXISTS activities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    intervals_id    TEXT UNIQUE,                   -- Intervals.icu activity ID
    sport           TEXT NOT NULL DEFAULT 'Other',  -- 'Run', 'Ride', 'Swim', etc.
    sub_type        TEXT,                          -- Intervals.icu sub-type
    name            TEXT,
    description     TEXT,
    start_time      TEXT NOT NULL DEFAULT '',      -- ISO 8601 local
    start_time_utc  TEXT,                          -- ISO 8601 UTC
    duration_s      REAL,                          -- moving time in seconds
    elapsed_s       REAL,                          -- elapsed time
    recording_s     REAL,                          -- recording time
    distance_m      REAL,
    avg_hr          REAL,
    max_hr          REAL,
    avg_speed       REAL,                          -- m/s
    max_speed       REAL,                          -- m/s
    avg_pace        REAL,                          -- s/m from Intervals
    gap             REAL,                          -- grade adjusted pace s/m
    avg_power       REAL,                          -- average watts
    np              REAL,                          -- normalized / weighted avg watts
    avg_cadence     REAL,
    elevation_gain  REAL,                          -- meters
    elevation_loss  REAL,                          -- meters
    calories        REAL,
    training_load   REAL,                          -- Intervals.icu training load
    atl             REAL,                          -- acute training load at time of activity
    ctl             REAL,                          -- chronic training load at time of activity
    ftp             REAL,                          -- FTP used for this activity
    intensity       REAL,                          -- intensity factor from Intervals
    efficiency_factor REAL,
    variability_index REAL,
    decoupling      REAL,                          -- aerobic decoupling %
    trimp           REAL,
    polarization_index REAL,
    perceived_exertion REAL,                       -- Garmin perceived exertion
    rpe             REAL,                          -- Intervals.icu RPE
    session_rpe     REAL,                          -- session RPE
    feel            REAL,                          -- how it felt 1-5
    avg_temp_c      REAL,                          -- device temp sensor
    avg_weather_temp_c REAL,                       -- from weather overlay
    hr_zone_times   TEXT,                          -- JSON: seconds per HR zone
    pace_zone_times TEXT,                          -- JSON: seconds per pace zone
    power_zone_times TEXT,                         -- JSON: seconds per power zone
    hr_zones        TEXT,                          -- JSON: zone boundaries used
    pace_zones      TEXT,                          -- JSON: zone boundaries used
    power_zones     TEXT,                          -- JSON: zone boundaries used
    interval_summary TEXT,                         -- JSON: interval descriptions
    is_indoor       INTEGER DEFAULT 0,
    is_race         INTEGER DEFAULT 0,
    gear_name       TEXT,
    threshold_pace  REAL,                          -- threshold pace s/m
    lthr            REAL,                          -- lactate threshold HR
    resting_hr      REAL,                          -- resting HR on that day
    weight_kg       REAL,                          -- weight on that day
    power_source    TEXT,                          -- 'stryd', 'garmin_rd_pod', 'stages', 'power2max', etc. from Intervals.icu powerMeter field
    compliance      REAL,                          -- planned vs actual compliance
    source          TEXT DEFAULT 'intervals',      -- 'intervals' / 'manual'
    strava_id       TEXT,
    synced_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_activities_sport ON activities(sport);
CREATE INDEX IF NOT EXISTS idx_activities_start ON activities(start_time);
CREATE INDEX IF NOT EXISTS idx_activities_intervals_id ON activities(intervals_id);

-- ============================================================
-- WEATHER CACHE (per activity)
-- ============================================================
CREATE TABLE IF NOT EXISTS weather_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id     INTEGER REFERENCES activities(id) ON DELETE CASCADE,
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    timestamp       TEXT NOT NULL,                 -- time of weather reading
    temperature_c   REAL,
    feels_like_c    REAL,
    humidity_pct    REAL,
    wind_speed_kmh  REAL,
    wind_gust_kmh   REAL,
    wind_direction  REAL,                          -- degrees
    precipitation_mm REAL,
    weather_code    INTEGER,                       -- WMO code
    description     TEXT,                          -- human readable
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(activity_id)
);

CREATE INDEX IF NOT EXISTS idx_weather_activity ON weather_cache(activity_id);

-- ============================================================
-- DAILY WEATHER (home location, every day including rest days)
-- ============================================================
-- Uses athlete_profile.location_lat/lon. Ensures rest days and
-- easy days still have weather context so the coach can interpret
-- fatigue and subjective feel correctly.
CREATE TABLE IF NOT EXISTS daily_weather (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL UNIQUE,           -- ISO date
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    temperature_high_c  REAL,
    temperature_low_c   REAL,
    temperature_mean_c  REAL,
    feels_like_high_c   REAL,
    feels_like_low_c    REAL,
    humidity_mean_pct    REAL,
    wind_speed_max_kmh   REAL,
    wind_gust_max_kmh    REAL,
    precipitation_sum_mm REAL,
    weather_code    INTEGER,                       -- WMO code (dominant)
    description     TEXT,                          -- human readable summary
    sunrise         TEXT,                          -- HH:MM local
    sunset          TEXT,                          -- HH:MM local
    daylight_hours  REAL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_daily_weather_date ON daily_weather(date);

-- ============================================================
-- WELLNESS (synced from Intervals.icu)
-- ============================================================
CREATE TABLE IF NOT EXISTS wellness (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL UNIQUE,           -- ISO date
    ctl             REAL,                          -- chronic training load
    atl             REAL,                          -- acute training load
    ramp_rate       REAL,                          -- CTL ramp rate
    weight_kg       REAL,
    resting_hr      REAL,
    hrv             REAL,                          -- HRV (rMSSD)
    hrv_sdnn        REAL,                          -- HRV SDNN
    sleep_seconds   REAL,                          -- total sleep duration
    sleep_score     REAL,                          -- Garmin sleep score
    sleep_quality   REAL,                          -- 1-5 scale
    avg_sleeping_hr REAL,                          -- average HR during sleep
    soreness        REAL,                          -- 1-10
    fatigue         REAL,                          -- 1-10
    stress          REAL,                          -- 1-10
    mood            REAL,                          -- 1-10
    motivation      REAL,                          -- 1-10
    spo2            REAL,                          -- blood oxygen %
    readiness       REAL,                          -- readiness score
    vo2max          REAL,                          -- estimated VO2max
    steps           INTEGER,                       -- daily step count
    respiration     REAL,                          -- respiration rate
    synced_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_wellness_date ON wellness(date);

-- ============================================================
-- CHECK-INS (morning / evening / weekend / weekly)
-- ============================================================
CREATE TABLE IF NOT EXISTS checkins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,                  -- ISO date
    type            TEXT NOT NULL CHECK (type IN ('morning', 'evening', 'weekend', 'weekly')),
    completed       INTEGER NOT NULL DEFAULT 0,    -- boolean: fully submitted
    completion_pct  REAL NOT NULL DEFAULT 0.0,     -- 0.0-100.0: partial completion for dashboard

    -- Morning fields
    sleep_quality   INTEGER CHECK (sleep_quality BETWEEN 1 AND 10),
    hours_slept     REAL,
    work_finish_time TEXT,                          -- e.g. '22:30'
    work_stress     INTEGER CHECK (work_stress BETWEEN 1 AND 10),
    energy_level    INTEGER CHECK (energy_level BETWEEN 1 AND 10),
    motivation      INTEGER CHECK (motivation BETWEEN 1 AND 10),
    body_weight_kg  REAL,
    injury_update   TEXT,                           -- free text

    -- Evening fields (per-session RPE stored in session_checkins)
    did_planned     TEXT CHECK (did_planned IN ('yes', 'partly', 'no')),
    tomorrow_objective TEXT,
    improvement     TEXT,                           -- one thing could have done better
    alcohol         INTEGER,                        -- boolean 0/1
    nutrition       TEXT CHECK (nutrition IN ('good', 'ok', 'poor')),

    -- Weekend fields: reuses sleep_quality, hours_slept, energy_level,
    --   improvement, tomorrow_objective, alcohol, nutrition
    -- (no work_stress, work_finish_time, motivation for weekends)

    -- Weekly fields
    hours_worked    REAL,
    three_improvements TEXT,                        -- JSON array of 3 strings
    weekly_reflection TEXT,                         -- free text

    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_checkins_date ON checkins(date);
CREATE INDEX IF NOT EXISTS idx_checkins_type ON checkins(type, date);

-- Per-session RPE within a check-in (supports two-a-days)
CREATE TABLE IF NOT EXISTS session_checkins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    checkin_id      INTEGER NOT NULL REFERENCES checkins(id) ON DELETE CASCADE,
    activity_id     INTEGER REFERENCES activities(id),
    session_type    TEXT,                           -- auto-filled from Intervals.icu
    rpe             INTEGER CHECK (rpe BETWEEN 1 AND 10),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_session_checkins_checkin ON session_checkins(checkin_id);

-- ============================================================
-- INJURY LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS injuries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    body_part       TEXT NOT NULL,                  -- e.g. 'right knee', 'left achilles'
    description     TEXT NOT NULL,
    onset_date      TEXT NOT NULL,                  -- ISO date
    severity        INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 10),
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'monitoring', 'resolved')),
    resolved_date   TEXT,                           -- ISO date when resolved
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_injuries_status ON injuries(status);
CREATE INDEX IF NOT EXISTS idx_injuries_body_part ON injuries(body_part);

-- Injury severity history (daily tracking from check-ins)
CREATE TABLE IF NOT EXISTS injury_updates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    injury_id       INTEGER NOT NULL REFERENCES injuries(id) ON DELETE CASCADE,
    date            TEXT NOT NULL,                  -- ISO date
    severity        INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 10),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_injury_updates_injury ON injury_updates(injury_id, date);

-- ============================================================
-- KEY SESSIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS key_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id     INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    session_type    TEXT NOT NULL,                  -- 'threshold_run', 'long_run', 'race_specific', 'tempo', 'interval', 'ftp_test', etc.
    tagged_by       TEXT NOT NULL DEFAULT 'athlete' CHECK (tagged_by IN ('athlete', 'coach')),
    performance_notes TEXT,                         -- coach's assessment
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(activity_id)
);

CREATE INDEX IF NOT EXISTS idx_key_sessions_type ON key_sessions(session_type);
CREATE INDEX IF NOT EXISTS idx_key_sessions_activity ON key_sessions(activity_id);

-- ============================================================
-- TRAINING PLAN
-- ============================================================
CREATE TABLE IF NOT EXISTS training_plan (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start      TEXT NOT NULL,                  -- ISO date (Monday)
    day_of_week     INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6), -- 0=Monday
    session_order   INTEGER NOT NULL DEFAULT 1,     -- for two-a-days: 1, 2
    session_type    TEXT NOT NULL,                  -- 'easy_run', 'threshold', 'long_run', 'rest', 'ride', etc.
    target_duration_s REAL,                         -- planned duration in seconds
    target_intensity TEXT,                          -- zone or description: 'Z2', 'threshold', '10k pace'
    key_objective   TEXT,                           -- one sentence
    is_key_session  INTEGER DEFAULT 0,             -- boolean: this is THE priority session for the week
    is_rest_day     INTEGER DEFAULT 0,             -- boolean
    completed       INTEGER DEFAULT 0,             -- boolean
    actual_activity_id INTEGER REFERENCES activities(id),
    deviation_notes TEXT,                           -- what changed and why
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_plan_week ON training_plan(week_start);
CREATE INDEX IF NOT EXISTS idx_plan_day ON training_plan(week_start, day_of_week);

-- Full version history for plan changes
CREATE TABLE IF NOT EXISTS training_plan_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_entry_id   INTEGER NOT NULL REFERENCES training_plan(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    previous_data   TEXT NOT NULL,                  -- JSON snapshot of previous state
    change_reason   TEXT,                           -- why the change was made
    changed_by      TEXT DEFAULT 'coach' CHECK (changed_by IN ('coach', 'athlete')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_plan_versions_entry ON training_plan_versions(plan_entry_id);

-- ============================================================
-- COACHING CONVERSATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT,                           -- auto-generated or user-set
    conversation_type TEXT DEFAULT 'general',       -- 'general', 'onboarding', 'plan_build', 'race_discussion', 'weekly_review'
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    token_count     INTEGER,                        -- for context budget tracking
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);

-- ============================================================
-- COACH'S NOTEBOOK
-- ============================================================
CREATE TABLE IF NOT EXISTS coach_notebook (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT NOT NULL,                  -- 'pattern', 'observation', 'preference', 'risk', 'strength'
    content         TEXT NOT NULL,                  -- the observation itself
    evidence        TEXT,                           -- supporting data points
    confidence      TEXT DEFAULT 'medium' CHECK (confidence IN ('low', 'medium', 'high')),
    active          INTEGER DEFAULT 1,             -- boolean: still relevant?
    source_type     TEXT NOT NULL DEFAULT 'conversation'
                    CHECK (source_type IN ('conversation', 'checkin', 'activity', 'system')),
    source_conversation_id INTEGER REFERENCES conversations(id), -- nullable: only set when source_type='conversation'
    source_checkin_id      INTEGER REFERENCES checkins(id),      -- nullable: only set when source_type='checkin'
    source_activity_id     INTEGER REFERENCES activities(id),    -- nullable: only set when source_type='activity'
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_notebook_category ON coach_notebook(category);
CREATE INDEX IF NOT EXISTS idx_notebook_active ON coach_notebook(active);
CREATE INDEX IF NOT EXISTS idx_notebook_source_type ON coach_notebook(source_type);

-- ============================================================
-- WORK LOG (derived from check-ins, queryable separately)
-- ============================================================
CREATE TABLE IF NOT EXISTS work_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL UNIQUE,           -- ISO date
    finish_time     TEXT,                           -- HH:MM
    stress_level    INTEGER CHECK (stress_level BETWEEN 1 AND 10),
    hours_worked    REAL,                           -- for weekly entries
    source_checkin_id INTEGER REFERENCES checkins(id),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_work_log_date ON work_log(date);

-- ============================================================
-- EMAIL REMINDERS CONFIG
-- ============================================================
CREATE TABLE IF NOT EXISTS reminder_config (
    id              INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    email           TEXT,
    weekday_morning_time  TEXT DEFAULT '06:30',
    weekday_evening_time  TEXT DEFAULT '21:00',
    weekend_morning_time  TEXT DEFAULT '09:30',
    weekly_review_time    TEXT DEFAULT '19:00',     -- Sunday evening
    enabled         INTEGER DEFAULT 1,
    smtp_host       TEXT,
    smtp_port       INTEGER DEFAULT 587,
    smtp_user       TEXT,
    smtp_password   TEXT,                           -- encrypted in practice
    from_email      TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ============================================================
-- CONTEXT PRIORITY SYSTEM
-- ============================================================
-- Defines the tiered context window strategy for Claude API calls.
-- When token budget is tight, items are included in priority order.
-- Tier 1 (ALWAYS included, never dropped):
--   - athlete_profile
--   - coach_notebook (active entries)
--   - injuries (active)
--   - current training_phase
--   - current week training_plan
--   - races (upcoming)
-- Tier 2 (included when budget allows, trimmed first):
--   - recent check-ins (last 14 days)
--   - recent activities with weather (last 14 days)
--   - wellness/CTL/ATL/TSB (last 14 days)
--   - work_log trends (last 14 days)
--   - personal_records
--   - daily_weather (last 7 days)
-- Tier 3 (first to drop under pressure):
--   - conversation history (oldest messages dropped first)
--
-- This table stores per-block token budgets and priority weights
-- so the context builder can be tuned without code changes.
CREATE TABLE IF NOT EXISTS context_priority (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    block_name      TEXT NOT NULL UNIQUE,           -- e.g. 'athlete_profile', 'coach_notebook', 'conversation_history'
    tier            INTEGER NOT NULL CHECK (tier BETWEEN 1 AND 3), -- 1=always, 2=preferred, 3=droppable
    priority_order  INTEGER NOT NULL,              -- within tier, lower = higher priority
    max_tokens      INTEGER,                       -- soft cap for this block (NULL = no cap)
    enabled         INTEGER NOT NULL DEFAULT 1,    -- boolean
    description     TEXT
);

-- Seed the priority configuration
INSERT OR IGNORE INTO context_priority (block_name, tier, priority_order, max_tokens, description) VALUES
    ('athlete_profile',       1, 1, NULL,  'Full athlete profile from onboarding — always included'),
    ('coach_notebook',        1, 2, 2000,  'Active coach observations and patterns — always included'),
    ('active_injuries',       1, 3, 500,   'Currently active/monitoring injuries — always included'),
    ('training_phase',        1, 4, 300,   'Current training phase and sport focus — always included'),
    ('current_week_plan',     1, 5, 1500,  'This week''s training plan — always included'),
    ('race_calendar',         1, 6, 500,   'Upcoming races with weeks-to-race — always included'),
    ('recent_checkins',       2, 1, 3000,  'Check-in responses from last 14 days'),
    ('recent_activities',     2, 2, 4000,  'Activities with weather context from last 14 days'),
    ('wellness_trends',       2, 3, 1000,  'CTL/ATL/TSB and wellness from last 14 days'),
    ('work_stress_trends',    2, 4, 800,   'Work log and stress trends from last 14 days'),
    ('personal_records',      2, 5, 500,   'All personal records and benchmarks'),
    ('daily_weather',         2, 6, 400,   'Daily weather from last 7 days'),
    ('conversation_history',  3, 1, 8000,  'Prior conversation messages — oldest dropped first');

-- ============================================================
-- VIEWS — Planned vs Actual Hours
-- ============================================================
-- Weekly planned hours from training plan
CREATE VIEW IF NOT EXISTS v_weekly_planned_hours AS
SELECT
    tp.week_start,
    SUM(tp.target_duration_s) / 3600.0 AS planned_hours,
    COUNT(CASE WHEN tp.is_key_session = 1 THEN 1 END) AS planned_key_sessions,
    COUNT(CASE WHEN tp.is_rest_day = 0 THEN 1 END) AS planned_training_days
FROM training_plan tp
WHERE tp.is_rest_day = 0
GROUP BY tp.week_start;

-- Weekly actual hours from activities
CREATE VIEW IF NOT EXISTS v_weekly_actual_hours AS
SELECT
    -- Derive week_start (Monday) from activity start_time
    date(a.start_time, 'weekday 1', '-7 days') AS week_start,
    SUM(COALESCE(a.duration_s, a.elapsed_s, 0)) / 3600.0 AS actual_hours,
    COUNT(*) AS total_sessions,
    COUNT(CASE WHEN ks.id IS NOT NULL THEN 1 END) AS completed_key_sessions,
    SUM(CASE WHEN a.sport = 'Run' THEN COALESCE(a.duration_s, 0) ELSE 0 END) / 3600.0 AS run_hours,
    SUM(CASE WHEN a.sport = 'Ride' THEN COALESCE(a.duration_s, 0) ELSE 0 END) / 3600.0 AS ride_hours,
    SUM(CASE WHEN a.sport NOT IN ('Run', 'Ride') THEN COALESCE(a.duration_s, 0) ELSE 0 END) / 3600.0 AS other_hours
FROM activities a
LEFT JOIN key_sessions ks ON ks.activity_id = a.id
GROUP BY date(a.start_time, 'weekday 1', '-7 days');

-- Combined planned vs actual per week (the analytics chart query)
CREATE VIEW IF NOT EXISTS v_planned_vs_actual AS
SELECT
    COALESCE(p.week_start, a.week_start) AS week_start,
    COALESCE(p.planned_hours, 0) AS planned_hours,
    COALESCE(a.actual_hours, 0) AS actual_hours,
    COALESCE(a.actual_hours, 0) - COALESCE(p.planned_hours, 0) AS delta_hours,
    CASE
        WHEN COALESCE(p.planned_hours, 0) > 0
        THEN ROUND(COALESCE(a.actual_hours, 0) / p.planned_hours * 100, 1)
        ELSE NULL
    END AS completion_pct,
    COALESCE(p.planned_key_sessions, 0) AS planned_key_sessions,
    COALESCE(a.completed_key_sessions, 0) AS completed_key_sessions,
    COALESCE(a.run_hours, 0) AS run_hours,
    COALESCE(a.ride_hours, 0) AS ride_hours,
    COALESCE(a.other_hours, 0) AS other_hours
FROM v_weekly_planned_hours p
FULL OUTER JOIN v_weekly_actual_hours a ON p.week_start = a.week_start
ORDER BY COALESCE(p.week_start, a.week_start);
