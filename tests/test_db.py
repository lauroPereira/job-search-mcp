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


def test_create_schema_creates_the_four_tables(tmp_path):
    conn = db.connect(tmp_path / "empty.db")
    try:
        db.create_schema(conn)
        db.create_schema(conn)  # safe to run again on an existing database
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    finally:
        conn.close()
    assert tables == {"job", "contact", "interaction", "job_history"}


def test_connect_enables_foreign_keys_and_named_rows(connection):
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    job = connection.execute("SELECT * FROM job WHERE id = 1").fetchone()
    assert job["company"] == "Banco Aurora"


def test_connect_creates_missing_parent_directory(tmp_path):
    path = tmp_path / "nested" / "local" / "job_search.db"
    conn = db.connect(path)
    conn.close()
    assert path.is_file()


def test_seed_loads_expected_counts(connection):
    assert count(connection, "job") == 15
    assert count(connection, "contact") == 8
    assert count(connection, "interaction") == 0
    assert count(connection, "job_history") == 0
    assert count_by_status(connection, "job") == EXPECTED_JOBS_BY_STATUS
    assert count_by_status(connection, "contact") == EXPECTED_CONTACTS_BY_STATUS


def test_seed_empty_cells_become_null_and_links_resolve(connection):
    job = connection.execute("SELECT * FROM job WHERE id = 2").fetchone()
    assert job["applied_on"] == "2026-03-11"
    assert job["last_contact_on"] is None
    linked = connection.execute("SELECT COUNT(*) FROM contact WHERE job_id IS NOT NULL")
    assert linked.fetchone()[0] == 6
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_duplicate_url_is_rejected(connection):
    url = connection.execute("SELECT url FROM job WHERE id = 1").fetchone()["url"]
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO job (company, title, url, status) VALUES (?, ?, ?, ?)",
            ("Banco Aurora", "Data Engineer", url, "suggested"),
        )
    assert count(connection, "job") == 15


def test_job_without_url_is_rejected(connection):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO job (company, title, status) VALUES (?, ?, ?)",
            ("Banco Aurora", "Data Engineer", "suggested"),
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


def test_contact_with_unknown_job_is_rejected(connection):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO contact (name, status, job_id) VALUES (?, ?, ?)",
            ("Ana Exemplo", "to_contact", 999),
        )


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
