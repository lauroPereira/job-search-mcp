import sqlite3
from pathlib import Path

import pytest

from job_search_mcp import db

EXPECTED_JOBS_BY_STATUS = {
    "applied": 2,
    "blocked": 1,
    "closed": 1,
    "hired": 1,
    "hr_interview": 1,
    "in_review": 1,
    "manager_interview": 1,
    "offer": 1,
    "rejected": 1,
    "suggested": 1,
    "tech_interview": 1,
    "to_apply": 2,
    "withdrawn": 1,
}
EXPECTED_CONTACTS_BY_STATUS = {
    "awaiting_reply": 1,
    "closed": 1,
    "in_conversation": 2,
    "referred": 1,
    "resume_sent": 1,
    "to_contact": 2,
}


def count(connection, table):
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def count_by_status(connection, table):
    rows = connection.execute(f"SELECT status, COUNT(*) AS total FROM {table} GROUP BY status")
    return {row["status"]: row["total"] for row in rows}


def test_create_schema_creates_the_version_2_tables(tmp_path):
    conn = db.connect(tmp_path / "empty.db")
    try:
        db.create_schema(conn)
        db.create_schema(conn)  # safe to run again on an existing database
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()
    assert tables == {
        "company",
        "job",
        "application",
        "application_stage",
        "application_person",
        "contact",
        "interaction",
        "history",
        "proposal",
    }
    assert version == db.SCHEMA_VERSION == 2
    assert not list(tmp_path.glob("*.bak"))  # a new database is not migrated


def test_connect_enables_foreign_keys_and_named_rows(connection):
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    job = connection.execute("SELECT * FROM job WHERE id = 1").fetchone()
    assert job["title"] == "Data Engineer"


def test_connect_creates_missing_parent_directory(tmp_path):
    path = tmp_path / "nested" / "local" / "job_search.db"
    conn = db.connect(path)
    conn.close()
    assert path.is_file()


def test_seed_loads_expected_counts(connection):
    assert count(connection, "job") == 15
    assert count(connection, "contact") == 8
    assert count(connection, "interaction") == 0
    assert count(connection, "application") == 15
    assert count(connection, "company") == 16  # 15 job companies plus Consultoria Tangará
    assert count(connection, "history") == 0
    assert count_by_status(connection, "application") == EXPECTED_JOBS_BY_STATUS
    assert count_by_status(connection, "contact") == EXPECTED_CONTACTS_BY_STATUS


def test_seed_empty_cells_become_null_and_links_resolve(connection):
    application = connection.execute("SELECT * FROM application WHERE job_id = 2").fetchone()
    assert application["applied_on"] == "2026-03-11"
    assert application["last_contact_on"] is None
    links = connection.execute(
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
    ]
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_duplicate_url_is_rejected(connection):
    url = connection.execute("SELECT url FROM job WHERE id = 1").fetchone()["url"]
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO job (company_id, title, url) VALUES (?, ?, ?)",
            (1, "Data Engineer", url),
        )
    assert count(connection, "job") == 15


def test_job_without_url_is_rejected(connection):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO job (company_id, title) VALUES (?, ?)",
            (1, "Data Engineer"),
        )
    assert count(connection, "job") == 15


def test_second_seed_load_fails_and_keeps_the_first_load(connection):
    with pytest.raises(sqlite3.IntegrityError):
        db.load_seed(connection)
    assert count(connection, "job") == 15
    assert count(connection, "contact") == 8


def test_failed_seed_load_leaves_no_partial_data(tmp_path):
    conn = db.connect(tmp_path / "conflict.db")
    try:
        db.create_schema(conn)
        # A contact that collides with the seed makes the load fail after the jobs are inserted.
        conn.execute("INSERT INTO contact (id, name, status) VALUES (1, 'Ana Exemplo', 'closed')")
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db.load_seed(conn)
        assert count(conn, "job") == 0
        assert count(conn, "contact") == 1
    finally:
        conn.close()


def test_contact_link_to_unknown_application_is_rejected(connection):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO application_person (application_id, contact_id, role) VALUES (?, ?, ?)",
            (999, 1, "contact"),
        )


def test_company_names_are_joined_by_normalized_name(connection):
    assert db.normalize_name("  Clínica BOREAL ") == "clinica boreal"
    assert db.normalize_name("Clínica   Boreal") == "clinica boreal"
    with connection:
        same = db.ensure_company(connection, "clinica boreal")
        other = db.ensure_company(connection, "Clínica Boreal Sul")
    clinica = connection.execute("SELECT company_id FROM job WHERE id = 4").fetchone()[0]
    assert same == clinica  # job 4 is at Clínica Boreal in the seed
    assert other not in (same, None)
    assert db.ensure_company(connection, "  ") is None
    assert db.ensure_company(connection, None) is None


def test_create_schema_refuses_an_unknown_version(tmp_path):
    conn = db.connect(tmp_path / "future.db")
    try:
        conn.execute("PRAGMA user_version = 3")
        with pytest.raises(sqlite3.DatabaseError, match="version 3"):
            db.create_schema(conn)
    finally:
        conn.close()


def test_default_db_path_uses_environment_variable(monkeypatch, tmp_path):
    custom = tmp_path / "custom.db"
    monkeypatch.setenv("JOB_SEARCH_DB", str(custom))
    assert db.default_db_path() == custom


def test_default_db_path_is_anchored_at_project_root(monkeypatch, tmp_path):
    monkeypatch.delenv("JOB_SEARCH_DB", raising=False)
    monkeypatch.chdir(tmp_path)  # the default must not depend on the working directory
    path = db.default_db_path()
    assert path.is_absolute()
    assert path == db.PROJECT_ROOT / "data" / "local" / "job_search.db"
    assert (db.PROJECT_ROOT / "pyproject.toml").is_file()
    assert db.SEED_DIR == db.PROJECT_ROOT / "data" / "seed"
    assert tmp_path.resolve() not in path.parents


def test_connect_without_path_uses_environment_variable(monkeypatch, tmp_path):
    custom = tmp_path / "from_env" / "job_search.db"
    monkeypatch.setenv("JOB_SEARCH_DB", str(custom))
    conn = db.connect()
    try:
        database_file = Path(conn.execute("PRAGMA database_list").fetchone()["file"])
    finally:
        conn.close()
    assert database_file.resolve() == custom.resolve()
    assert custom.is_file()


def test_test_database_lives_in_temporary_directory(connection, tmp_path):
    database_file = Path(connection.execute("PRAGMA database_list").fetchone()["file"])
    assert tmp_path.resolve() in database_file.resolve().parents
    assert Path.cwd().resolve() not in database_file.resolve().parents
