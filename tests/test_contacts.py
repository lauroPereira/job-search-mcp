import json
from datetime import date

from helpers import write

from job_search_mcp import contacts, domain, jobs, summary


def count(connection, table):
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def rows(connection, table):
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]


def job_history(connection):
    """History lines written for applications (the job side of an interaction)."""
    query = "SELECT * FROM history WHERE entity = 'application' ORDER BY id"
    return [dict(row) for row in connection.execute(query)]


def test_list_contacts_returns_all_seed_contacts_with_follow_up(connection):
    result = contacts.list_contacts(connection)
    assert [contact["id"] for contact in result] == list(range(1, 9))
    follow_ups = {contact["id"]: contact["follow_up"] for contact in result}
    assert follow_ups == {
        1: "2026-03-14",  # last interaction 2026-03-08 plus 6 days
        2: "2026-03-17",
        3: "2026-03-20",
        4: "2026-03-16",
        5: None,  # to_contact
        6: None,  # closed, even with a last interaction date
        7: "2026-03-18",
        8: None,  # to_contact
    }
    json.dumps(result)  # serializable: plain dicts, dates as ISO text


def test_contacts_in_closed_or_to_contact_status_have_no_follow_up(connection):
    for status in ("closed", "to_contact"):
        result = contacts.list_contacts(connection, status=status)
        assert result
        assert all(contact["follow_up"] is None for contact in result)
    closed = contacts.list_contacts(connection, status="closed")[0]
    assert closed["last_contact_on"] == "2026-02-25"


def test_list_contacts_filters_by_status_and_company(connection):
    in_conversation = contacts.list_contacts(connection, status="in_conversation")
    assert [contact["id"] for contact in in_conversation] == [2, 7]
    assert [c["id"] for c in contacts.list_contacts(connection, company="Banco Aurora")] == [1]
    assert [c["id"] for c in contacts.list_contacts(connection, company="banco aurora")] == [1]
    both = contacts.list_contacts(connection, status="to_contact", company="Escola Mirante")
    assert [contact["id"] for contact in both] == [8]
    assert contacts.list_contacts(connection, status="closed", company="Banco Aurora") == []


def test_list_contacts_with_invalid_status_returns_error(connection):
    result = contacts.list_contacts(connection, status="applied")
    assert result["error"] == "invalid_status"
    assert result["valid_statuses"] == list(domain.CONTACT_STATUSES)


def test_log_interaction_moves_follow_up_to_interaction_date_plus_six_days(
    connection, reference_date
):
    result = write(
        connection,
        contacts.plan_log_interaction(connection, 7, "Conversa de acompanhamento", reference_date),
    )
    assert result["follow_up"] == "2026-03-22"
    assert result["contact"]["last_contact_on"] == "2026-03-16"
    assert result["contact"]["follow_up"] == "2026-03-22"
    assert result["contact"]["status"] == "in_conversation"  # not informed: kept
    assert result["contact"]["next_step"] == "Marcar conversa de acompanhamento"
    assert result["job"] is None  # contact 7 has no linked job
    assert rows(connection, "interaction") == [
        {
            "id": 1,
            "contact_id": 7,
            "date": "2026-03-16",
            "summary": "Conversa de acompanhamento",
            "channel": None,
            "source_type": None,
        }
    ]
    assert job_history(connection) == []
    json.dumps(result)


def test_log_interaction_accepts_iso_text_and_updates_status_and_next_step(connection):
    result = write(
        connection,
        contacts.plan_log_interaction(
            connection,
            8,
            "Primeira conversa",
            "2026-03-16",
            status="in_conversation",
            next_step="Enviar currículo",
        ),
    )
    assert result["contact"]["status"] == "in_conversation"
    assert result["contact"]["next_step"] == "Enviar currículo"
    assert result["contact"]["last_contact_on"] == "2026-03-16"
    assert result["follow_up"] == "2026-03-22"


def test_log_interaction_that_leaves_contact_in_status_without_follow_up(connection):
    result = write(
        connection,
        contacts.plan_log_interaction(connection, 1, "Encerrou o contato", "2026-03-16", "closed"),
    )
    assert result["contact"]["status"] == "closed"
    assert result["contact"]["last_contact_on"] == "2026-03-16"
    assert result["follow_up"] is None


def test_log_interaction_updates_last_contact_of_linked_job_with_history(
    connection, reference_date
):
    before = jobs.get_job(connection, 1)
    assert before["last_contact_on"] == "2026-03-09"
    result = write(
        connection,
        contacts.plan_log_interaction(connection, 1, "Respondeu sobre a indicação", reference_date),
    )
    assert result["job"]["id"] == 1
    assert result["job"]["last_contact_on"] == "2026-03-16"
    assert result["job"]["follow_up"] == "2026-03-23"
    assert jobs.get_job(connection, 1) == result["job"]
    history = job_history(connection)
    assert len(history) == 1
    assert history[0]["record_id"] == 1  # the application of job 1
    assert history[0]["date"] == "2026-03-16"
    assert history[0]["field"] == "last_contact_on"
    assert history[0]["old_value"] == "2026-03-09"
    assert history[0]["new_value"] == "2026-03-16"
    assert history[0]["source_type"] == "user"
    assert history[0]["source_ref"] == contacts.INTERACTION_SOURCE == "contact_interaction"


