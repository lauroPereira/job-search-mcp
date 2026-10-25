import asyncio
import os
import shutil
import sqlite3
import subprocess
import sys
import sysconfig
from datetime import date
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from job_search_mcp import db, server, summary

TOOL_NAMES = [
    "add_job",
    "daily_summary",
    "list_contacts",
    "list_jobs",
    "log_interaction",
    "pending_followups",
    "update_job",
]
TODAY = date(2026, 3, 16)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Seeded database in the temporary directory, with the server's "today" fixed."""
    path = tmp_path / "job_search_server_test.db"
    monkeypatch.setenv(db.DB_ENV_VAR, str(path))
    monkeypatch.setattr(server, "today", lambda: TODAY)
    assert server.seed_database() is None
    return path


def run(action, transport=None):
    """Open a client (in memory unless a transport is given) and run `action(client)`."""

    async def session():
        async with Client(transport or server.mcp) as client:
            return await action(client)

    return asyncio.run(session())


def call(name, **arguments):
    """Call a tool through the in-memory client and return the raw result."""
    return run(lambda client: client.call_tool(name, arguments, raise_on_error=False))


def structured(name, **arguments):
    """Call a tool and return its structured content, checking it is not a protocol error."""
    result = call(name, **arguments)
    assert result.is_error is False
    assert isinstance(result.structured_content, dict)
    return result.structured_content


def rows(path, query):
    connection = sqlite3.connect(path)
    try:
        return connection.execute(query).fetchall()
    finally:
        connection.close()


def test_server_lists_exactly_the_seven_tools(db_path):
    tools = run(lambda client: client.list_tools())
    assert sorted(tool.name for tool in tools) == TOOL_NAMES
    assert server.mcp.name == "job-search"
    for tool in tools:
        assert tool.description
        assert tool.output_schema["type"] == "object"
        for name, schema in tool.input_schema["properties"].items():
            assert schema.get("description"), f"{tool.name}.{name} has no description"


def test_tool_parameters_match_the_plan(db_path):
    tools = {tool.name: tool for tool in run(lambda client: client.list_tools())}
    parameters = {name: sorted(tool.input_schema["properties"]) for name, tool in tools.items()}
    assert parameters == {
        "list_jobs": ["min_score", "status", "track"],
        "add_job": ["company", "next_step", "score", "title", "track", "url"],
        "update_job": ["applied_on", "job_id", "last_contact_on", "next_step", "source", "status"],
        "list_contacts": ["company", "status"],
        "log_interaction": ["contact_id", "date", "next_step", "status", "summary"],
        "pending_followups": ["days_ahead", "reference_date"],
        "daily_summary": ["deadline", "reference_date"],
    }
    required = {name: sorted(tool.input_schema.get("required", [])) for name, tool in tools.items()}
    assert required == {
        "list_jobs": [],
        "add_job": ["company", "title", "url"],
        "update_job": ["job_id", "source"],
        "list_contacts": [],
        "log_interaction": ["contact_id", "summary"],
        "pending_followups": [],
        "daily_summary": [],
    }
    days_ahead = tools["pending_followups"].input_schema["properties"]["days_ahead"]
    assert days_ahead["type"] == "integer"
    assert days_ahead["default"] == 2


def test_only_the_four_query_tools_carry_the_read_only_hint(db_path):
    tools = {tool.name: tool for tool in run(lambda client: client.list_tools())}
    read_only = {
        name: getattr(tool.annotations, "read_only_hint", None) for name, tool in tools.items()
    }
    assert read_only == {
        "list_jobs": True,
        "list_contacts": True,
        "pending_followups": True,
        "daily_summary": True,
        "add_job": None,
        "update_job": None,
        "log_interaction": None,
    }


