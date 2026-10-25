"""SQLite connection, schema creation, migration from v0.1.0 and synthetic seed loading."""

import csv
import os
import sqlite3
import sys
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
    """Company name used to join companies: lowercase, without accents, trimmed and with
    inner runs of spaces collapsed into one."""
    decomposed = unicodedata.normalize("NFKD", name.lower())
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(unaccented.split())


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
    """A free path for the copy of a v0.1.0 database: <name>.v1.bak beside it, or
    <name>.v1.1.bak, <name>.v1.2.bak... when it is taken, so no copy is ever overwritten."""
    path = database_file.with_name(database_file.name + ".v1.bak")
    number = 0
    while path.exists():
        number += 1
        path = database_file.with_name(f"{database_file.name}.v1.{number}.bak")
    return path


def _run_schema(connection: sqlite3.Connection) -> None:
    # executescript would commit first; statement by statement they stay in the transaction.
    for statement in SCHEMA.split(";"):
        if statement.strip():
            connection.execute(statement)


def _user_version(connection: sqlite3.Connection) -> int:
    return connection.execute("PRAGMA user_version").fetchone()[0]


def create_schema(connection: sqlite3.Connection) -> None:
    """Bring the database to the schema version 2 (PRAGMA user_version).

    A new database is created directly in version 2. A v0.1.0 database (version 0 with the
    old tables) is copied to <name>.v1.bak and migrated in a single transaction; the
    migration report (backup path and joined or renamed companies) goes to stderr, never to
    stdout, which carries the MCP protocol. A database already in version 2 is left as it
    is, so this is safe to call at every opening. Any other version raises
    sqlite3.DatabaseError.

    The version is read again under the write lock (BEGIN IMMEDIATE): when two processes
    open the same v0.1.0 database at once, only the first one copies and migrates it.
    """
    if _user_version(connection) == SCHEMA_VERSION:
        return
    # Foreign keys can only be switched off outside a transaction. legacy_alter_table keeps
    # interaction pointing to the name "contact" when the old table is renamed.
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("PRAGMA legacy_alter_table = ON")
    report = []
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            version = _user_version(connection)
            if version == 0:
                is_v1 = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'job_history'"
                ).fetchone()
                if is_v1:
                    report = _migrate_from_v1(connection)
                else:
                    _run_schema(connection)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            elif version != SCHEMA_VERSION:
                raise sqlite3.DatabaseError(
                    f"Database schema version {version} is not supported (expected 0 or "
                    f"{SCHEMA_VERSION}): use the version of job-search-mcp that created it."
                )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    finally:
        connection.execute("PRAGMA legacy_alter_table = OFF")
        connection.execute("PRAGMA foreign_keys = ON")
    for line in report:
        print(line, file=sys.stderr)


def _backup(connection: sqlite3.Connection) -> Path | None:
    """Copy the database to a free <name>.v1.bak path and return it; in-memory and
    temporary databases have no file and get no copy (None)."""
    file = connection.execute("PRAGMA database_list").fetchone()[2]
    if not file:
        return None
    path = backup_path(Path(file))
    # The caller holds the write lock (BEGIN IMMEDIATE), so the copy is read through a
    # second connection: it sees the committed database, which nobody else can change now.
    source = sqlite3.connect(file)
    target = sqlite3.connect(path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return path


def _insert_job(connection: sqlite3.Connection, job, company_id: int | None) -> None:
    connection.execute(
        "INSERT INTO job (id, company_id, title, url, track, score, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            job["id"],
            company_id,
            job["title"],
            job["url"],
            job["track"],
            job["score"],
            job["created_at"],
        ),
    )


def _insert_contact(connection: sqlite3.Connection, contact, company_id: int | None) -> None:
    connection.execute(
        "INSERT INTO contact (id, name, company_id, relationship, channel, status, next_step,"
        " last_contact_on) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            contact["id"],
            contact["name"],
            company_id,
            contact["relationship"],
            contact["channel"],
            contact["status"],
            contact["next_step"],
            contact["last_contact_on"],
        ),
    )