def test_log_interaction_sets_last_contact_of_linked_job_that_had_none(connection):
    result = write(
        connection, contacts.plan_log_interaction(connection, 2, "Combinou horários", "2026-03-15")
    )
    assert result["job"]["id"] == 2
    assert result["job"]["last_contact_on"] == "2026-03-15"
    assert result["job"]["follow_up"] == "2026-03-22"  # now counts from the contact, not applied_on
    history = job_history(connection)
    assert history[0]["old_value"] is None
    assert history[0]["new_value"] == "2026-03-15"


def test_log_interaction_older_than_last_contact_keeps_the_most_recent_dates(connection):
    result = write(
        connection,
        contacts.plan_log_interaction(connection, 1, "Conversa antiga", date(2026, 3, 1)),
    )
    assert result["contact"]["last_contact_on"] == "2026-03-08"
    assert result["follow_up"] == "2026-03-14"
    assert result["job"]["last_contact_on"] == "2026-03-09"
    assert count(connection, "interaction") == 1
    assert job_history(connection) == []


def test_log_interaction_unknown_contact_returns_error(connection, reference_date):
    result = write(
        connection, contacts.plan_log_interaction(connection, 999, "Conversa", reference_date)
    )
    assert result["error"] == "not_found"
    assert "999" in result["detail"]
    assert count(connection, "interaction") == 0


def test_log_interaction_with_invalid_status_returns_error_and_changes_nothing(
    connection, reference_date
):
    before = contacts.get_contact(connection, 1)
    job_before = jobs.get_job(connection, 1)
    result = write(
        connection,
        contacts.plan_log_interaction(connection, 1, "Conversa", reference_date, status="applied"),
    )
    assert result["error"] == "invalid_status"
    assert result["valid_statuses"] == list(domain.CONTACT_STATUSES)
    assert "awaiting_reply" in result["detail"]
    assert contacts.get_contact(connection, 1) == before
    assert jobs.get_job(connection, 1) == job_before
    assert count(connection, "interaction") == 0
    assert job_history(connection) == []


def test_log_interaction_requires_summary_and_valid_date(connection, reference_date):
    assert (
        write(connection, contacts.plan_log_interaction(connection, 1, " ", reference_date))[
            "error"
        ]
        == "invalid_input"
    )
    assert (
        write(connection, contacts.plan_log_interaction(connection, 1, "Conversa", "16/03"))[
            "error"
        ]
        == "invalid_date"
    )
    assert (
        write(connection, contacts.plan_log_interaction(connection, 1, "Conversa", None))["error"]
        == "invalid_date"
    )
    assert count(connection, "interaction") == 0


def test_log_interaction_without_status_moves_to_contact_to_awaiting_reply(
    connection, reference_date
):
    before = contacts.get_contact(connection, 8)
    assert before["status"] == "to_contact"
    assert before["follow_up"] is None
    result = write(
        connection,
        contacts.plan_log_interaction(connection, 8, "Primeira mensagem enviada", reference_date),
    )
    assert result["contact"]["status"] == "awaiting_reply"
    assert result["contact"]["last_contact_on"] == "2026-03-16"
    assert result["follow_up"] == "2026-03-22"  # interaction date plus 6 days
    assert result["contact"]["follow_up"] == "2026-03-22"
    assert result["contact"]["next_step"] == before["next_step"]  # not informed: kept
    assert contacts.get_contact(connection, 8) == result["contact"]
    assert [c["id"] for c in contacts.list_contacts(connection, status="to_contact")] == [5]


def test_log_interaction_with_explicit_status_on_to_contact_keeps_the_informed_status(
    connection, reference_date
):
    result = write(
        connection,
        contacts.plan_log_interaction(
            connection, 8, "Conversa por telefone", reference_date, status="in_conversation"
        ),
    )
    assert result["contact"]["status"] == "in_conversation"
    assert result["follow_up"] == "2026-03-22"
    # Explicitly keeping to_contact is respected too: the contact stays without a follow-up.
    kept = write(
        connection,
        contacts.plan_log_interaction(
            connection, 5, "Tentativa sem resposta", reference_date, status="to_contact"
        ),
    )
    assert kept["contact"]["status"] == "to_contact"
    assert kept["follow_up"] is None


