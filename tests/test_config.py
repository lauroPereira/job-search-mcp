import asyncio
from datetime import date
from pathlib import Path

import pytest
from fastmcp import Client

from job_search_mcp import config, contacts, db, domain, jobs, server, summary
from job_search_mcp.config import ConfigError, Settings, load_settings

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"


def write(tmp_path, text, name="config.toml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_without_the_variable_the_defaults_apply():
    settings = load_settings()
    assert settings == Settings()
    assert settings.job_follow_up_days == domain.JOB_FOLLOW_UP_DAYS == 7
    assert settings.contact_follow_up_days == domain.CONTACT_FOLLOW_UP_DAYS == 6
    assert settings.deadline is None
    assert settings.applications_per_week is None
    assert settings.interview_rate is None
    assert settings.proposal_ttl_hours == 24


def test_a_missing_file_gives_the_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(tmp_path / "missing.toml"))
    assert load_settings() == Settings()
    assert load_settings(tmp_path / "missing.toml") == Settings()


def test_the_example_file_is_read_from_the_variable(monkeypatch):
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(EXAMPLE))
    assert load_settings() == Settings(
        job_follow_up_days=7,
        contact_follow_up_days=6,
        deadline=date(2099, 12, 31),
        applications_per_week=5,
        interview_rate=0.2,
        proposal_ttl_hours=24,
    )


def test_settings_are_immutable():
    with pytest.raises(AttributeError):
        Settings().job_follow_up_days = 10


def test_partial_file_keeps_the_other_defaults_and_accepts_an_iso_text_deadline(tmp_path):
    path = write(tmp_path, '[follow_up]\njob_days = 10\n[goals]\ndeadline = "2026-06-30"\n')
    settings = load_settings(path)
    assert settings.job_follow_up_days == 10
    assert settings.contact_follow_up_days == 6
    assert settings.deadline == date(2026, 6, 30)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[follow_up\njob_days = 10\n", "Invalid settings file"),
        ('[follow_up]\njob_days = "10"\n', "'follow_up.job_days'"),
        ("[follow_up]\ncontact_days = 0\n", "'follow_up.contact_days'"),
        ("[follow_up]\njob_days = true\n", "'follow_up.job_days'"),
        ('[goals]\ndeadline = "30/06/2026"\n', "'goals.deadline'"),
        ("[goals]\ndeadline = true\n", "'goals.deadline'"),
        ("[goals]\ninterview_rate = 1.5\n", "'goals.interview_rate'"),
        ("[proposals]\nttl_hours = 1.5\n", "'proposals.ttl_hours'"),
        ("[follow_up]\njob_day = 10\n", "Unknown key 'follow_up.job_day'"),
        ("[salary]\nfloor = 1\n", "Unknown section [salary]"),
        ("follow_up = 10\n", "must be a section"),
    ],
)
def test_an_invalid_file_raises_a_clear_error(tmp_path, text, message):
    path = write(tmp_path, text)
    with pytest.raises(ConfigError) as failure:
        load_settings(path)
    assert message in str(failure.value)
    assert str(path) in str(failure.value)


def test_domain_follow_up_receives_the_days():
    assert domain.job_follow_up("2026-03-02", "2026-03-09", days=10) == date(2026, 3, 19)
    assert domain.contact_follow_up("2026-03-08", days=9) == date(2026, 3, 17)


def test_follow_ups_are_recalculated_with_other_days(connection, reference_date):
    default_job = jobs.get_job(connection, 1)
    default_contact = contacts.get_contact(connection, 1)
    assert default_job["follow_up"] == "2026-03-16"  # 2026-03-09 + 7
    assert default_contact["follow_up"] == "2026-03-14"  # 2026-03-08 + 6

    settings = Settings(job_follow_up_days=10, contact_follow_up_days=9)
    assert jobs.get_job(connection, 1, settings)["follow_up"] == "2026-03-19"
    assert jobs.list_jobs(connection, settings=settings)[0]["follow_up"] == "2026-03-19"
    assert contacts.get_contact(connection, 1, settings)["follow_up"] == "2026-03-17"

    # Job 1 was overdue on the reference date with 7 days; with 10 it is no longer pending.
    default_pending = summary.pending_followups(connection, reference_date)
    pending = summary.pending_followups(connection, reference_date, settings=settings)
    assert 1 in [job["id"] for job in default_pending["jobs"]]
    assert 1 not in [job["id"] for job in pending["jobs"]]


def test_daily_summary_uses_the_settings_deadline_unless_one_is_informed(
    connection, reference_date
):
    settings = Settings(deadline=date(2026, 4, 15))
    without = summary.daily_summary(connection, reference_date)
    assert without["deadline"] is None
    from_settings = summary.daily_summary(connection, reference_date, settings=settings)
    assert from_settings["deadline"] == "2026-04-15"
    assert from_settings["days_to_deadline"] == 30
    informed = summary.daily_summary(connection, reference_date, "2026-03-20", settings=settings)
    assert informed["deadline"] == "2026-03-20"
    assert informed["days_to_deadline"] == 4


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    monkeypatch.setenv(db.DB_ENV_VAR, str(tmp_path / "job_search_config_test.db"))
    monkeypatch.setattr(server, "today", lambda: date(2026, 3, 16))
    assert server.seed_database() is None


def call_tool(name, **arguments):
    async def session():
        async with Client(server.mcp) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(session()).structured_content


def test_tools_read_the_settings_file(seeded, tmp_path, monkeypatch):
    assert call_tool("list_jobs")["jobs"][0]["follow_up"] == "2026-03-16"
    path = write(tmp_path, "[follow_up]\njob_days = 10\n[goals]\ndeadline = 2026-04-15\n")
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))
    assert call_tool("list_jobs")["jobs"][0]["follow_up"] == "2026-03-19"
    assert call_tool("daily_summary")["deadline"] == "2026-04-15"


def test_main_reports_an_invalid_settings_file_without_a_traceback(tmp_path, monkeypatch, capsys):
    path = write(tmp_path, '[follow_up]\njob_days = "ten"\n')
    monkeypatch.setenv(config.CONFIG_ENV_VAR, str(path))
    monkeypatch.setenv(db.DB_ENV_VAR, str(tmp_path / "demo.db"))
    assert server.main(["--seed"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "'follow_up.job_days'" in captured.err
    assert "Traceback" not in captured.err
    assert len(captured.err.strip().splitlines()) == 1
    assert not (tmp_path / "demo.db").exists()