def test_daily_summary_uses_today_and_returns_the_expected_object(db_path):
    result = structured("daily_summary")
    connection = db.connect(db_path)
    try:
        expected = summary.daily_summary(connection, TODAY)
    finally:
        connection.close()
    assert result == expected
    assert result["reference_date"] == "2026-03-16"
    assert result["jobs_by_status"]["applied"] == 2
    assert result["active_contacts"] == 7
    assert [job["id"] for job in result["overdue"]["jobs"]] == [5, 1]
    assert [contact["id"] for contact in result["due_soon"]["contacts"]] == [2, 7]
    assert [job["id"] for job in result["application_queue"]] == [8, 9, 10]
    assert result["days_to_deadline"] is None


def test_daily_summary_accepts_reference_date_and_deadline_as_iso_text(db_path):
    result = structured("daily_summary", reference_date="2026-03-20", deadline="2026-03-31")
    assert result["reference_date"] == "2026-03-20"
    assert result["days_to_deadline"] == 11
    assert structured("daily_summary", reference_date="20/03/2026")["error"] == "invalid_date"
    assert structured("daily_summary", deadline="fim do mês")["error"] == "invalid_date"


def test_pending_followups_defaults_to_today_and_two_days_ahead(db_path):
    result = structured("pending_followups")
    assert result["reference_date"] == "2026-03-16"
    assert result["days_ahead"] == 2
    assert [(job["id"], job["state"]) for job in result["jobs"]] == [
        (5, "overdue"),
        (1, "overdue"),
        (7, "due_soon"),
        (2, "due_soon"),
        (3, "due_soon"),
    ]
    assert [contact["id"] for contact in result["contacts"]] == [1, 4, 2, 7]
    wider = structured("pending_followups", reference_date="2026-03-16", days_ahead=0)
    assert [job["id"] for job in wider["jobs"]] == [5, 1]


def test_pending_followups_rejects_negative_days_ahead_and_invalid_date(db_path):
    negative = structured("pending_followups", days_ahead=-1)
    assert negative["error"] == "invalid_input"
    assert "days_ahead" in negative["detail"]
    assert structured("pending_followups", reference_date="amanhã")["error"] == "invalid_date"


def test_add_job_then_list_jobs(db_path):
    url = "https://vagas.example.com/empresa-exemplo/data-engineer"
    created = structured(
        "add_job", company="Empresa Exemplo", title="Data Engineer", url=url, track="data", score=8
    )
    assert created["id"] == 16
    assert created["status"] == "suggested"
    assert created["follow_up"] is None
    listed = structured("list_jobs", status="suggested")
    assert [job["id"] for job in listed["jobs"]] == [10, 16]
    assert listed["jobs"][1] == created
    assert len(structured("list_jobs")["jobs"]) == 16
    filtered = structured("list_jobs", track="data", min_score=8.4)
    assert [job["id"] for job in filtered["jobs"]] == [1, 8]


def test_duplicate_url_arrives_as_a_structured_error(db_path):
    url = "https://vagas.example.com/banco-aurora/data-engineer"
    result = structured("add_job", company="Banco Aurora", title="Data Engineer", url=url)
    assert result["error"] == "duplicate_url"
    assert "id 1" in result["detail"]
    assert result["job"]["id"] == 1
    assert rows(db_path, "SELECT COUNT(*) FROM job") == [(15,)]


def test_add_job_rejects_invalid_track_and_score_as_structured_errors(db_path):
    job = {"company": "Empresa Exemplo", "title": "Data Engineer", "url": "https://example.com/v"}
    track = structured("add_job", **job, track="dados")
    assert track["error"] == "invalid_input"
    assert "track" in track["detail"]
    assert track["valid_tracks"] == ["data", "systems", "product", "ai", "other"]
    for score in (-1, 10.5):
        result = structured("add_job", **job, score=score)
        assert result["error"] == "invalid_input"
        assert "score" in result["detail"]
    assert rows(db_path, "SELECT COUNT(*) FROM job") == [(15,)]
    created = structured("add_job", **job, track="other", score=10)
    assert (created["track"], created["score"]) == ("other", 10)


