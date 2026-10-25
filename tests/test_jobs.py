import json
from datetime import date, datetime

import pytest

from job_search_mcp import domain, jobs

NEW_URL = "https://vagas.example.com/empresa-exemplo/data-engineer"


def count(connection, table):
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def history_rows(connection, job_id):
    rows = connection.execute("SELECT * FROM job_history WHERE job_id = ? ORDER BY id", (job_id,))
    return [dict(row) for row in rows]


def test_list_jobs_returns_all_seed_jobs_as_plain_dicts(connection):
    result = jobs.list_jobs(connection)
    assert [job["id"] for job in result] == list(range(1, 16))
    assert result[0]["company"] == "Banco Aurora"
    json.dumps(result)  # serializable: plain dicts, dates as ISO text


def test_list_jobs_includes_the_calculated_follow_up(connection):
    by_id = {job["id"]: job for job in jobs.list_jobs(connection)}
    assert by_id[1]["follow_up"] == "2026-03-16"  # last contact 2026-03-09 plus 7 days
    assert by_id[2]["follow_up"] == "2026-03-18"  # no contact: applied 2026-03-11 plus 7 days
    assert by_id[8]["follow_up"] is None  # to_apply does not generate a follow-up
    assert by_id[13]["follow_up"] is None  # rejected: closed, even with a last contact date


def test_list_jobs_filters_by_status_track_and_min_score(connection):
    assert [job["id"] for job in jobs.list_jobs(connection, status="applied")] == [1, 2]
    assert [job["id"] for job in jobs.list_jobs(connection, track="ai")] == [5, 7]
    assert [job["id"] for job in jobs.list_jobs(connection, min_score=8.5)] == [1, 5, 8]
    combined = jobs.list_jobs(connection, status="to_apply", track="data", min_score=9)
    assert [job["id"] for job in combined] == [8]
    assert jobs.list_jobs(connection, track="data", min_score=9.9) == []


def test_list_jobs_with_invalid_status_returns_error(connection):
    result = jobs.list_jobs(connection, status="done")
    assert result["error"] == "invalid_status"
    assert result["valid_statuses"] == list(domain.JOB_STATUSES)


def test_add_job_creates_job_in_initial_status(connection):
    job = jobs.add_job(
        connection,
        "Empresa Exemplo",
        "Data Engineer",
        NEW_URL,
        track="data",
        score=7.0,
        next_step="Avaliar aderência",
    )
    assert not domain.is_error(job)
    assert job["id"] == 16
    assert job["status"] == "suggested"
    assert job["url"] == NEW_URL
    assert job["score"] == 7.0
    assert job["follow_up"] is None
    assert count(connection, "job") == 16
    assert jobs.list_jobs(connection, status="suggested")[-1] == job
    json.dumps(job)


def test_add_job_with_duplicate_url_returns_error_and_creates_nothing(connection):
    existing_url = "https://vagas.example.com/banco-aurora/data-engineer"
    result = jobs.add_job(connection, "Outra Empresa", "Outro Cargo", existing_url)
    assert result["error"] == "duplicate_url"
    assert result["detail"]
    assert result["job"]["id"] == 1
    assert result["job"]["company"] == "Banco Aurora"
    assert count(connection, "job") == 15


def test_add_job_twice_with_the_same_url_keeps_only_the_first(connection):
    first = jobs.add_job(connection, "Empresa Exemplo", "Data Engineer", NEW_URL)
    assert first["id"] == 16
    second = jobs.add_job(connection, "Empresa Exemplo", "Data Engineer", f"  {NEW_URL} ")
    assert second["error"] == "duplicate_url"
    assert second["job"]["id"] == 16
    assert count(connection, "job") == 16


def test_add_job_requires_company_title_and_url(connection):
    for arguments in (
        ("", "Data Engineer", NEW_URL),
        ("Empresa Exemplo", " ", NEW_URL),
        ("Empresa Exemplo", "Data Engineer", None),
    ):
        result = jobs.add_job(connection, *arguments)
        assert result["error"] == "invalid_input"
    assert count(connection, "job") == 15


def test_add_job_accepts_every_track_and_the_score_limits(connection):
    for number, track in enumerate(domain.JOB_TRACKS):
        job = jobs.add_job(connection, "Empresa Exemplo", "Cargo", f"{NEW_URL}/{track}", track)
        assert job["track"] == track
        assert job["id"] == 16 + number
    for score in (0, 10, 0.0, 10.0, 7.5):
        url = f"{NEW_URL}/{score!r}"
        job = jobs.add_job(connection, "Empresa Exemplo", "Cargo", url, score=score)
        assert job["score"] == score
    without = jobs.add_job(connection, "Empresa Exemplo", "Cargo", f"{NEW_URL}/none")
    assert without["track"] is None
    assert without["score"] is None


