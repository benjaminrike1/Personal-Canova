import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from backend.core.config import DATABASE_PATH, SCHEMA_PATH

log = logging.getLogger(__name__)

_db_path = DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables from schema.sql if they don't exist.

    Ensures the parent directory exists (required for Railway persistent volumes
    where DATABASE_PATH may be /data/coach.db and /data is a mounted volume).
    """
    db_dir = Path(_db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    log.info(f"Database path: {_db_path} (dir exists: {db_dir.is_dir()})")

    schema = Path(SCHEMA_PATH).read_text()
    conn = get_connection()
    try:
        conn.executescript(schema)
        conn.commit()
        log.info("Database schema initialized")

        # Run migrations for columns added after initial schema
        _migrate(conn)
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection):
    """Add columns that were introduced after the initial schema."""
    cursor = conn.execute("PRAGMA table_info(activities)")
    cols = {row[1] for row in cursor.fetchall()}

    if "power_source" not in cols:
        conn.execute("ALTER TABLE activities ADD COLUMN power_source TEXT")
        conn.commit()
        log.info("Migration: added power_source column to activities")


def dict_from_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def dicts_from_rows(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]