def test_invalid_status_arrives_as_a_structured_error_with_the_valid_ones(db_path):
    for name, arguments, valid in (
        ("list_jobs", {"status": "aplicada"}, "hr_interview"),
        ("update_job", {"job_id": 1, "source": "user", "status": "aplicada"}, "hr_interview"),
        ("list_contacts", {"status": "aplicada"}, "awaiting_reply"),
        ("log_interaction", {"contact_id": 1, "summary": "Conversa", "status": "x"}, "referred"),
    ):
        result = structured(name, **arguments)
        assert result["error"] == "invalid_status"
        assert valid in result["valid_statuses"]
        assert valid in result["detail"]
    assert rows(db_path, "SELECT COUNT(*) FROM job_history") == [(0,)]
    assert rows(db_path, "SELECT COUNT(*) FROM interaction") == [(0,)]


def test_update_job_writes_history_dated_today(db_path):
    result = structured(
        "update_job", job_id=8, source="user", status="applied", next_step="Aguardar triagem"
    )
    assert result["job"]["status"] == "applied"
    assert result["job"]["applied_on"] == "2026-03-16"  # filled with today
    assert result["job"]["follow_up"] == "2026-03-23"
    assert {
        (line["field"], line["old_value"], line["new_value"]) for line in result["history"]
    } == {
        ("status", "to_apply", "applied"),
        ("next_step", "Adaptar o currículo e enviar", "Aguardar triagem"),
        ("applied_on", None, "2026-03-16"),
    }
    assert all(line["date"] == "2026-03-16" for line in result["history"])
    assert all(line["source"] == "user" for line in result["history"])
    assert rows(db_path, "SELECT COUNT(*) FROM job_history") == [(3,)]


def test_update_job_does_not_expose_reference_date(db_path):
    result = call("update_job", job_id=8, source="user", reference_date="2026-01-01")
    assert result.is_error is True
    assert rows(db_path, "SELECT COUNT(*) FROM job_history") == [(0,)]


def test_update_job_rejects_future_and_invalid_dates(db_path):
    for field in ("applied_on", "last_contact_on"):
        future = structured("update_job", job_id=1, source="user", **{field: "2026-03-17"})
        assert future["error"] == "invalid_date"
        assert field in future["detail"]
        assert "2026-03-16" in future["detail"]
        invalid = structured("update_job", job_id=1, source="user", **{field: "ontem"})
        assert invalid["error"] == "invalid_date"
        assert field in invalid["detail"]
    assert rows(db_path, "SELECT COUNT(*) FROM job_history") == [(0,)]
    today = structured("update_job", job_id=1, source="user", last_contact_on="2026-03-16")
    assert today["job"]["last_contact_on"] == "2026-03-16"


def test_log_interaction_updates_the_contact_and_the_linked_job(db_path):
    result = structured("log_interaction", contact_id=1, summary="Respondeu sobre a indicação")
    assert result["contact"]["last_contact_on"] == "2026-03-16"  # defaults to today
    assert result["follow_up"] == "2026-03-22"
    assert result["job"]["id"] == 1
    assert result["job"]["last_contact_on"] == "2026-03-16"
    assert rows(db_path, "SELECT contact_id, date, summary FROM interaction") == [
        (1, "2026-03-16", "Respondeu sobre a indicação")
    ]
    dated = structured(
        "log_interaction",
        contact_id=8,
        summary="Primeira mensagem",
        date="2026-03-15",
        next_step="Aguardar resposta",
    )
    assert dated["contact"]["status"] == "awaiting_reply"
    assert dated["contact"]["next_step"] == "Aguardar resposta"
    assert dated["follow_up"] == "2026-03-21"
    assert dated["job"] is None


