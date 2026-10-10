"""Queries that answer "what needs attention" and "what to do today"."""

import sqlite3
from datetime import date

from job_search_mcp import domain
from job_search_mcp.contacts import list_contacts
from job_search_mcp.db import to_date
from job_search_mcp.jobs import list_jobs

QUEUE_STATUSES = ("suggested", "to_apply")


def _pending(records: list[dict], reference_date: date, days_ahead: int) -> list[dict]:
    """Keep the records whose follow-up is overdue or due soon, oldest follow-up first.

    Records without a follow-up (closed status, or one that does not generate it) are left out.
    """
    pending = []
    for record in records:
        if record["follow_up"] is None:
            continue
        state = domain.classify(to_date(record["follow_up"]), reference_date, days_ahead)
        if state != domain.ON_TRACK:
            pending.append({**record, "state": state})
    return sorted(pending, key=lambda record: (record["follow_up"], record["id"]))


def pending_followups(
    connection: sqlite3.Connection,
    reference_date: str | date,
    days_ahead: int = 2,
) -> dict:
    """Jobs and contacts whose follow-up is overdue or due within `days_ahead` days.

    Each item is the job or contact plus `follow_up` and `state` (overdue or due_soon),
    ordered from the oldest follow-up to the most recent.
    """
    try:
        reference = to_date(reference_date)
    except (ValueError, TypeError):
        reference = None
    if reference is None:
        return domain.invalid_date("reference_date", reference_date)
    return {
        "reference_date": reference.isoformat(),
        "days_ahead": days_ahead,
        "jobs": _pending(list_jobs(connection), reference, days_ahead),
        "contacts": _pending(list_contacts(connection), reference, days_ahead),
    }


def daily_summary(
    connection: sqlite3.Connection,
    reference_date: str | date,
    deadline: str | date | None = None,
) -> dict:
    """Summary of the day: counts, overdue and due-soon items and the application queue.

    `jobs_by_status` brings every job status, including the ones with zero jobs.
    `active_contacts` counts the contacts that are not closed. The application queue holds
    the jobs still to apply for (suggested and to_apply), highest score first. With a
    deadline, `days_to_deadline` is the number of days from the reference date to it
    (negative when it has passed).
    """
    pending = pending_followups(connection, reference_date)
    if domain.is_error(pending):
        return pending
    try:
        deadline_date = to_date(deadline)
    except (ValueError, TypeError):
        return domain.invalid_date("deadline", deadline)
    reference = to_date(pending["reference_date"])

    jobs = list_jobs(connection)
    contacts = list_contacts(connection)
    queue = [job for job in jobs if job["status"] in QUEUE_STATUSES]
    queue.sort(key=lambda job: (job["score"] is None, -(job["score"] or 0), job["id"]))

    def with_state(state: str) -> dict:
        return {
            kind: [item for item in pending[kind] if item["state"] == state]
            for kind in ("jobs", "contacts")
        }

    return {
        "reference_date": pending["reference_date"],
        "jobs_by_status": {
            status: sum(job["status"] == status for job in jobs) for status in domain.JOB_STATUSES
        },
        "active_contacts": sum(
            contact["status"] not in domain.CONTACT_CLOSED_STATUSES for contact in contacts
        ),
        "overdue": with_state(domain.OVERDUE),
        "due_soon": with_state(domain.DUE_SOON),
        "application_queue": queue,
        "deadline": deadline_date.isoformat() if deadline_date else None,
        "days_to_deadline": (deadline_date - reference).days if deadline_date else None,
    }
