import sqlite3
from contextlib import contextmanager
from pathlib import Path

from backend.core.config import DATABASE_PATH, SCHEMA_PATH

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
    """Create all tables from schema.sql if they don't exist."""
    schema = Path(SCHEMA_PATH).read_text()
    conn = get_connection()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def dict_from_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def dicts_from_rows(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]
