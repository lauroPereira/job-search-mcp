"""Queries that answer "what needs attention" and "what to do today"."""

import sqlite3
from datetime import date, timedelta

from job_search_mcp import domain
from job_search_mcp.config import DEFAULT_SETTINGS, Settings
from job_search_mcp.contacts import list_contacts
from job_search_mcp.db import to_date
from job_search_mcp.jobs import list_jobs

QUEUE_STATUSES = ("suggested", "to_apply")
DEFAULT_DAYS_AHEAD = 2
DEFAULT_WEEKS = 4
MAX_WEEKS = 52
# Active applications: every status that is not closed (on_hold included).
ACTIVE_STATUSES = tuple(
    status for status in domain.JOB_STATUSES if status not in domain.JOB_CLOSED_STATUSES
)


def _reference(reference_date: str | date | None) -> date | None:
    """Convert the reference date, giving None when it is missing or invalid."""
    try:
        return to_date(reference_date)
    except (ValueError, TypeError):
        return None


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
    days_ahead: int = DEFAULT_DAYS_AHEAD,
    settings: Settings | None = None,
) -> dict:
    """Jobs and contacts whose follow-up is overdue or due within `days_ahead` days.

    Each item is the job or contact plus `follow_up` and `state` (overdue or due_soon),
    ordered from the oldest follow-up to the most recent.
    """
    reference = _reference(reference_date)
    if reference is None:
        return domain.invalid_date("reference_date", reference_date)
    return {
        "reference_date": reference.isoformat(),
        "days_ahead": days_ahead,
        "jobs": _pending(list_jobs(connection, settings=settings), reference, days_ahead),
        "contacts": _pending(list_contacts(connection, settings=settings), reference, days_ahead),
    }


