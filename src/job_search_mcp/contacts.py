"""Contact operations: list contacts and log interactions, keeping the linked job in step."""

import datetime
import sqlite3

from job_search_mcp import domain, jobs
from job_search_mcp.config import DEFAULT_SETTINGS, Settings
from job_search_mcp.db import to_date

# Source written in job_history when an interaction moves the last contact date of a job.
INTERACTION_SOURCE = "contact_interaction"
# The first logged conversation takes a contact out of "to contact", so it gets a follow-up.
NOT_CONTACTED_STATUS = "to_contact"
FIRST_INTERACTION_STATUS = "awaiting_reply"


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
    row = connection.execute("SELECT * FROM contact WHERE id = ?", (contact_id,)).fetchone()
    return contact_to_dict(row, settings) if row else None


def list_contacts(
    connection: sqlite3.Connection,
    status: str | None = None,
    company: str | None = None,
    settings: Settings | None = None,
) -> list[dict] | dict:
    """List contacts ordered by id, optionally filtered by status and company.

    The company filter matches the whole name, ignoring case for unaccented letters.
    """
    if status is not None and status not in domain.CONTACT_STATUSES:
        return domain.invalid_status(status, domain.CONTACT_STATUSES)
    conditions, parameters = [], []
    for condition, value in (("status = ?", status), ("company = ? COLLATE NOCASE", company)):
        if value is not None:
            conditions.append(condition)
            parameters.append(value)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = connection.execute(f"SELECT * FROM contact{where} ORDER BY id", parameters)
    return [contact_to_dict(row, settings) for row in rows]


def log_interaction(
    connection: sqlite3.Connection,
    contact_id: int,
    summary: str,
    date: str | datetime.date,
    status: str | None = None,
    next_step: str | None = None,
    settings: Settings | None = None,
) -> dict:
    """Record an interaction with a contact and refresh its follow-up.

    Updates the last contact date of the contact and, when informed, its status and next
    step. A contact in to_contact logged without a status moves to awaiting_reply, so it
    starts to have a follow-up; an informed status always prevails. If the contact is
    linked to a job, the last contact date of the job is updated
    too, with a job_history line. A last contact date never moves backwards: logging an
    older interaction keeps the more recent date. Returns the updated contact, its new
    follow-up and the linked job (None when there is none), or a structured error without
    changing anything.
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
    job = jobs.get_job(connection, contact["job_id"], settings) if contact["job_id"] else None
    with connection:
        connection.execute(
            "INSERT INTO interaction (contact_id, date, summary) VALUES (?, ?, ?)",
            (contact_id, interaction_on, summary.strip()),
        )
        connection.execute(
            "UPDATE contact SET last_contact_on = ?, status = ?, next_step = ? WHERE id = ?",
            (
                max(interaction_on, contact["last_contact_on"] or ""),
                status if status is not None else contact["status"],
                next_step if next_step is not None else contact["next_step"],
                contact_id,
            ),
        )
        if job and interaction_on > (job["last_contact_on"] or ""):
            jobs.apply_job_changes(
                connection,
                job,
                {"last_contact_on": interaction_on},
                INTERACTION_SOURCE,
                interaction_date,
            )
    contact = get_contact(connection, contact_id, settings)
    return {
        "contact": contact,
        "follow_up": contact["follow_up"],
        "job": jobs.get_job(connection, job["id"], settings) if job else None,
    }
