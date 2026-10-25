from datetime import date

import pytest
from helpers import write

from job_search_mcp import contacts, domain, history, jobs

ON = date(2026, 3, 16)


def lines(connection, entity):
    query = "SELECT * FROM history WHERE entity = ? ORDER BY id"
    return [dict(row) for row in connection.execute(query, (entity,))]


def version(connection, table, record_id):
    query = f"SELECT version FROM {table} WHERE id = ?"
    return connection.execute(query, (record_id,)).fetchone()[0]


def test_split_source_keeps_known_types_and_turns_free_text_into_user():
    assert history.split_source("email") == ("email", None)
    assert history.split_source(" user ") == ("user", None)
    assert history.split_source("Ligação do RH") == ("user", "Ligação do RH")


def test_record_changes_writes_only_real_changes_and_bumps_the_version_once(connection):
    contact = contacts.get_contact(connection, 7)
    with connection:
        created = history.record_changes(
            connection,
            "contact",
            7,
            contact,
            {"status": "on_hold", "next_step": contact["next_step"]},
            ON,
            "meeting",
            "Reunião semanal",
        )
    assert created == [
        {
            "entity": "contact",
            "record_id": 7,
            "field": "status",
            "old_value": "in_conversation",
            "new_value": "on_hold",
            "date": "2026-03-16",
            "source_type": "meeting",
            "source_ref": "Reunião semanal",
        }
    ]
    assert [
        {key: line[key] for key in created[0]} for line in lines(connection, "contact")
    ] == created
    assert version(connection, "contact", 7) == 2
    assert contacts.get_contact(connection, 7)["status"] == "on_hold"


def test_record_changes_without_change_writes_nothing(connection):
    contact = contacts.get_contact(connection, 7)
    with connection:
        assert (
            history.record_changes(
                connection, "contact", 7, contact, {"status": contact["status"]}, ON, "user"
            )
            == []
        )
    assert lines(connection, "contact") == []
    assert version(connection, "contact", 7) == 1


@pytest.mark.parametrize(
    ("entity", "changes", "source_type", "message"),
    [
        ("job", {"title": "x"}, "user", "Entity"),
        ("contact", {"name": "x"}, "user", "name"),
        ("contact", {"status": "closed"}, "rumor", "source type"),
    ],
)
def test_record_changes_refuses_unknown_entity_field_or_source(
    connection, entity, changes, source_type, message
):
    before = connection.total_changes
    with pytest.raises(ValueError, match=message):
        history.record_changes(
            connection, entity, 1, contacts.get_contact(connection, 1), changes, ON, source_type
        )
    assert connection.total_changes == before


def test_update_job_with_a_known_source_type_stores_it_without_reference(connection):
    result = write(
        connection, jobs.plan_update_job(connection, 3, "email", ON, status="hr_interview")
    )
    assert result["history"][0]["source"] == "email"
    stored = lines(connection, "application")
    assert (stored[0]["source_type"], stored[0]["source_ref"]) == ("email", None)
    assert version(connection, "application", 3) == 2


def test_log_interaction_records_the_contact_changes_in_history(connection):
    write(
        connection,
        contacts.plan_log_interaction(connection, 5, "Primeira mensagem", ON, next_step="Aguardar"),
    )
    stored = {line["field"]: line for line in lines(connection, "contact")}
    assert set(stored) == {"last_contact_on", "status", "next_step"}
    assert (stored["status"]["old_value"], stored["status"]["new_value"]) == (
        "to_contact",
        "awaiting_reply",
    )
    assert all(line["record_id"] == 5 for line in stored.values())
    assert all(line["source_type"] == domain.USER_SOURCE for line in stored.values())
    assert all(line["source_ref"] == contacts.INTERACTION_SOURCE for line in stored.values())


def test_on_hold_has_no_follow_up_and_still_counts_as_active(connection, reference_date):
    from job_search_mcp import summary

    write(connection, jobs.plan_update_job(connection, 1, "user", reference_date, status="on_hold"))
    write(
        connection,
        contacts.plan_log_interaction(
            connection, 1, "Pausou o processo", reference_date, status="on_hold"
        ),
    )
    assert jobs.get_job(connection, 1)["follow_up"] is None
    assert contacts.get_contact(connection, 1)["follow_up"] is None
    pending = summary.pending_followups(connection, reference_date)
    assert 1 not in [job["id"] for job in pending["jobs"]]
    assert 1 not in [contact["id"] for contact in pending["contacts"]]
    result = summary.daily_summary(connection, reference_date)
    assert result["jobs_by_status"]["on_hold"] == 1
    assert result["active_contacts"] == 7  # on_hold is not closed
    assert [job["id"] for job in jobs.list_jobs(connection, status="on_hold")] == [1]
    assert [c["id"] for c in contacts.list_contacts(connection, status="on_hold")] == [1]


def test_reads_keep_the_v1_keys_and_add_company_id_and_role_title(connection):
    job = jobs.get_job(connection, 1)
    assert list(job) == [
        "id", "company", "title", "url", "track", "score", "status", "next_step",
        "applied_on", "last_contact_on", "created_at", "company_id", "follow_up",
    ]  # fmt: skip
    contact = contacts.get_contact(connection, 1)
    assert list(contact) == [
        "id", "name", "company", "relationship", "channel", "status", "next_step",
        "last_contact_on", "job_id", "company_id", "role_title", "follow_up",
    ]  # fmt: skip
    assert contact["company"] == job["company"] == "Banco Aurora"
    assert contact["company_id"] == job["company_id"]
    assert contact["job_id"] == 1
    assert contact["role_title"] is None