def test_log_interaction_without_status_keeps_the_status_of_other_contacts(
    connection, reference_date
):
    # Only to_contact advances by itself; a closed contact stays closed.
    result = write(
        connection,
        contacts.plan_log_interaction(connection, 6, "Mensagem de cortesia", reference_date),
    )
    assert result["contact"]["status"] == "closed"
    assert result["follow_up"] is None


def test_list_contacts_company_filter_ignores_case_accents_and_spaces(connection):
    for spelling in ("Transportadora Pampa", "TRANSPORTADORA PAMPA", " transportadora  pampá "):
        assert [c["id"] for c in contacts.list_contacts(connection, company=spelling)] == [3]
    assert contacts.list_contacts(connection, company="Transportadora") == []


def save_person(connection, **arguments):
    return contacts.plan_save_person(
        connection, **{"source": "conversation", "reference_date": date(2026, 3, 16), **arguments}
    )


def history_of(connection, entity, record_id):
    query = (
        "SELECT field, old_value, new_value FROM history"
        " WHERE entity = ? AND record_id = ? ORDER BY id"
    )
    return [tuple(row) for row in connection.execute(query, (entity, record_id))]


def test_save_person_with_a_new_company_plans_both_creations(connection):
    companies_before = count(connection, "company")
    plan = save_person(connection, name="Iara Nova", company=" Empresa Zeta ", role_title="CTO")
    assert [(c["entity"], c["record_id"], c["field"], c["new_value"]) for c in plan.changes] == [
        ("company", None, "name", "Empresa Zeta"),
        ("contact", None, "name", "Iara Nova"),
        ("contact", None, "company", "Empresa Zeta"),
        ("contact", None, "role_title", "CTO"),
        ("contact", None, "status", "to_contact"),
    ]
    assert count(connection, "company") == companies_before
    contact = write(connection, plan)["contact"]
    assert (contact["name"], contact["company"], contact["status"]) == (
        "Iara Nova",
        "Empresa Zeta",
        "to_contact",
    )
    assert count(connection, "company") == companies_before + 1
    assert history_of(connection, "company", contact["company_id"]) == [
        ("name", None, "Empresa Zeta")
    ]
    assert history_of(connection, "contact", contact["id"]) == [
        ("name", None, "Iara Nova"),
        ("company", None, "Empresa Zeta"),
        ("role_title", None, "CTO"),
        ("status", None, "to_contact"),
    ]


def test_save_person_finds_the_company_by_normalized_name(connection):
    plan = save_person(connection, name="João Exemplo", company="banco  AURORA")
    assert [c["entity"] for c in plan.changes] == ["contact"] * 3
    contact = write(connection, plan)["contact"]
    assert (contact["company"], contact["company_id"]) == ("Banco Aurora", 1)


def test_save_person_changes_only_the_informed_fields(connection):
    before = contacts.get_contact(connection, 2)
    plan = save_person(connection, contact_id=2, role_title="Tech Recruiter")
    assert plan.base_versions == {"contact:2": 1}
    assert [(c["field"], c["old_value"], c["new_value"]) for c in plan.changes] == [
        ("role_title", None, "Tech Recruiter")
    ]
    after = write(connection, plan)["contact"]
    assert after == {**before, "role_title": "Tech Recruiter"}
    assert connection.execute("SELECT version FROM contact WHERE id = 2").fetchone()[0] == 2


def test_save_person_moves_the_person_to_another_company_recorded_by_name(connection):
    contact = write(
        connection,
        save_person(connection, contact_id=7, name="Gabriela Ensaio", company="Loja Horizonte"),
    )["contact"]
    assert (contact["company"], contact["company_id"]) == ("Loja Horizonte", 2)
    assert history_of(connection, "contact", 7) == [
        ("company", "Consultoria Tangará", "Loja Horizonte")
    ]


def test_save_person_on_hold_leaves_the_follow_ups(connection, reference_date):
    pending = summary.pending_followups(connection, reference_date)
    assert 1 in [contact["id"] for contact in pending["contacts"]]
    contact = write(connection, save_person(connection, contact_id=1, status="on_hold"))["contact"]
    assert (contact["status"], contact["follow_up"]) == ("on_hold", None)
    pending = summary.pending_followups(connection, reference_date)
    assert 1 not in [contact["id"] for contact in pending["contacts"]]


def test_save_person_validation_errors(connection):
    assert save_person(connection, name=" ")["error"] == "invalid_input"
    assert save_person(connection, role_title="CTO")["error"] == "invalid_input"
    assert save_person(connection, name="X", status="ghosted")["error"] == "invalid_status"
    assert save_person(connection, name="X", contact_id=99)["error"] == "not_found"
    assert save_person(connection, name="X", source="")["error"] == "invalid_input"
    assert save_person(connection, name="X", reference_date="x")["error"] == "invalid_date"