def _migrate_from_v1(connection: sqlite3.Connection) -> list[str]:
    """Migrate a v0.1.0 database (version 0) to the version 2 without losing data.

    Runs inside the caller's transaction, with foreign keys off; returns the report lines.
    - The database is copied to a free <name>.v1.bak path before anything changes.
    - Companies come from the texts of job.company and contact.company, joined by
      normalized name; the name kept is the first one seen (jobs first, then contacts, by id).
      Every text stored under another name (joined or trimmed) is reported.
    - job keeps what describes the posting; its progress fields go to application (1:1,
      with the same id as the job).
    - contact gets company_id and role_title; contact.job_id becomes an application_person
      link with role 'contact' and confirmed true.
    - job_history goes to history with entity 'application', source_type 'user' and the
      original free text of source in source_ref.
    A link or history line pointing to a missing job stops the migration, naming the ids.
    """
    backup = _backup(connection)
    report = [f"Migrating the database to schema version {SCHEMA_VERSION}; copy at {backup}."]
    orphan_contacts = [
        row[0]
        for row in connection.execute(
            "SELECT id FROM contact WHERE job_id IS NOT NULL"
            " AND job_id NOT IN (SELECT id FROM job) ORDER BY id"
        )
    ]
    orphan_lines = [
        row[0]
        for row in connection.execute(
            "SELECT id FROM job_history WHERE job_id NOT IN (SELECT id FROM job) ORDER BY id"
        )
    ]
    if orphan_contacts or orphan_lines:
        raise sqlite3.IntegrityError(
            "The v0.1.0 database points to missing jobs (contact ids "
            f"{orphan_contacts}, job_history ids {orphan_lines}); nothing was migrated. "
            f"Fix them and open it again; a copy is at {backup}."
        )

    joined = {}

    def company_id(text: str | None) -> int | None:
        found = ensure_company(connection, text)
        if found is not None:
            row = connection.execute("SELECT name FROM company WHERE id = ?", (found,))
            name = row.fetchone()[0]
            if text != name:
                joined[text] = name
        return found

    connection.execute("ALTER TABLE job RENAME TO job_v1")
    connection.execute("ALTER TABLE contact RENAME TO contact_v1")
    connection.execute("ALTER TABLE interaction ADD COLUMN channel TEXT")
    connection.execute("ALTER TABLE interaction ADD COLUMN source_type TEXT")
    _run_schema(connection)
    for job in connection.execute("SELECT * FROM job_v1 ORDER BY id").fetchall():
        _insert_job(connection, job, company_id(job["company"]))
    connection.execute(
        "INSERT INTO application (id, job_id, status, applied_on, last_contact_on, next_step)"
        " SELECT id, id, status, applied_on, last_contact_on, next_step FROM job_v1"
    )
    for contact in connection.execute("SELECT * FROM contact_v1 ORDER BY id").fetchall():
        _insert_contact(connection, contact, company_id(contact["company"]))
    connection.execute(
        "INSERT INTO application_person (application_id, contact_id, role, confirmed)"
        " SELECT application.id, contact_v1.id, 'contact', 1 FROM contact_v1"
        " JOIN application ON application.job_id = contact_v1.job_id"
    )
    connection.execute(
        "INSERT INTO history (entity, record_id, field, old_value, new_value, date,"
        " source_type, source_ref)"
        " SELECT 'application', application.id, field, old_value, new_value, date,"
        " 'user', source FROM job_history"
        " JOIN application ON application.job_id = job_history.job_id"
        " ORDER BY job_history.id"
    )
    for table in ("job_history", "job_v1", "contact_v1"):
        connection.execute(f"DROP TABLE {table}")
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise sqlite3.IntegrityError(
            f"The migrated database has broken references; nothing was migrated. A copy is "
            f"at {backup}."
        )
    report += [f"Company {text!r} stored as {name!r}." for text, name in joined.items()]
    return report


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
            _insert_job(connection, job, ensure_company(connection, job["company"]))
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
            company_id = ensure_company(connection, contact["company"])
            _insert_contact(connection, contact, company_id)
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
