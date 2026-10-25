"""Contact operations: list contacts and log interactions, keeping the linked job in step.

A contact is read with its company and keeps the keys of v0.1.0: `company` is the name of
the company and `job_id` the job of the first application the person is linked to with the
role 'contact' (null when there is none). `company_id` and `role_title` are additive.
"""

import datetime
import sqlite3

from job_search_mcp import db, domain, history, jobs
from job_search_mcp.config import DEFAULT_SETTINGS, Settings
from job_search_mcp.db import to_date

# Origin written in the history for the changes an interaction makes (contact and job).
INTERACTION_SOURCE_TYPE = domain.USER_SOURCE
INTERACTION_SOURCE = "contact_interaction"
# The first logged conversation takes a contact out of "to contact", so it gets a follow-up.
NOT_CONTACTED_STATUS = "to_contact"
FIRST_INTERACTION_STATUS = "awaiting_reply"

# Contact and company joined, with the keys (and their order) of v0.1.0.
CONTACT_SELECT = """
SELECT contact.id, contact.name, company.name AS company, contact.relationship,
    contact.channel, contact.status, contact.next_step, contact.last_contact_on,
    (
        SELECT application.job_id FROM application_person
        JOIN application ON application.id = application_person.application_id
        WHERE application_person.contact_id = contact.id AND application_person.role = 'contact'
        ORDER BY application.id LIMIT 1
    ) AS job_id,
    contact.company_id, contact.role_title
FROM contact
LEFT JOIN company ON company.id = contact.company_id
"""


def contact_to_dict(row: sqlite3.Row, settings: Settings | None = None) -> dict:
    """Turn a contact row into a plain dict, adding the calculated follow-up (ISO or None).

    The follow-up days come from `settings` (None: the defaults).
    """
    contact = dict(row)
    days = (settings or DEFAULT_SETTINGS).contact_follow_up_days
    follow_up = domain.contact_follow_up(contact["last_contact_on"], contact["status"], days=days)
    contact["follow_up"] = follow_up.isoformat() if follow_up else None
    return contact


def get_contact(
    connection: sqlite3.Connection, contact_id: int, settings: Settings | None = None
) -> dict | None:
    row = connection.execute(f"{CONTACT_SELECT} WHERE contact.id = ?", (contact_id,)).fetchone()
    return contact_to_dict(row, settings) if row else None


def list_contacts(
    connection: sqlite3.Connection,
    status: str | None = None,
    company: str | None = None,
    settings: Settings | None = None,
) -> list[dict] | dict:
    """List contacts ordered by id, optionally filtered by status and company.

    The company filter matches the whole name, compared by normalized name (db.normalize_name:
    case, accents and extra spaces are ignored).
    """
    if status is not None and status not in domain.CONTACT_STATUSES:
        return domain.invalid_status(status, domain.CONTACT_STATUSES)
    conditions, parameters = [], []
    for condition, value in (
        ("contact.status = ?", status),
        ("company.normalized_name = ?", db.normalize_name(company) if company else company),
    ):
        if value is not None:
            conditions.append(condition)
            parameters.append(value)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = connection.execute(f"{CONTACT_SELECT}{where} ORDER BY contact.id", parameters)
    return [contact_to_dict(row, settings) for row in rows]


def plan_log_interaction(
    connection: sqlite3.Connection,
    contact_id: int,
    summary: str,
    date: str | datetime.date,
    status: str | None = None,
    next_step: str | None = None,
    settings: Settings | None = None,
) -> domain.Plan | dict:
    """Plan the record of an interaction with a contact, without writing anything.

    The plan adds the interaction and updates the last contact date of the contact and,
    when informed, its status and next step. A contact in to_contact logged without a
    status moves to awaiting_reply, so it starts to have a follow-up; an informed status
    always prevails. If the contact is linked to a job, the last contact date of the job
    is updated too. Every field that changes, of the contact or of the job, gets a history
    line. A last contact date never moves backwards: logging an older interaction keeps
    the more recent date. The plan depends on the versions of the contact and of the
    linked application; applying it returns the updated contact, its new follow-up and
    the linked job (None when there is none). Errors are structured and nothing is planned.
    """
    if not summary or not summary.strip():
        return domain.error("invalid_input", "Field 'summary' is required.")
    try:
        interaction_date = to_date(date)
    except (ValueError, TypeError):
        interaction_date = None
    if interaction_date is None:
        return domain.invalid_date("date", date)
    contact = get_contact(connection, contact_id, settings)
    if contact is None:
        return domain.not_found("contact", contact_id)
    if status is not None and status not in domain.CONTACT_STATUSES:
        return domain.invalid_status(status, domain.CONTACT_STATUSES)

    if status is None and contact["status"] == NOT_CONTACTED_STATUS:
        status = FIRST_INTERACTION_STATUS

    interaction_on = interaction_date.isoformat()
    interaction = {"contact_id": contact_id, "date": interaction_on, "summary": summary.strip()}
    contact_changes = {
        "last_contact_on": max(interaction_on, contact["last_contact_on"] or ""),
        "status": status if status is not None else contact["status"],
        "next_step": next_step if next_step is not None else contact["next_step"],
    }
    changes = history.creation("interaction", interaction)
    changes += history.diff("contact", contact_id, contact, contact_changes)
    base_versions = {
        f"contact:{contact_id}": history.read_version(connection, "contact", contact_id)
    }
    job = jobs.get_job(connection, contact["job_id"], settings) if contact["job_id"] else None
    job_changes = {}
    if job:
        application_id = jobs.application_id(connection, job["id"])
        base_versions[f"application:{application_id}"] = history.read_version(
            connection, "application", application_id
        )
        if interaction_on > (job["last_contact_on"] or ""):
            job_changes = {"last_contact_on": interaction_on}
            changes += history.diff("application", application_id, job, job_changes)

    def apply() -> dict:
        connection.execute(
            "INSERT INTO interaction (contact_id, date, summary) VALUES (?, ?, ?)",
            (contact_id, interaction_on, interaction["summary"]),
        )
        history.record_changes(
            connection,
            "contact",
            contact_id,
            contact,
            contact_changes,
            interaction_date,
            INTERACTION_SOURCE_TYPE,
            INTERACTION_SOURCE,
        )
        if job_changes:
            jobs.apply_job_changes(
                connection,
                job,
                job_changes,
                INTERACTION_SOURCE_TYPE,
                INTERACTION_SOURCE,
                interaction_date,
            )
        updated = get_contact(connection, contact_id, settings)
        return {
            "contact": updated,
            "follow_up": updated["follow_up"],
            "job": jobs.get_job(connection, job["id"], settings) if job else None,
        }

    return domain.Plan(changes=changes, base_versions=base_versions, apply=apply)
