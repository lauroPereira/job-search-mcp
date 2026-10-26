"""Two-step writes: proposals are stored without changing anything until confirmed."""

from datetime import UTC, datetime, timedelta

import pytest

from job_search_mcp import config, db, jobs, proposals

NOW = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
ON = "2026-03-16"
NEW_URL = "https://vagas.example.com/empresa-nova/data-engineer"

WRITES = (
    (
        "add_job",
        {"company": "Empresa Nova", "title": "Data Engineer", "url": NEW_URL, "reference_date": ON},
    ),
    ("update_job", {"job_id": 8, "source": "email", "reference_date": ON, "status": "applied"}),
    ("log_interaction", {"contact_id": 1, "summary": "Respondeu sobre a indicação", "date": ON}),
    (
        "network_save_company",
        {"name": "Empresa Nova", "priority": "B", "source": "user", "reference_date": ON},
    ),
    (
        "network_save_person",
        {
            "name": "Iara Nova",
            "company": "Empresa Zeta",
            "source": "conversation",
            "reference_date": ON,
        },
    ),
)


def snapshot(connection):
    """Every row of every table except proposal."""
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%' AND name != 'proposal' ORDER BY name"
        )
    ]
    return {
        table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
        for table in tables
    }


def status(connection, proposal_id):
    row = connection.execute("SELECT status FROM proposal WHERE id = ?", (proposal_id,))
    return row.fetchone()[0]


def count(connection, table):
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def propose(connection, tool, arguments, now=NOW, settings=None):
    result = proposals.create(connection, tool, arguments, now, settings)
    assert list(result) == ["proposal"], result
    return result["proposal"]


@pytest.mark.parametrize(("tool", "arguments"), WRITES)
def test_a_proposal_changes_nothing_and_its_confirmation_applies_it(connection, tool, arguments):
    before = snapshot(connection)
    proposal = propose(connection, tool, arguments)
    assert snapshot(connection) == before
    assert proposal["tool"] == tool
    assert proposal["expires_at"] == "2026-03-17 12:00:00"
    assert len(proposal["id"]) >= 20
    assert status(connection, proposal["id"]) == "pending"

    history_before = count(connection, "history")
    result = proposals.confirm(connection, proposal["id"], NOW)
    assert "error" not in result
    assert snapshot(connection) != before
    assert count(connection, "history") > history_before
    assert status(connection, proposal["id"]) == "applied"
    assert not connection.in_transaction


def test_confirmation_returns_the_v1_result_and_matches_the_preview(connection):
    proposal = propose(connection, *WRITES[1])
    assert proposal["changes"] == [
        {
            "entity": "application",
            "record_id": 8,
            "field": "status",
            "old_value": "to_apply",
            "new_value": "applied",
        },
        {
            "entity": "application",
            "record_id": 8,
            "field": "applied_on",
            "old_value": None,
            "new_value": ON,
        },
    ]
    result = proposals.confirm(connection, proposal["id"], NOW)
    assert sorted(result) == ["history", "job"]
    assert result["job"]["status"] == "applied"
    assert [(line["field"], line["source"]) for line in result["history"]] == [
        ("status", "email"),
        ("applied_on", "email"),
    ]
    assert connection.execute("SELECT version FROM application WHERE id = 8").fetchone()[0] == 2


def test_add_job_preview_and_history_cover_the_new_company_job_and_application(connection):
    proposal = propose(connection, *WRITES[0])
    assert [(c["entity"], c["record_id"], c["field"]) for c in proposal["changes"]] == [
        ("company", None, "name"),
        ("job", None, "company"),
        ("job", None, "title"),
        ("job", None, "url"),
        ("application", None, "status"),
    ]
    job = proposals.confirm(connection, proposal["id"], NOW)
    lines = connection.execute(
        "SELECT entity, field, old_value, new_value, date, source_type FROM history ORDER BY id"
    ).fetchall()
    assert [tuple(line) for line in lines] == [
        ("company", "name", None, "Empresa Nova", ON, "user"),
        ("job", "company", None, "Empresa Nova", ON, "user"),
        ("job", "title", None, "Data Engineer", ON, "user"),
        ("job", "url", None, NEW_URL, ON, "user"),
        ("application", "status", None, "suggested", ON, "user"),
    ]
    assert job["url"] == NEW_URL


