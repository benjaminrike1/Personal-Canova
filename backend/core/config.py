import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "coach.db"))
SCHEMA_PATH = str(BASE_DIR / "schema.sql")

# Intervals.icu
INTERVALS_ATHLETE_ID = os.getenv("INTERVALS_ATHLETE_ID", "")
INTERVALS_API_KEY = os.getenv("INTERVALS_API_KEY", "")
INTERVALS_BASE_URL = "https://intervals.icu/api/v1"

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 4096

# Open-Meteo (no API key required)
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1"

# Email / SMTP
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
REMINDER_EMAIL = os.getenv("REMINDER_EMAIL", "")

# App
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
