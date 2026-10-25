"""Migration of a v0.1.0 database (schema version 0) to the version 2."""

import sqlite3
from pathlib import Path

import pytest

from job_search_mcp import contacts, db, jobs

SCHEMA_V1 = (Path(__file__).parent / "fixtures" / "schema_v1.sql").read_text(encoding="utf-8")

# Extra synthetic rows on top of the seed: a contact whose company differs from a job's only
# in case, accents and spaces, a contact without company, interactions and job history.
EXTRA_CONTACTS = [
    (
        9,
        "Igor Variante",
        "  banco ÁURORA ",
        "Recrutador",
        "email",
        "awaiting_reply",
        None,
        "2026-03-10",
        1,
    ),
    (10, "Júlia Sem Empresa", None, "Amiga", "whatsapp", "to_contact", None, None, None),
]
INTERACTIONS = [(1, "2026-03-08", "Pediu indicação"), (2, "2026-03-11", "Combinou horários")]
JOB_HISTORY = [
    (1, "2026-03-02", "status", "to_apply", "applied", "user"),
    (1, "2026-03-09", "last_contact_on", None, "2026-03-09", "contact_interaction"),
    (5, "2026-03-04", "status", "applied", "tech_interview", "E-mail do recrutador"),
]


def create_v1_database(path: Path) -> None:
    """A database as v0.1.0 left it: old schema, the seed loaded the old way and extra rows."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_V1)
        job_rows = [
            tuple(row.values()) for row in db._read_csv(db.SEED_DIR / "jobs.csv", db.JOB_COLUMNS)
        ]
        contact_rows = [
            tuple(row.values())
            for row in db._read_csv(db.SEED_DIR / "contacts.csv", db.CONTACT_COLUMNS)
        ]
        with conn:
            conn.executemany(f"INSERT INTO job VALUES ({', '.join('?' * 11)})", job_rows)
            conn.executemany(
                f"INSERT INTO contact VALUES ({', '.join('?' * 9)})", contact_rows + EXTRA_CONTACTS
            )
            conn.executemany(
                "INSERT INTO interaction (contact_id, date, summary) VALUES (?, ?, ?)",
                INTERACTIONS,
            )
            conn.executemany(
                "INSERT INTO job_history (job_id, date, field, old_value, new_value, source)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                JOB_HISTORY,
            )
    finally:
        conn.close()


def count(connection, table):
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def user_version(connection):
    return connection.execute("PRAGMA user_version").fetchone()[0]


@pytest.fixture
def v1_path(tmp_path):
    path = tmp_path / "job_search.db"
    create_v1_database(path)
    return path


@pytest.fixture
def migrated(v1_path):
    conn = db.connect(v1_path)
    db.create_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def fresh(tmp_path):
    """A v0.2.0 database created new, with the seed: what the migration must match."""
    conn = db.connect(tmp_path / "fresh.db")
    db.create_schema(conn)
    db.load_seed(conn)
    yield conn
    conn.close()


def test_migration_reaches_version_2_and_keeps_every_row(migrated):
    assert user_version(migrated) == 2
    assert count(migrated, "job") == 15
    assert count(migrated, "application") == 15
    assert count(migrated, "contact") == 10
    assert count(migrated, "interaction") == 2
    assert count(migrated, "history") == 3
    tables = {
        row[0] for row in migrated.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert "job_history" not in tables
    assert not {"job_v1", "contact_v1"} & tables
    assert migrated.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert migrated.execute("PRAGMA foreign_key_check").fetchall() == []


def test_migration_copies_the_database_before_changing_it(v1_path, migrated):
    backup = v1_path.with_name("job_search.db.v1.bak")
    assert db.backup_path(v1_path) == backup
    copy = sqlite3.connect(backup)
    try:
        assert user_version(copy) == 0
        assert count(copy, "job_history") == 3
        assert count(copy, "contact") == 10
    finally:
        copy.close()


def test_migration_joins_companies_by_normalized_name(migrated):
    # 15 job companies plus Consultoria Tangará; "  banco ÁURORA " joins Banco Aurora.
    assert count(migrated, "company") == 16
    igor = contacts.get_contact(migrated, 9)
    assert igor["company"] == "Banco Aurora"
    assert igor["company_id"] == jobs.get_job(migrated, 1)["company_id"]
    assert contacts.get_contact(migrated, 10)["company"] is None
    assert contacts.get_contact(migrated, 10)["company_id"] is None
    banco = [c["id"] for c in contacts.list_contacts(migrated, company="BANCO AURORA")]
    assert banco == [1, 9]


def test_migration_moves_job_links_to_application_person(migrated):
    links = migrated.execute(
        "SELECT application.job_id, contact_id, role, confirmed FROM application_person"
        " JOIN application ON application.id = application_id ORDER BY contact_id"
    ).fetchall()
    assert [tuple(link) for link in links] == [
        (1, 1, "contact", 1),
        (2, 2, "contact", 1),
        (5, 3, "contact", 1),
        (11, 4, "contact", 1),
        (8, 5, "contact", 1),
        (13, 6, "contact", 1),
        (1, 9, "contact", 1),
    ]
    assert contacts.get_contact(migrated, 9)["job_id"] == 1
    assert contacts.get_contact(migrated, 7)["job_id"] is None


def test_migration_moves_job_history_with_the_free_source_as_reference(migrated):
    lines = migrated.execute(
        "SELECT entity, record_id, field, old_value, new_value, date, source_type, source_ref"
        " FROM history ORDER BY id"
    ).fetchall()
    assert [tuple(line) for line in lines] == [
        ("application", 1, "status", "to_apply", "applied", "2026-03-02", "user", "user"),
        (
            "application",
            1,
            "last_contact_on",
            None,
            "2026-03-09",
            "2026-03-09",
            "user",
            "contact_interaction",
        ),
        (
            "application",
            5,
            "status",
            "applied",
            "tech_interview",
            "2026-03-04",
            "user",
            "E-mail do recrutador",
        ),
    ]


def test_migrated_interactions_keep_their_data_and_gain_empty_columns(migrated):
    rows = [dict(row) for row in migrated.execute("SELECT * FROM interaction ORDER BY id")]
    assert rows == [
        {
            "id": 1,
            "contact_id": 1,
            "date": "2026-03-08",
            "summary": "Pediu indicação",
            "channel": None,
            "source_type": None,
        },
        {
            "id": 2,
            "contact_id": 2,
            "date": "2026-03-11",
            "summary": "Combinou horários",
            "channel": None,
            "source_type": None,
        },
    ]


def test_migrated_reads_match_a_new_database_with_the_same_seed(migrated, fresh):
    assert jobs.list_jobs(migrated) == jobs.list_jobs(fresh)
    assert contacts.list_contacts(migrated)[:8] == contacts.list_contacts(fresh)


def test_migrated_database_accepts_writes(migrated):
    result = jobs.update_job(migrated, 2, "user", "2026-03-16", status="in_review")
    assert result["job"]["status"] == "in_review"
    assert count(migrated, "history") == 4
    added = jobs.add_job(migrated, "Banco Aurora", "Analista", "https://vagas.example.com/x")
    assert added["company_id"] == jobs.get_job(migrated, 1)["company_id"]


def test_opening_again_does_not_migrate_twice(v1_path, migrated):
    backup = db.backup_path(v1_path)
    backup.unlink()
    db.create_schema(migrated)
    reopened = db.connect(v1_path)
    try:
        db.create_schema(reopened)
        assert user_version(reopened) == 2
        assert count(reopened, "job") == 15
        assert count(reopened, "history") == 3
    finally:
        reopened.close()
    assert not backup.exists()


def test_failed_migration_leaves_the_v1_database_untouched(tmp_path):
    path = tmp_path / "broken.db"
    create_v1_database(path)
    conn = sqlite3.connect(path)
    with conn:
        # Only possible with foreign keys off: a history line of a job that does not exist.
        conn.execute(
            "INSERT INTO job_history (job_id, date, field, old_value, new_value, source)"
            " VALUES (999, '2026-03-01', 'status', 'a', 'b', 'user')"
        )
    conn.close()
    conn = db.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="missing jobs"):
            db.create_schema(conn)
        assert user_version(conn) == 0
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert tables == {"job", "contact", "interaction", "job_history"}
        assert count(conn, "job_history") == 4
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()
    assert db.backup_path(path).exists()


def test_in_memory_v1_database_migrates_without_backup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA_V1)
        conn.execute(
            "INSERT INTO job (company, title, url, status) VALUES ('Banco Aurora', 'DE', 'u', 'applied')"
        )
        conn.commit()
        db.create_schema(conn)
        assert user_version(conn) == 2
        assert jobs.get_job(conn, 1)["company"] == "Banco Aurora"
    finally:
        conn.close()
    assert not list(tmp_path.iterdir())