def test_validation_errors_come_back_at_once_without_a_proposal(connection):
    for tool, arguments, code in (
        ("add_job", {"company": "Banco Aurora", "title": "X", "url": "", "reference_date": ON}, "invalid_input"),
        ("add_job", {**WRITES[0][1], "source": "  "}, "invalid_input"),
        ("update_job", {"job_id": 1, "source": "", "reference_date": ON}, "invalid_input"),
        ("update_job", {"job_id": 99, "source": "user", "reference_date": ON}, "not_found"),
        ("update_job", {"job_id": 1, "source": "user", "reference_date": ON, "status": "x"}, "invalid_status"),
        ("log_interaction", {"contact_id": 1, "summary": "x", "date": "ontem"}, "invalid_date"),
    ):  # fmt: skip
        result = proposals.create(connection, tool, arguments, NOW)
        assert result["error"] == code
    assert count(connection, "proposal") == 0


def test_a_proposal_on_a_record_changed_since_then_is_stale(connection):
    before = propose(connection, "update_job", {**WRITES[1][1], "status": "in_review"})
    other = propose(connection, "update_job", {**WRITES[1][1], "next_step": "Outro passo"})
    proposals.confirm(connection, other["id"], NOW)
    changed = snapshot(connection)
    result = proposals.confirm(connection, before["id"], NOW)
    assert result["error"] == "stale_proposal"
    assert snapshot(connection) == changed
    assert status(connection, before["id"]) == "stale"
    assert proposals.confirm(connection, before["id"], NOW)["error"] == "stale_proposal"


@pytest.mark.parametrize(
    ("tool", "arguments", "other_arguments"),
    [
        (
            "network_save_company",
            {"company_id": 1, "name": "Banco Aurora", "priority": "A"},
            {"company_id": 1, "name": "Banco Aurora", "sector": "Finanças"},
        ),
        (
            "network_save_person",
            {"contact_id": 7, "name": "Gabriela Ensaio", "status": "on_hold"},
            {"contact_id": 7, "name": "Gabriela Ensaio", "next_step": "Outro passo"},
        ),
    ],
)
def test_a_network_proposal_on_a_record_changed_since_then_is_stale(
    connection, tool, arguments, other_arguments
):
    common = {"source": "user", "reference_date": ON}
    before = propose(connection, tool, {**arguments, **common})
    other = propose(connection, tool, {**other_arguments, **common})
    assert "error" not in proposals.confirm(connection, other["id"], NOW)
    changed = snapshot(connection)
    assert proposals.confirm(connection, before["id"], NOW)["error"] == "stale_proposal"
    assert snapshot(connection) == changed


def test_a_company_created_by_another_proposal_makes_the_duplicate_stale(connection):
    company = propose(connection, *WRITES[3])
    person = propose(connection, "network_save_person", {**WRITES[4][1], "company": "Empresa Nova"})
    assert person["changes"][0]["entity"] == "company"
    proposals.confirm(connection, company["id"], NOW)
    result = proposals.confirm(connection, person["id"], NOW)
    assert result["error"] == "stale_proposal"
    assert count(connection, "contact") == 8
    twin = proposals.create(connection, *WRITES[3], NOW)
    assert twin["error"] == "duplicate_company"


def test_a_proposal_whose_preview_changed_is_stale(connection):
    # Same company in two proposals: once the first creates it, the second's preview differs.
    first = propose(connection, *WRITES[0])
    second_arguments = {**WRITES[0][1], "url": f"{NEW_URL}-2"}
    second = propose(connection, "add_job", second_arguments)
    proposals.confirm(connection, first["id"], NOW)
    assert proposals.confirm(connection, second["id"], NOW)["error"] == "stale_proposal"
    assert count(connection, "job") == 16


def test_a_proposal_whose_operation_now_fails_is_stale_with_the_reason(connection):
    first = propose(connection, *WRITES[0])
    twin = propose(connection, *WRITES[0])
    proposals.confirm(connection, first["id"], NOW)
    result = proposals.confirm(connection, twin["id"], NOW)
    assert result["error"] == "stale_proposal"
    assert result["reason"]["error"] == "duplicate_url"
    assert count(connection, "job") == 16


def test_an_expired_proposal_is_refused_and_changes_nothing(connection):
    proposal = propose(connection, *WRITES[1])
    before = snapshot(connection)
    late = NOW + timedelta(hours=24)
    result = proposals.confirm(connection, proposal["id"], late)
    assert result["error"] == "expired_proposal"
    assert snapshot(connection) == before
    assert status(connection, proposal["id"]) == "expired"
    assert proposals.discard(connection, proposal["id"], late)["error"] == "expired_proposal"


