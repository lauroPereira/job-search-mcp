"""Domain constants and pure rules: valid statuses, follow-up dates and their classification.

No function here reads the current date: the reference date always comes in as a parameter.
"""

from datetime import date, timedelta

from job_search_mcp.db import to_date

JOB_STATUSES = (
    "suggested",
    "to_apply",
    "blocked",
    "applied",
    "in_review",
    "hr_interview",
    "tech_interview",
    "manager_interview",
    "offer",
    "hired",
    "rejected",
    "withdrawn",
    "closed",
)
# Closed statuses end the follow-up; the "no follow-up" ones have not started it yet.
JOB_CLOSED_STATUSES = frozenset({"hired", "rejected", "withdrawn", "closed"})
JOB_NO_FOLLOW_UP_STATUSES = frozenset({"suggested", "to_apply", "blocked"})

CONTACT_STATUSES = (
    "to_contact",
    "awaiting_reply",
    "in_conversation",
    "resume_sent",
    "referred",
    "closed",
)
CONTACT_CLOSED_STATUSES = frozenset({"closed"})
CONTACT_NO_FOLLOW_UP_STATUSES = frozenset({"to_contact", "closed"})

JOB_FOLLOW_UP_DAYS = 7
CONTACT_FOLLOW_UP_DAYS = 6

OVERDUE = "overdue"
DUE_SOON = "due_soon"
ON_TRACK = "on_track"


def error(code: str, detail: str, **extra) -> dict:
    """Build the structured business error every operation returns instead of raising.

    `error` is a stable code (invalid_status, duplicate_url, not_found, invalid_date,
    invalid_input) and `detail` a message the agent can relay. Extra keys carry context,
    such as the valid statuses or the existing job.
    """
    return {"error": code, "detail": detail, **extra}


def is_error(result) -> bool:
    """Tell a structured business error apart from a normal result."""
    return isinstance(result, dict) and "error" in result


def invalid_status(status: str, valid: tuple[str, ...]) -> dict:
    return error(
        "invalid_status",
        f"Invalid status '{status}'. Valid statuses: {', '.join(valid)}.",
        valid_statuses=list(valid),
    )


def not_found(kind: str, record_id) -> dict:
    return error("not_found", f"No {kind} with id {record_id}.")


def invalid_date(field: str, value) -> dict:
    return error("invalid_date", f"Invalid {field} '{value}'. Use the ISO format YYYY-MM-DD.")


def job_follow_up(
    applied_on: str | date | None,
    last_contact_on: str | date | None,
    status: str | None = None,
) -> date | None:
    """Follow-up date of a job: last contact plus 7 days; without contact, application plus 7.

    Returns None when there is no date to count from or when the status, if given, is
    closed or does not generate a follow-up.
    """
    if status in JOB_CLOSED_STATUSES or status in JOB_NO_FOLLOW_UP_STATUSES:
        return None
    base = to_date(last_contact_on) or to_date(applied_on)
    return base + timedelta(days=JOB_FOLLOW_UP_DAYS) if base else None


def contact_follow_up(last_contact_on: str | date | None, status: str | None = None) -> date | None:
    """Follow-up date of a contact: last interaction plus 6 days.

    Returns None without a last interaction or when the status, if given, does not
    generate a follow-up (to_contact, closed).
    """
    if status in CONTACT_NO_FOLLOW_UP_STATUSES:
        return None
    base = to_date(last_contact_on)
    return base + timedelta(days=CONTACT_FOLLOW_UP_DAYS) if base else None


def classify(follow_up: date, reference_date: date, days_ahead: int = 2) -> str:
    """Classify a follow-up against the reference date.

    overdue: the follow-up date is the reference date or earlier.
    due_soon: it falls within the next `days_ahead` days.
    on_track: it is further ahead.
    """
    days_left = (follow_up - reference_date).days
    if days_left <= 0:
        return OVERDUE
    if days_left <= days_ahead:
        return DUE_SOON
    return ON_TRACK