def test_log_interaction_rejects_future_and_invalid_dates(db_path):
    future = structured("log_interaction", contact_id=1, summary="Conversa", date="2026-03-17")
    assert future["error"] == "invalid_date"
    assert "after today" in future["detail"]
    assert structured("log_interaction", contact_id=1, summary="x", date="hoje")["error"] == (
        "invalid_date"
    )
    assert structured("log_interaction", contact_id=99, summary="x")["error"] == "not_found"
    assert rows(db_path, "SELECT COUNT(*) FROM interaction") == [(0,)]


def test_list_contacts_filters_by_status_and_company(db_path):
    assert len(structured("list_contacts")["contacts"]) == 8
    result = structured("list_contacts", status="in_conversation")
    assert [contact["id"] for contact in result["contacts"]] == [2, 7]
    result = structured("list_contacts", company="banco aurora")
    assert [contact["name"] for contact in result["contacts"]] == ["Ana Exemplo"]


def test_tools_create_the_schema_in_a_new_database(tmp_path, monkeypatch):
    path = tmp_path / "new" / "job_search.db"
    monkeypatch.setenv(db.DB_ENV_VAR, str(path))
    assert structured("list_jobs") == {"jobs": []}
    assert path.is_file()
    assert structured("daily_summary", reference_date="2026-03-16")["active_contacts"] == 0


def test_tools_close_the_connection_on_success_business_error_and_exception(db_path, monkeypatch):
    """Counts the real calls to close(): one for each connection a tool opens."""
    opened, closed = [], []
    original_connect = sqlite3.connect

    class CountingConnection(sqlite3.Connection):
        def close(self):
            closed.append(self)
            super().close()

    def counting_connect(database, *args, **kwargs):
        opened.append(original_connect(database, *args, factory=CountingConnection, **kwargs))
        return opened[-1]

    def failing(*args, **kwargs):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(db.sqlite3, "connect", counting_connect)

    assert structured("list_jobs")["jobs"]  # success
    assert (len(opened), len(closed)) == (1, 1)

    assert structured("list_jobs", status="aplicada")["error"] == "invalid_status"  # business error
    assert (len(opened), len(closed)) == (2, 2)

    monkeypatch.setattr(server.jobs, "list_jobs", failing)  # unexpected exception in the domain
    result = call("list_jobs")
    assert result.is_error is True
    assert "unexpected failure" in result.content[0].text
    assert (len(opened), len(closed)) == (3, 3)

    assert all(a is b for a, b in zip(opened, closed, strict=True))


def test_nothing_is_written_outside_the_temporary_directory(db_path, tmp_path, monkeypatch):
    opened = []
    original_connect = sqlite3.connect

    def tracking_connect(database, *args, **kwargs):
        opened.append(Path(database).resolve())
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(db.sqlite3, "connect", tracking_connect)
    default_existed = db.DEFAULT_DB_PATH.exists()
    structured("daily_summary")
    structured("pending_followups")
    structured("list_contacts")
    structured("add_job", company="Empresa Exemplo", title="Dev", url="https://example.com/vaga")
    structured("update_job", job_id=16, source="user", status="to_apply")
    structured("log_interaction", contact_id=2, summary="Conversa")
    assert len(opened) == 6
    assert set(opened) == {db_path.resolve()}
    assert db_path.resolve().is_relative_to(tmp_path.resolve())
    assert [path.name for path in tmp_path.iterdir()] == [db_path.name]
    assert db.DEFAULT_DB_PATH.exists() == default_existed


def test_seed_option_loads_a_new_database_and_refuses_one_with_data(tmp_path, monkeypatch, capsys):
    path = tmp_path / "demo.db"
    monkeypatch.setenv(db.DB_ENV_VAR, str(path))
    assert server.main(["--seed"]) == 0
    assert rows(path, "SELECT COUNT(*) FROM job") == [(15,)]
    assert rows(path, "SELECT COUNT(*) FROM contact") == [(8,)]
    assert "Demo data loaded" in capsys.readouterr().err
    assert server.main(["--seed"]) == 1
    captured = capsys.readouterr()
    assert "already has data" in captured.err
    assert captured.out == ""
    assert rows(path, "SELECT COUNT(*) FROM job") == [(15,)]


