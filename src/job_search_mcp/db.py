"""SQLite connection, schema creation, migration from v0.1.0 and synthetic seed loading."""

import csv
import os
import sqlite3
import unicodedata
from datetime import date, datetime
from pathlib import Path

DB_ENV_VAR = "JOB_SEARCH_DB"
# Project root (the directory that holds data/), so paths do not depend on the working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "local" / "job_search.db"
SEED_DIR = PROJECT_ROOT / "data" / "seed"

# Columns of the seed CSV files (still the v0.1.0 format; the import format comes later).
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

# Schema version kept in PRAGMA user_version: 0 is the v0.1.0 database, 2 the v0.2.0 one.
SCHEMA_VERSION = 2

# Dates are stored as ISO 8601 text (YYYY-MM-DD).
# created_at is stored in UTC as "YYYY-MM-DD HH:MM:SS" (the format of CURRENT_TIMESTAMP).
# The tables that can be changed carry `version`, incremented at every write.
# No statement may contain ";" in its text: the script is split on it to run in a transaction.
SCHEMA = """
CREATE TABLE IF NOT EXISTS company (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    sector TEXT,
    priority TEXT CHECK (priority IN ('A', 'B', 'C')),
    job_platform TEXT,
    notes TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES company (id),
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    track TEXT,
    score REAL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS application (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE REFERENCES job (id),
    status TEXT NOT NULL,
    applied_on TEXT,
    last_contact_on TEXT,
    next_step TEXT,
    resume_track TEXT,
    salary_ask TEXT,
    contract_type TEXT,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS application_stage (
    id INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES application (id),
    kind TEXT NOT NULL,
    date TEXT NOT NULL,
    result TEXT,
    feedback TEXT
);

CREATE TABLE IF NOT EXISTS contact (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    company_id INTEGER REFERENCES company (id),
    role_title TEXT,
    relationship TEXT,
    channel TEXT,
    status TEXT NOT NULL,
    next_step TEXT,
    last_contact_on TEXT,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS application_person (
    application_id INTEGER NOT NULL REFERENCES application (id),
    contact_id INTEGER NOT NULL REFERENCES contact (id),
    role TEXT NOT NULL,
    confirmed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (application_id, contact_id, role)
);

CREATE TABLE IF NOT EXISTS interaction (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contact (id),
    date TEXT NOT NULL,
    summary TEXT NOT NULL,
    channel TEXT,
    source_type TEXT
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY,
    entity TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    date TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref TEXT
);

CREATE INDEX IF NOT EXISTS history_record ON history (entity, record_id);
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


def normalize_name(name: str) -> str:
    """Company name used to join companies: lowercase, without accents, trimmed."""
    decomposed = unicodedata.normalize("NFKD", name.strip().lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def ensure_company(connection: sqlite3.Connection, name: str | None) -> int | None:
    """Id of the company with this name (compared by normalized name), creating it if missing.

    A missing or blank name gives None. Does not commit: the caller owns the transaction.
    """
    if name is None or not name.strip():
        return None
    normalized = normalize_name(name)
    row = connection.execute(
        "SELECT id FROM company WHERE normalized_name = ?", (normalized,)
    ).fetchone()
    if row:
        return row[0]
    cursor = connection.execute(
        "INSERT INTO company (name, normalized_name) VALUES (?, ?)", (name.strip(), normalized)
    )
    return cursor.lastrowid


def backup_path(database_file: Path) -> Path:
    """Where a v0.1.0 database is copied before the migration: <name>.v1.bak beside it."""
    return database_file.with_name(database_file.name + ".v1.bak")


def _run_schema(connection: sqlite3.Connection) -> None:
    # executescript would commit first; statement by statement they stay in the transaction.
    for statement in SCHEMA.split(";"):
        if statement.strip():
            connection.execute(statement)


def create_schema(connection: sqlite3.Connection) -> None:
    """Bring the database to the schema version 2 (PRAGMA user_version).

    A new database is created directly in version 2. A v0.1.0 database (version 0 with the
    old tables) is copied to <name>.v1.bak and migrated in a single transaction. A database
    already in version 2 is left as it is, so this is safe to call at every opening. Any
    other version raises sqlite3.DatabaseError.
    """
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version == SCHEMA_VERSION:
        return
    if version != 0:
        raise sqlite3.DatabaseError(
            f"Database schema version {version} is not supported (expected 0 or "
            f"{SCHEMA_VERSION}): use the version of job-search-mcp that created it."
        )
    is_v1 = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'job_history'"
    ).fetchone()
    if is_v1:
        _migrate_from_v1(connection)
        return
    connection.execute("BEGIN")
    try:
        _run_schema(connection)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def _backup(connection: sqlite3.Connection) -> None:
    """Copy the database file to <name>.v1.bak; in-memory and temporary databases have none."""
    file = connection.execute("PRAGMA database_list").fetchone()[2]
    if not file:
        return
    target = sqlite3.connect(backup_path(Path(file)))
    try:
        connection.backup(target)
    finally:
        target.close()


def _insert_job(connection: sqlite3.Connection, job) -> None:
    connection.execute(
        "INSERT INTO job (id, company_id, title, url, track, score, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            job["id"],
            ensure_company(connection, job["company"]),
            job["title"],
            job["url"],
            job["track"],
            job["score"],
            job["created_at"],
        ),
    )


def _insert_contact(connection: sqlite3.Connection, contact) -> None:
    connection.execute(
        "INSERT INTO contact (id, name, company_id, relationship, channel, status, next_step,"
        " last_contact_on) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            contact["id"],
            contact["name"],
            ensure_company(connection, contact["company"]),
            contact["relationship"],
            contact["channel"],
            contact["status"],
            contact["next_step"],
            contact["last_contact_on"],
        ),
    )


def _migrate_from_v1(connection: sqlite3.Connection) -> None:
    """Migrate a v0.1.0 database (version 0) to the version 2 without losing data.

    - The database file is copied to <name>.v1.bak before anything changes.
    - Companies come from the texts of job.company and contact.company, joined by
      normalized name; the name kept is the first one seen (jobs first, then contacts, by id).
    - job keeps what describes the posting; its progress fields go to application (1:1,
      with the same id as the job).
    - contact gets company_id and role_title; contact.job_id becomes an application_person
      link with role 'contact' and confirmed true.
    - job_history goes to history with entity 'application', source_type 'user' and the
      original free text of source in source_ref.
    Everything runs in one transaction: on any failure the database stays in version 0.
    """
    _backup(connection)
    # Foreign keys can only be switched off outside a transaction. legacy_alter_table keeps
    # interaction pointing to the name "contact" when the old table is renamed.
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("PRAGMA legacy_alter_table = ON")
    connection.execute("BEGIN")
    try:
        connection.execute("ALTER TABLE job RENAME TO job_v1")
        connection.execute("ALTER TABLE contact RENAME TO contact_v1")
        connection.execute("ALTER TABLE interaction ADD COLUMN channel TEXT")
        connection.execute("ALTER TABLE interaction ADD COLUMN source_type TEXT")
        _run_schema(connection)
        for job in connection.execute("SELECT * FROM job_v1 ORDER BY id").fetchall():
            _insert_job(connection, job)
        connection.execute(
            "INSERT INTO application (id, job_id, status, applied_on, last_contact_on, next_step)"
            " SELECT id, id, status, applied_on, last_contact_on, next_step FROM job_v1"
        )
        for contact in connection.execute("SELECT * FROM contact_v1 ORDER BY id").fetchall():
            _insert_contact(connection, contact)
        links = connection.execute(
            "INSERT INTO application_person (application_id, contact_id, role, confirmed)"
            " SELECT application.id, contact_v1.id, 'contact', 1 FROM contact_v1"
            " JOIN application ON application.job_id = contact_v1.job_id"
        ).rowcount
        lines = connection.execute(
            "INSERT INTO history (entity, record_id, field, old_value, new_value, date,"
            " source_type, source_ref)"
            " SELECT 'application', application.id, field, old_value, new_value, date,"
            " 'user', source FROM job_history"
            " JOIN application ON application.job_id = job_history.job_id"
            " ORDER BY job_history.id"
        ).rowcount
        # A link or history line pointing to a missing job would be dropped by the joins.
        expected = connection.execute(
            "SELECT (SELECT COUNT(*) FROM contact_v1 WHERE job_id IS NOT NULL),"
            " (SELECT COUNT(*) FROM job_history)"
        ).fetchone()
        if (links, lines) != tuple(expected):
            raise sqlite3.IntegrityError(
                "The v0.1.0 database has links or history lines pointing to missing jobs."
            )
        for table in ("job_history", "job_v1", "contact_v1"):
            connection.execute(f"DROP TABLE {table}")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise sqlite3.IntegrityError("The migrated database has broken references.")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA legacy_alter_table = OFF")
        connection.execute("PRAGMA foreign_keys = ON")


def _read_csv(path: Path, columns: tuple[str, ...]) -> list[dict]:
    """Read a seed CSV as dicts with the given columns, turning empty cells into NULL."""
    with path.open(encoding="utf-8", newline="") as file:
        return [{column: row[column] or None for column in columns} for row in csv.DictReader(file)]


def load_seed(connection: sqlite3.Connection, seed_dir: Path = SEED_DIR) -> None:
    """Insert the synthetic demo jobs and contacts from the seed CSV files.

    The CSV files keep the v0.1.0 format: each job row becomes a company (joined by
    normalized name), a job and its application; each contact row a person, whose job_id
    becomes a link with role 'contact'. Meant for an empty database only: it is not
    idempotent. The seed rows carry fixed ids and unique URLs, so a second load raises
    sqlite3.IntegrityError. Everything is inserted in a single transaction, so a failed load
    leaves no partial data behind.
    """
    jobs = _read_csv(seed_dir / "jobs.csv", JOB_COLUMNS)
    contacts = _read_csv(seed_dir / "contacts.csv", CONTACT_COLUMNS)
    with connection:
        for job in jobs:
            _insert_job(connection, job)
            connection.execute(
                "INSERT INTO application (job_id, status, applied_on, last_contact_on, next_step)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    job["id"],
                    job["status"],
                    job["applied_on"],
                    job["last_contact_on"],
                    job["next_step"],
                ),
            )
        for contact in contacts:
            _insert_contact(connection, contact)
            if contact["job_id"]:
                cursor = connection.execute(
                    "INSERT INTO application_person (application_id, contact_id, role, confirmed)"
                    " SELECT id, ?, 'contact', 1 FROM application WHERE job_id = ?",
                    (contact["id"], contact["job_id"]),
                )
                if cursor.rowcount != 1:
                    raise sqlite3.IntegrityError(
                        f"Seed contact {contact['id']} points to unknown job {contact['job_id']}."
                    )