def daily_summary(
    connection: sqlite3.Connection,
    reference_date: str | date,
    deadline: str | date | None = None,
    settings: Settings | None = None,
) -> dict:
    """Summary of the day: counts, overdue and due-soon items and the application queue.

    `jobs_by_status` brings every job status, including the ones with zero jobs.
    `active_contacts` counts the contacts that are not closed. The application queue holds
    the jobs still to apply for (suggested and to_apply), highest score first. With a
    deadline, `days_to_deadline` is the number of days from the reference date to it
    (negative when it has passed). Without an informed deadline, the one in the settings
    (goals.deadline) is used, if any.
    """
    reference = _reference(reference_date)
    if reference is None:
        return domain.invalid_date("reference_date", reference_date)
    settings = settings or DEFAULT_SETTINGS
    if deadline is None:
        deadline = settings.deadline
    try:
        deadline_date = to_date(deadline)
    except (ValueError, TypeError):
        return domain.invalid_date("deadline", deadline)

    # Jobs and contacts are read once and reused by the counts, the pending items and the queue.
    jobs = list_jobs(connection, settings=settings)
    contacts = list_contacts(connection, settings=settings)
    pending = {
        "jobs": _pending(jobs, reference, DEFAULT_DAYS_AHEAD),
        "contacts": _pending(contacts, reference, DEFAULT_DAYS_AHEAD),
    }
    queue = [job for job in jobs if job["status"] in QUEUE_STATUSES]
    queue.sort(key=lambda job: (job["score"] is None, -(job["score"] or 0), job["id"]))

    def with_state(state: str) -> dict:
        return {
            kind: [item for item in pending[kind] if item["state"] == state]
            for kind in ("jobs", "contacts")
        }

    return {
        "reference_date": reference.isoformat(),
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


def _reached_interview(job: dict) -> bool:
    """The application had an hr, technical or manager stage, or is in an interview status."""
    return job["status"] in domain.JOB_INTERVIEW_STATUSES or any(
        stage["kind"] in domain.INTERVIEW_STAGE_KINDS for stage in job["stages"]
    )


def _has_confirmed_referral(job: dict) -> bool:
    return any(
        person["role"] == domain.REFERRER_ROLE and person["confirmed"] for person in job["people"]
    )


def _applications_per_week(jobs: list[dict], reference: date, weeks: int) -> list[dict]:
    """Applications counted by applied_on in each ISO week (Monday to Sunday), oldest first.

    The week of the reference date is the last one; weeks without applications count zero.
    """
    current_monday = reference - timedelta(days=reference.weekday())
    applied = [to_date(job["applied_on"]) for job in jobs if job["applied_on"]]
    result = []
    for back in range(weeks - 1, -1, -1):
        start = current_monday - timedelta(weeks=back)
        end = start + timedelta(days=6)
        year, week, _ = start.isocalendar()
        result.append(
            {
                "week": f"{year}-W{week:02d}",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "applications": sum(start <= day <= end for day in applied),
            }
        )
    return result


def funnel_metrics(
    connection: sqlite3.Connection,
    reference_date: str | date,
    weeks: int = DEFAULT_WEEKS,
    settings: Settings | None = None,
) -> dict:
    """Funnel metrics at the reference date, calculated from the database (nothing is written).

    - `active_by_status`: applications in each status of `active_statuses` (every status that
      is not closed, on_hold included) and `active_total`.
    - `in_interview`: applications now in an interview status.
    - `interview_rate`: `reached_interview` (applications with applied_on that had an hr,
      technical or manager stage or are in an interview status) divided by `applied`
      (applications with applied_on); `rate` is None when there is none.
    - `applications_per_week`: the last `weeks` ISO weeks (1 to MAX_WEEKS), oldest first.
    - `active_with_referral` / `active_without_referral`: active applications with and
      without a confirmed referrer.
    - `follow_ups`: how many jobs and contacts are overdue or due soon (as pending_followups).
    - `deadline` and `days_to_deadline` from goals.deadline, and the `goals` of the settings;
      None when not set.
    """
    reference = _reference(reference_date)
    if reference is None:
        return domain.invalid_date("reference_date", reference_date)
    if isinstance(weeks, bool) or not isinstance(weeks, int) or not 1 <= weeks <= MAX_WEEKS:
        return domain.error(
            "invalid_input", f"Invalid weeks '{weeks}'. Use an integer from 1 to {MAX_WEEKS}."
        )
    settings = settings or DEFAULT_SETTINGS

    jobs = list_jobs(connection, settings=settings)
    contacts = list_contacts(connection, settings=settings)
    active = [job for job in jobs if job["status"] in ACTIVE_STATUSES]
    applied = [job for job in jobs if job["applied_on"]]
    reached = sum(_reached_interview(job) for job in applied)
    with_referral = sum(_has_confirmed_referral(job) for job in active)
    pending = {
        "jobs": _pending(jobs, reference, DEFAULT_DAYS_AHEAD),
        "contacts": _pending(contacts, reference, DEFAULT_DAYS_AHEAD),
    }

    def count(state: str) -> dict:
        return {
            kind: sum(item["state"] == state for item in items) for kind, items in pending.items()
        }

    deadline = settings.deadline
    return {
        "reference_date": reference.isoformat(),
        "active_statuses": list(ACTIVE_STATUSES),
        "active_by_status": {
            status: sum(job["status"] == status for job in active) for status in ACTIVE_STATUSES
        },
        "active_total": len(active),
        "in_interview": sum(job["status"] in domain.JOB_INTERVIEW_STATUSES for job in active),
        "interview_rate": {
            "reached_interview": reached,
            "applied": len(applied),
            "rate": round(reached / len(applied), 4) if applied else None,
        },
        "applications_per_week": _applications_per_week(jobs, reference, weeks),
        "active_with_referral": with_referral,
        "active_without_referral": len(active) - with_referral,
        "follow_ups": {
            "days_ahead": DEFAULT_DAYS_AHEAD,
            "overdue": count(domain.OVERDUE),
            "due_soon": count(domain.DUE_SOON),
        },
        "deadline": deadline.isoformat() if deadline else None,
        "days_to_deadline": (deadline - reference).days if deadline else None,
        "goals": {
            "applications_per_week": settings.applications_per_week,
            "interview_rate": settings.interview_rate,
        },
    }
