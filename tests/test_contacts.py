import json
from datetime import date

from job_search_mcp import contacts, domain, jobs


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
    result = contacts.log_interaction(connection, 7, "Conversa de acompanhamento", reference_date)
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
    result = contacts.log_interaction(
        connection,
        8,
        "Primeira conversa",
        "2026-03-16",
        status="in_conversation",
        next_step="Enviar currículo",
    )
    assert result["contact"]["status"] == "in_conversation"
    assert result["contact"]["next_step"] == "Enviar currículo"
    assert result["contact"]["last_contact_on"] == "2026-03-16"
    assert result["follow_up"] == "2026-03-22"


def test_log_interaction_that_leaves_contact_in_status_without_follow_up(connection):
    result = contacts.log_interaction(connection, 1, "Encerrou o contato", "2026-03-16", "closed")
    assert result["contact"]["status"] == "closed"
    assert result["contact"]["last_contact_on"] == "2026-03-16"
    assert result["follow_up"] is None


def test_log_interaction_updates_last_contact_of_linked_job_with_history(
    connection, reference_date
):
    before = jobs.get_job(connection, 1)
    assert before["last_contact_on"] == "2026-03-09"
    result = contacts.log_interaction(connection, 1, "Respondeu sobre a indicação", reference_date)
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
    result = contacts.log_interaction(connection, 2, "Combinou horários", "2026-03-15")
    assert result["job"]["id"] == 2
    assert result["job"]["last_contact_on"] == "2026-03-15"
    assert result["job"]["follow_up"] == "2026-03-22"  # now counts from the contact, not applied_on
    history = job_history(connection)
    assert history[0]["old_value"] is None
    assert history[0]["new_value"] == "2026-03-15"


def test_log_interaction_older_than_last_contact_keeps_the_most_recent_dates(connection):
    result = contacts.log_interaction(connection, 1, "Conversa antiga", date(2026, 3, 1))
    assert result["contact"]["last_contact_on"] == "2026-03-08"
    assert result["follow_up"] == "2026-03-14"
    assert result["job"]["last_contact_on"] == "2026-03-09"
    assert count(connection, "interaction") == 1
    assert job_history(connection) == []


def test_log_interaction_unknown_contact_returns_error(connection, reference_date):
    result = contacts.log_interaction(connection, 999, "Conversa", reference_date)
    assert result["error"] == "not_found"
    assert "999" in result["detail"]
    assert count(connection, "interaction") == 0


def test_log_interaction_with_invalid_status_returns_error_and_changes_nothing(
    connection, reference_date
):
    before = contacts.get_contact(connection, 1)
    job_before = jobs.get_job(connection, 1)
    result = contacts.log_interaction(connection, 1, "Conversa", reference_date, status="applied")
    assert result["error"] == "invalid_status"
    assert result["valid_statuses"] == list(domain.CONTACT_STATUSES)
    assert "awaiting_reply" in result["detail"]
    assert contacts.get_contact(connection, 1) == before
    assert jobs.get_job(connection, 1) == job_before
    assert count(connection, "interaction") == 0
    assert job_history(connection) == []


def test_log_interaction_requires_summary_and_valid_date(connection, reference_date):
    assert contacts.log_interaction(connection, 1, " ", reference_date)["error"] == "invalid_input"
    assert contacts.log_interaction(connection, 1, "Conversa", "16/03")["error"] == "invalid_date"
    assert contacts.log_interaction(connection, 1, "Conversa", None)["error"] == "invalid_date"
    assert count(connection, "interaction") == 0


def test_log_interaction_without_status_moves_to_contact_to_awaiting_reply(
    connection, reference_date
):
    before = contacts.get_contact(connection, 8)
    assert before["status"] == "to_contact"
    assert before["follow_up"] is None
    result = contacts.log_interaction(connection, 8, "Primeira mensagem enviada", reference_date)
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
    result = contacts.log_interaction(
        connection, 8, "Conversa por telefone", reference_date, status="in_conversation"
    )
    assert result["contact"]["status"] == "in_conversation"
    assert result["follow_up"] == "2026-03-22"
    # Explicitly keeping to_contact is respected too: the contact stays without a follow-up.
    kept = contacts.log_interaction(
        connection, 5, "Tentativa sem resposta", reference_date, status="to_contact"
    )
    assert kept["contact"]["status"] == "to_contact"
    assert kept["follow_up"] is None


def test_log_interaction_without_status_keeps_the_status_of_other_contacts(
    connection, reference_date
):
    # Only to_contact advances by itself; a closed contact stays closed.
    result = contacts.log_interaction(connection, 6, "Mensagem de cortesia", reference_date)
    assert result["contact"]["status"] == "closed"
    assert result["follow_up"] is None


def test_list_contacts_company_filter_ignores_case_accents_and_spaces(connection):
    for spelling in ("Transportadora Pampa", "TRANSPORTADORA PAMPA", " transportadora  pampá "):
        assert [c["id"] for c in contacts.list_contacts(connection, company=spelling)] == [3]
    assert contacts.list_contacts(connection, company="Transportadora") == []