def test_seed_option_reports_an_unusable_path_without_a_traceback(tmp_path, monkeypatch, capsys):
    a_file = tmp_path / "not_a_directory"
    a_file.write_text("x", encoding="utf-8")
    for path in (tmp_path, a_file / "demo.db"):  # a directory as the file; a file as the parent
        monkeypatch.setenv(db.DB_ENV_VAR, str(path))
        assert server.main(["--seed"]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err.startswith("Could not load the demo data into")
        assert len(captured.err.strip().splitlines()) == 1
        assert db.DB_ENV_VAR in captured.err
    assert sorted(item.name for item in tmp_path.iterdir()) == ["not_a_directory"]


def test_seed_option_reports_missing_demo_data_without_blaming_the_database_path(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "demo.db"
    empty_seed_dir = tmp_path / "seed"
    empty_seed_dir.mkdir()
    monkeypatch.setenv(db.DB_ENV_VAR, str(path))
    monkeypatch.setattr(db, "SEED_DIR", empty_seed_dir)
    assert server.main(["--seed"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Could not read the demo data in")
    assert len(captured.err.strip().splitlines()) == 1
    assert "jobs.csv" in captured.err
    assert db.DB_ENV_VAR not in captured.err
    assert not path.exists()  # no empty database file is left behind


def installed_entry_point():
    """The `job-search-mcp` executable of this environment, in the interpreter's scripts."""
    executable = shutil.which("job-search-mcp", path=sysconfig.get_path("scripts"))
    if executable is None:
        pytest.skip("job-search-mcp is not installed in this environment (pip install -e .)")
    return executable


def test_installed_entry_point_seeds_and_serves(tmp_path):
    """The executable declared in [project.scripts]: --seed, the error path and the server."""
    executable = installed_entry_point()
    path = tmp_path / "demo.db"

    def seed(target):
        return subprocess.run(
            [executable, "--seed"],
            env={**os.environ, db.DB_ENV_VAR: str(target)},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    loaded = seed(path)
    assert (loaded.returncode, loaded.stdout) == (0, "")
    assert "Demo data loaded" in loaded.stderr
    unusable = seed(tmp_path)  # a directory in place of the database file
    assert unusable.returncode == 1
    assert "Could not load the demo data" in unusable.stderr
    assert "Traceback" not in unusable.stderr

    transport = StdioTransport(
        command=executable, args=[], env={**os.environ, db.DB_ENV_VAR: str(path)}, keep_alive=False
    )

    async def session(client):
        tools = await client.list_tools()
        return tools, await client.call_tool("daily_summary", {"reference_date": "2026-03-16"})

    tools, result = run(session, transport)
    assert sorted(tool.name for tool in tools) == TOOL_NAMES
    assert result.is_error is False
    assert result.structured_content["active_contacts"] == 7
    assert [job["id"] for job in result.structured_content["application_queue"]] == [8, 9, 10]


def test_server_runs_over_stdio_as_a_subprocess(db_path):
    """The real entry point, started as a subprocess, answers a client connected by stdio."""
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "job_search_mcp.server"],
        env={**os.environ, db.DB_ENV_VAR: str(db_path)},
        keep_alive=False,
    )

    async def session(client):
        tools = await client.list_tools()
        result = await client.call_tool("pending_followups", {"reference_date": "2026-03-16"})
        return tools, result

    tools, result = run(session, transport)
    assert sorted(tool.name for tool in tools) == TOOL_NAMES
    assert result.is_error is False
    assert [job["id"] for job in result.structured_content["jobs"]] == [5, 1, 7, 2, 3]
    assert [contact["id"] for contact in result.structured_content["contacts"]] == [1, 4, 2, 7]