@pytest.mark.parametrize("track", ["dados", "Data", "", " data", "backend"])
def test_add_job_with_invalid_track_returns_error_and_creates_nothing(connection, track):
    result = jobs.add_job(connection, "Empresa Exemplo", "Data Engineer", NEW_URL, track=track)
    assert result["error"] == "invalid_input"
    assert "track" in result["detail"]
    assert result["valid_tracks"] == ["data", "systems", "product", "ai", "other"]
    assert count(connection, "job") == 15


@pytest.mark.parametrize("score", [-0.1, 10.1, 11, -1, float("nan"), float("inf"), True, "8"])
def test_add_job_with_invalid_score_returns_error_and_creates_nothing(connection, score):
    result = jobs.add_job(connection, "Empresa Exemplo", "Data Engineer", NEW_URL, score=score)
    assert result["error"] == "invalid_input"
    assert "score" in result["detail"]
    assert "0 to 10" in result["detail"]
    assert count(connection, "job") == 15


def test_seed_jobs_respect_the_track_and_score_rules(connection):
    for job in jobs.list_jobs(connection):
        assert job["track"] in domain.JOB_TRACKS
        assert domain.is_valid_score(job["score"])


def test_update_job_status_generates_history_with_old_and_new_value(connection, reference_date):
    result = jobs.update_job(
        connection, 8, source="usuário", reference_date=reference_date, status="applied"
    )
    assert result["job"]["status"] == "applied"
    assert result["history"][0] == {
        "job_id": 8,
        "date": "2026-03-16",
        "field": "status",
        "old_value": "to_apply",
        "new_value": "applied",
        "source": "usuário",
    }
    # Job 8 had no application date: becoming applied also fills applied_on (second line).
    assert [line["field"] for line in result["history"]] == ["status", "applied_on"]
    stored = history_rows(connection, 8)
    assert len(stored) == 2
    for line, stored_line in zip(result["history"], stored, strict=True):
        assert {key: stored_line[key] for key in line} == line
    json.dumps(result)


def test_update_job_to_applied_without_application_date_fills_it_with_the_reference_date(
    connection, reference_date
):
    assert jobs.get_job(connection, 8)["applied_on"] is None
    result = jobs.update_job(
        connection, 8, source="usuário", reference_date=reference_date, status="applied"
    )
    assert result["job"]["applied_on"] == "2026-03-16"
    assert result["job"]["follow_up"] == "2026-03-23"  # the job now has a follow-up
    assert result["history"][1] == {
        "job_id": 8,
        "date": "2026-03-16",
        "field": "applied_on",
        "old_value": None,
        "new_value": "2026-03-16",
        "source": "usuário",
    }
    assert count(connection, "job_history") == 2


def test_update_job_to_applied_keeps_the_informed_application_date(connection, reference_date):
    result = jobs.update_job(
        connection,
        8,
        source="usuário",
        reference_date=reference_date,
        status="applied",
        applied_on="2026-03-12",
    )
    assert result["job"]["applied_on"] == "2026-03-12"
    assert result["job"]["follow_up"] == "2026-03-19"
    assert [line["field"] for line in result["history"]] == ["status", "applied_on"]
    assert result["history"][1]["new_value"] == "2026-03-12"


def test_update_job_to_applied_keeps_the_stored_application_date(connection, reference_date):
    # Job 3 is in_review and already has an application date: going back to applied keeps it.
    result = jobs.update_job(
        connection, 3, source="usuário", reference_date=reference_date, status="applied"
    )
    assert result["job"]["applied_on"] == "2026-03-05"
    assert [line["field"] for line in result["history"]] == ["status"]


def test_update_job_to_another_status_does_not_fill_the_application_date(
    connection, reference_date
):
    result = jobs.update_job(
        connection, 8, source="usuário", reference_date=reference_date, status="blocked"
    )
    assert result["job"]["applied_on"] is None
    assert [line["field"] for line in result["history"]] == ["status"]


def test_update_job_records_one_history_line_per_changed_field(connection, reference_date):
    result = jobs.update_job(
        connection,
        8,
        source="usuário",
        reference_date=reference_date,
        status="applied",
        next_step="Aguardar triagem",
        applied_on="2026-03-16",
    )
    assert [line["field"] for line in result["history"]] == ["status", "next_step", "applied_on"]
    assert result["history"][1]["old_value"] == "Adaptar o currículo e enviar"
    assert result["history"][1]["new_value"] == "Aguardar triagem"
    assert result["history"][2]["old_value"] is None
    assert result["job"]["applied_on"] == "2026-03-16"
    assert result["job"]["follow_up"] == "2026-03-23"
    assert count(connection, "job_history") == 3


def test_update_job_accepts_date_objects_and_moves_the_follow_up(connection, reference_date):
    result = jobs.update_job(
        connection,
        1,
        source="usuário",
        reference_date=reference_date,
        last_contact_on=reference_date,
    )
    assert result["job"]["last_contact_on"] == "2026-03-16"
    assert result["job"]["follow_up"] == "2026-03-23"
    assert result["history"][0]["old_value"] == "2026-03-09"


