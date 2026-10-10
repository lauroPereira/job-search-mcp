"""SQLite connection, schema creation and synthetic seed loading."""

import csv
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_ENV_VAR = "JOB_SEARCH_DB"
# Project root (the directory that holds data/), so paths do not depend on the working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "local" / "job_search.db"
SEED_DIR = PROJECT_ROOT / "data" / "seed"

JOB_COLUMNS = (
    "id",
    "company",
    "title",
    "url",
    "track",
    "score",
    "status",
    "next_step",
    "applied_on",
    "last_contact_on",
    "created_at",
)
CONTACT_COLUMNS = (
    "id",
    "name",
    "company",
    "relationship",
    "channel",
    "status",
    "next_step",
    "last_contact_on",
    "job_id",
)

# Dates are stored as ISO 8601 text (YYYY-MM-DD).
# created_at is stored in UTC as "YYYY-MM-DD HH:MM:SS" (the format of CURRENT_TIMESTAMP).
SCHEMA = """
CREATE TABLE IF NOT EXISTS job (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    track TEXT,
    score REAL,
    status TEXT NOT NULL,
    next_step TEXT,
    applied_on TEXT,
    last_contact_on TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contact (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT,
    relationship TEXT,
    channel TEXT,
    status TEXT NOT NULL,
    next_step TEXT,
    last_contact_on TEXT,
    job_id INTEGER REFERENCES job (id)
);

CREATE TABLE IF NOT EXISTS interaction (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contact (id),
    date TEXT NOT NULL,
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_history (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES job (id),
    date TEXT NOT NULL,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    source TEXT NOT NULL
);
"""


def to_date(value: str | date | None) -> date | None:
    """Convert a stored ISO 8601 text (YYYY-MM-DD) into a date; the single conversion point.

    Dates pass through unchanged, a datetime loses its time and None stays None. Invalid
    text raises ValueError and a value of another type raises TypeError.
    """
    if value is None:
        return None
    # datetime is a subclass of date: checked first, so the time never reaches the database.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def default_db_path() -> Path:
    """Return the database path from JOB_SEARCH_DB, or data/local/ under the project root."""
    return Path(os.environ.get(DB_ENV_VAR) or DEFAULT_DB_PATH)


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open the SQLite database with foreign keys enabled and rows accessible by name."""
    db_path = Path(path) if path is not None else default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the job, contact, interaction and job_history tables if they do not exist."""
    connection.executescript(SCHEMA)


def _read_csv(path: Path, columns: tuple[str, ...]) -> list[tuple]:
    """Read a seed CSV as tuples in column order, turning empty cells into NULL."""
    with path.open(encoding="utf-8", newline="") as file:
        return [tuple(row[column] or None for column in columns) for row in csv.DictReader(file)]


def _insert(connection: sqlite3.Connection, table: str, columns: tuple[str, ...], rows) -> None:
    placeholders = ", ".join("?" for _ in columns)
    connection.executemany(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", rows
    )


def load_seed(connection: sqlite3.Connection, seed_dir: Path = SEED_DIR) -> None:
    """Insert the synthetic demo jobs and contacts from the seed CSV files.

    Meant for an empty database only: it is not idempotent. The seed rows carry fixed ids
    and unique URLs, so a second load raises sqlite3.IntegrityError. Jobs and contacts are
    inserted in a single transaction, so a failed load leaves no partial data behind.
    """
    jobs = _read_csv(seed_dir / "jobs.csv", JOB_COLUMNS)
    contacts = _read_csv(seed_dir / "contacts.csv", CONTACT_COLUMNS)
    with connection:
        _insert(connection, "job", JOB_COLUMNS, jobs)
        _insert(connection, "contact", CONTACT_COLUMNS, contacts)
