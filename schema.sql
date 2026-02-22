-- Coach App — Full Database Schema
-- SQLite with strict typing where possible
-- All timestamps stored as ISO 8601 UTC strings
-- All distances in meters, durations in seconds, weights in kg

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- ATHLETE PROFILE (single row — one athlete app)
-- ============================================================
CREATE TABLE athlete_profile (
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
CREATE TABLE personal_records (
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

CREATE INDEX idx_pr_discipline ON personal_records(discipline);
CREATE INDEX idx_pr_event ON personal_records(event);

-- ============================================================
-- RACE CALENDAR
-- ============================================================
CREATE TABLE races (
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
    status          TEXT NOT NULL DEFAULT 'upcoming' CHECK (status IN ('upcoming', 'completed', 'dns', 'dnf', 'cancelled')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_races_date ON races(date);
CREATE INDEX idx_races_priority ON races(priority);

-- ============================================================
-- ACTIVITIES (synced from Intervals.icu)
-- ============================================================
CREATE TABLE activities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    intervals_id    TEXT UNIQUE,                   -- Intervals.icu activity ID
    sport           TEXT NOT NULL,                 -- 'Run', 'Ride', 'Swim', etc.
    name            TEXT,
    start_time      TEXT NOT NULL,                 -- ISO 8601
    duration_s      REAL,                          -- moving time in seconds
    elapsed_s       REAL,                          -- elapsed time
    distance_m      REAL,
    avg_hr          REAL,
    max_hr          REAL,
    avg_pace_s_km   REAL,                          -- seconds per km (running)
    avg_power       REAL,                          -- watts (cycling or Stryd)
    np              REAL,                          -- normalized power
    tss             REAL,                          -- training stress score
    intensity_factor REAL,
    avg_cadence     REAL,
    elevation_gain  REAL,                          -- meters
    calories        REAL,
    training_load   REAL,                          -- Intervals.icu training load
    has_stryd_power INTEGER DEFAULT 0,             -- boolean: Stryd data available
    intervals_data  TEXT,                          -- JSON: raw intervals/laps from API
    zone_time       TEXT,                          -- JSON: time-in-zone breakdown
    source          TEXT DEFAULT 'intervals',      -- 'intervals' / 'manual'
    synced_at       TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_activities_sport ON activities(sport);
CREATE INDEX idx_activities_start ON activities(start_time);
CREATE INDEX idx_activities_intervals_id ON activities(intervals_id);

-- ============================================================
-- WEATHER CACHE (per activity)
-- ============================================================
CREATE TABLE weather_cache (
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

CREATE INDEX idx_weather_activity ON weather_cache(activity_id);

-- ============================================================
-- WELLNESS (synced from Intervals.icu)
-- ============================================================
CREATE TABLE wellness (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL UNIQUE,           -- ISO date
    ctl             REAL,                          -- chronic training load
    atl             REAL,                          -- acute training load
    tsb             REAL,                          -- training stress balance
    resting_hr      REAL,
    hrv             REAL,
    weight_kg       REAL,
    sleep_quality   REAL,                          -- from Intervals.icu if available
    source          TEXT DEFAULT 'intervals',
    synced_at       TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_wellness_date ON wellness(date);

-- ============================================================
-- CHECK-INS (morning / evening / weekend / weekly)
-- ============================================================
CREATE TABLE checkins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,                  -- ISO date
    type            TEXT NOT NULL CHECK (type IN ('morning', 'evening', 'weekend', 'weekly')),

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

CREATE INDEX idx_checkins_date ON checkins(date);
CREATE INDEX idx_checkins_type ON checkins(type, date);

-- Per-session RPE within a check-in (supports two-a-days)
CREATE TABLE session_checkins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    checkin_id      INTEGER NOT NULL REFERENCES checkins(id) ON DELETE CASCADE,
    activity_id     INTEGER REFERENCES activities(id),
    session_type    TEXT,                           -- auto-filled from Intervals.icu
    rpe             INTEGER CHECK (rpe BETWEEN 1 AND 10),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_session_checkins_checkin ON session_checkins(checkin_id);

-- ============================================================
-- INJURY LOG
-- ============================================================
CREATE TABLE injuries (
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

CREATE INDEX idx_injuries_status ON injuries(status);
CREATE INDEX idx_injuries_body_part ON injuries(body_part);

-- Injury severity history (daily tracking from check-ins)
CREATE TABLE injury_updates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    injury_id       INTEGER NOT NULL REFERENCES injuries(id) ON DELETE CASCADE,
    date            TEXT NOT NULL,                  -- ISO date
    severity        INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 10),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_injury_updates_injury ON injury_updates(injury_id, date);

-- ============================================================
-- KEY SESSIONS
-- ============================================================
CREATE TABLE key_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id     INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    session_type    TEXT NOT NULL,                  -- 'threshold_run', 'long_run', 'race_specific', 'tempo', 'interval', 'ftp_test', etc.
    tagged_by       TEXT NOT NULL DEFAULT 'athlete' CHECK (tagged_by IN ('athlete', 'coach')),
    performance_notes TEXT,                         -- coach's assessment
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(activity_id)
);

CREATE INDEX idx_key_sessions_type ON key_sessions(session_type);
CREATE INDEX idx_key_sessions_activity ON key_sessions(activity_id);

-- ============================================================
-- TRAINING PLAN
-- ============================================================
CREATE TABLE training_plan (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start      TEXT NOT NULL,                  -- ISO date (Monday)
    day_of_week     INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6), -- 0=Monday
    session_order   INTEGER NOT NULL DEFAULT 1,     -- for two-a-days: 1, 2
    session_type    TEXT NOT NULL,                  -- 'easy_run', 'threshold', 'long_run', 'rest', 'ride', etc.
    target_duration_s REAL,                         -- planned duration in seconds
    target_intensity TEXT,                          -- zone or description: 'Z2', 'threshold', '10k pace'
    key_objective   TEXT,                           -- one sentence
    is_key_session  INTEGER DEFAULT 0,             -- boolean
    is_rest_day     INTEGER DEFAULT 0,             -- boolean
    completed       INTEGER DEFAULT 0,             -- boolean
    actual_activity_id INTEGER REFERENCES activities(id),
    deviation_notes TEXT,                           -- what changed and why
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_plan_week ON training_plan(week_start);
CREATE INDEX idx_plan_day ON training_plan(week_start, day_of_week);

-- Full version history for plan changes
CREATE TABLE training_plan_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_entry_id   INTEGER NOT NULL REFERENCES training_plan(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    previous_data   TEXT NOT NULL,                  -- JSON snapshot of previous state
    change_reason   TEXT,                           -- why the change was made
    changed_by      TEXT DEFAULT 'coach' CHECK (changed_by IN ('coach', 'athlete')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_plan_versions_entry ON training_plan_versions(plan_entry_id);

-- ============================================================
-- COACHING CONVERSATIONS
-- ============================================================
CREATE TABLE conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT,                           -- auto-generated or user-set
    conversation_type TEXT DEFAULT 'general',       -- 'general', 'onboarding', 'plan_build', 'race_discussion', 'weekly_review'
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    token_count     INTEGER,                        -- for context budget tracking
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);

-- ============================================================
-- COACH'S NOTEBOOK
-- ============================================================
CREATE TABLE coach_notebook (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT NOT NULL,                  -- 'pattern', 'observation', 'preference', 'risk', 'strength'
    content         TEXT NOT NULL,                  -- the observation itself
    evidence        TEXT,                           -- supporting data points
    confidence      TEXT DEFAULT 'medium' CHECK (confidence IN ('low', 'medium', 'high')),
    active          INTEGER DEFAULT 1,             -- boolean: still relevant?
    source_conversation_id INTEGER REFERENCES conversations(id),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_notebook_category ON coach_notebook(category);
CREATE INDEX idx_notebook_active ON coach_notebook(active);

-- ============================================================
-- WORK LOG (derived from check-ins, queryable separately)
-- ============================================================
CREATE TABLE work_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL UNIQUE,           -- ISO date
    finish_time     TEXT,                           -- HH:MM
    stress_level    INTEGER CHECK (stress_level BETWEEN 1 AND 10),
    hours_worked    REAL,                           -- for weekly entries
    source_checkin_id INTEGER REFERENCES checkins(id),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX idx_work_log_date ON work_log(date);

-- ============================================================
-- EMAIL REMINDERS CONFIG
-- ============================================================
CREATE TABLE reminder_config (
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