def test_update_job_without_real_change_generates_no_history(connection, reference_date):
    result = jobs.update_job(
        connection, 1, source="usuário", reference_date=reference_date, status="applied"
    )
    assert result["history"] == []
    assert result["job"]["status"] == "applied"
    assert count(connection, "job_history") == 0


def test_update_job_with_invalid_status_returns_error_and_changes_nothing(
    connection, reference_date
):
    before = jobs.get_job(connection, 1)
    result = jobs.update_job(
        connection,
        1,
        source="usuário",
        reference_date=reference_date,
        status="done",
        next_step="Não deve ser gravado",
    )
    assert result["error"] == "invalid_status"
    assert result["valid_statuses"] == list(domain.JOB_STATUSES)
    assert "hr_interview" in result["detail"]
    assert jobs.get_job(connection, 1) == before
    assert count(connection, "job_history") == 0


def test_update_job_with_invalid_date_returns_error_and_changes_nothing(connection, reference_date):
    before = jobs.get_job(connection, 1)
    result = jobs.update_job(
        connection,
        1,
        source="usuário",
        reference_date=reference_date,
        status="in_review",
        applied_on="16/03/2026",
    )
    assert result["error"] == "invalid_date"
    assert jobs.get_job(connection, 1) == before
    assert count(connection, "job_history") == 0


def test_update_job_unknown_id_returns_error(connection, reference_date):
    result = jobs.update_job(
        connection, 999, source="usuário", reference_date=reference_date, status="applied"
    )
    assert result["error"] == "not_found"
    assert "999" in result["detail"]


def test_update_job_requires_source(connection, reference_date):
    result = jobs.update_job(
        connection, 8, source=" ", reference_date=reference_date, status="applied"
    )
    assert result["error"] == "invalid_input"
    assert jobs.get_job(connection, 8)["status"] == "to_apply"


def test_update_job_with_datetime_stores_only_the_date_and_keeps_listing_working(
    connection, reference_date
):
    result = jobs.update_job(
        connection,
        1,
        source="usuário",
        reference_date=reference_date,
        applied_on=datetime(2026, 3, 3, 9, 15),
        last_contact_on=datetime(2026, 3, 16, 14, 30, 59),
    )
    assert result["job"]["applied_on"] == "2026-03-03"
    assert result["job"]["last_contact_on"] == "2026-03-16"
    stored = connection.execute(
        "SELECT applied_on, last_contact_on FROM job WHERE id = 1"
    ).fetchone()
    assert tuple(stored) == ("2026-03-03", "2026-03-16")
    assert [line["new_value"] for line in result["history"]] == ["2026-03-03", "2026-03-16"]
    listed = {job["id"]: job for job in jobs.list_jobs(connection)}
    assert len(listed) == 15
    assert listed[1]["follow_up"] == "2026-03-23"


def test_update_job_with_non_text_date_returns_error_and_changes_nothing(
    connection, reference_date
):
    before = jobs.get_job(connection, 8)
    result = jobs.update_job(
        connection,
        8,
        source="usuário",
        reference_date=reference_date,
        status="applied",
        applied_on=20260316,
    )
    assert result["error"] == "invalid_date"
    assert "applied_on" in result["detail"]
    assert jobs.get_job(connection, 8) == before
    assert count(connection, "job_history") == 0


def test_update_job_accepts_reference_date_as_iso_text_or_datetime(connection):
    as_text = jobs.update_job(
        connection, 9, source="usuário", reference_date="2026-03-16", status="applied"
    )
    assert [line["date"] for line in as_text["history"]] == ["2026-03-16", "2026-03-16"]
    assert as_text["job"]["applied_on"] == "2026-03-16"
    as_datetime = jobs.update_job(
        connection, 10, "usuário", datetime(2026, 3, 16, 8, 0), status="applied"
    )
    assert as_datetime["history"][0]["date"] == "2026-03-16"
    assert as_datetime["job"]["applied_on"] == "2026-03-16"


def test_update_job_with_invalid_reference_date_returns_error_and_changes_nothing(connection):
    before = jobs.get_job(connection, 8)
    for value in ("16/03/2026", None, 20260316):
        result = jobs.update_job(
            connection, 8, source="usuário", reference_date=value, status="applied"
        )
        assert result["error"] == "invalid_date"
        assert "reference_date" in result["detail"]
    assert jobs.get_job(connection, 8) == before
    assert count(connection, "job_history") == 0


def test_apply_job_changes_refuses_a_field_outside_the_allowed_list(connection):
    job = jobs.get_job(connection, 1)
    changes = {"status": "in_review", "company": "Outra Empresa"}
    before = connection.total_changes
    with pytest.raises(ValueError, match="company"):
        jobs.apply_job_changes(connection, job, changes, "usuário", date(2026, 3, 16))
    assert connection.total_changes == before  # failed before writing anything
    assert jobs.get_job(connection, 1) == job
    assert count(connection, "job_history") == 0
    assert jobs.JOB_UPDATABLE_FIELDS == ("status", "next_step", "applied_on", "last_contact_on")
