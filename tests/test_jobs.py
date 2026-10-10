import json

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


def test_update_job_status_generates_history_with_old_and_new_value(connection, reference_date):
    result = jobs.update_job(
        connection, 8, source="usuário", reference_date=reference_date, status="applied"
    )
    assert result["job"]["status"] == "applied"
    assert result["history"] == [
        {
            "job_id": 8,
            "date": "2026-03-16",
            "field": "status",
            "old_value": "to_apply",
            "new_value": "applied",
            "source": "usuário",
        }
    ]
    stored = history_rows(connection, 8)
    assert len(stored) == 1
    assert {key: stored[0][key] for key in result["history"][0]} == result["history"][0]
    json.dumps(result)


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