def test_the_expiry_comes_from_the_settings(connection):
    settings = config.Settings(proposal_ttl_hours=1)
    proposal = propose(connection, *WRITES[1], settings=settings)
    assert proposal["expires_at"] == "2026-03-16 13:00:00"
    just_before = NOW + timedelta(minutes=59)
    assert "error" not in proposals.confirm(connection, proposal["id"], just_before)


def test_list_pending_marks_the_expired_ones_and_keeps_the_rest(connection):
    old = propose(connection, *WRITES[1])
    recent = propose(connection, *WRITES[2], now=NOW + timedelta(hours=10))
    pending = proposals.list_pending(connection, NOW + timedelta(hours=25))
    assert [item["id"] for item in pending] == [recent["id"]]
    assert pending[0]["changes"] == recent["changes"]
    assert pending[0]["created_at"] == "2026-03-16 22:00:00"
    assert status(connection, old["id"]) == "expired"


def test_a_discarded_proposal_changes_nothing_and_cannot_be_confirmed(connection):
    before = snapshot(connection)
    proposal = propose(connection, *WRITES[2])
    assert proposals.discard(connection, proposal["id"], NOW) == {
        "proposal": {"id": proposal["id"], "tool": "log_interaction", "status": "discarded"}
    }
    assert snapshot(connection) == before
    result = proposals.confirm(connection, proposal["id"], NOW)
    assert (result["error"], result["status"]) == ("not_found", "discarded")
    assert proposals.list_pending(connection, NOW) == []


def test_confirming_twice_does_not_apply_again(connection):
    proposal = propose(connection, *WRITES[2])
    proposals.confirm(connection, proposal["id"], NOW)
    after = snapshot(connection)
    again = proposals.confirm(connection, proposal["id"], NOW)
    assert (again["error"], again["status"]) == ("not_found", "applied")
    assert snapshot(connection) == after


def test_an_unknown_proposal_is_not_found(connection):
    assert proposals.confirm(connection, "nao-existe", NOW)["error"] == "not_found"
    assert proposals.discard(connection, "nao-existe", NOW)["error"] == "not_found"


def test_a_failure_while_applying_rolls_everything_back(connection, monkeypatch):
    proposal = propose(connection, *WRITES[0])
    before = snapshot(connection)

    def failing(*args, **kwargs):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(jobs.history, "record_creation", failing)
    with pytest.raises(RuntimeError):
        proposals.confirm(connection, proposal["id"], NOW)
    assert snapshot(connection) == before
    assert status(connection, proposal["id"]) == "pending"


def test_an_existing_version_2_database_gets_the_proposal_table(tmp_path):
    connection = db.connect(tmp_path / "v2.db")
    try:
        db.create_schema(connection)
        connection.execute("DROP TABLE proposal")
        db.create_schema(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert count(connection, "proposal") == 0
    finally:
        connection.close()


def stored(connection, proposal_id):
    row = connection.execute(
        "SELECT tool, status, arguments, preview, created_at, expires_at FROM proposal"
        " WHERE id = ?",
        (proposal_id,),
    )
    return tuple(row.fetchone())


def test_proposals_that_will_never_apply_keep_no_arguments_or_preview(connection):
    discarded = propose(connection, *WRITES[2])
    proposals.discard(connection, discarded["id"], NOW)
    expired = propose(connection, *WRITES[1])
    proposals.list_pending(connection, NOW + timedelta(hours=24))
    stale = propose(connection, "update_job", {**WRITES[1][1], "next_step": "Primeiro"})
    other = propose(connection, "update_job", {**WRITES[1][1], "next_step": "Segundo"})
    proposals.confirm(connection, other["id"], NOW)
    proposals.confirm(connection, stale["id"], NOW)
    for proposal, status_, tool in (
        (discarded, "discarded", "log_interaction"),
        (expired, "expired", "update_job"),
        (stale, "stale", "update_job"),
    ):
        assert stored(connection, proposal["id"]) == (
            tool,
            status_,
            "{}",
            "{}",
            "2026-03-16 12:00:00",
            proposal["expires_at"],
        )
    applied = stored(connection, other["id"])
    assert applied[1] == "applied"
    assert "Segundo" in applied[2]
