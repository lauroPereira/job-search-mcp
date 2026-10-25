"""Domain constants and pure rules: valid statuses, follow-up dates and their classification.

No function here reads the current date: the reference date always comes in as a parameter.
"""

from collections.abc import Callable
from dataclasses import dataclass
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
    "on_hold",
    "hired",
    "rejected",
    "withdrawn",
    "closed",
)
# Closed statuses end the follow-up; the "no follow-up" ones have not started it yet, or
# paused it (on_hold, which still counts as active).
JOB_CLOSED_STATUSES = frozenset({"hired", "rejected", "withdrawn", "closed"})
JOB_NO_FOLLOW_UP_STATUSES = frozenset({"suggested", "to_apply", "blocked", "on_hold"})
# Statuses of an application in interview.
JOB_INTERVIEW_STATUSES = frozenset({"hr_interview", "tech_interview", "manager_interview"})

CONTACT_STATUSES = (
    "to_contact",
    "awaiting_reply",
    "in_conversation",
    "resume_sent",
    "referred",
    "on_hold",
    "closed",
)
CONTACT_CLOSED_STATUSES = frozenset({"closed"})
CONTACT_NO_FOLLOW_UP_STATUSES = frozenset({"to_contact", "on_hold", "closed"})

# Priority the user gives a company, and the one suggested when the company has an active
# person (not closed) or an active application (not in a closed status).
COMPANY_PRIORITIES = ("A", "B", "C")
SUGGESTED_PRIORITY = "A"

# Types of origin written in the history. Free text given as a source is stored as
# USER_SOURCE, with the text as the reference.
SOURCE_TYPES = ("conversation", "print", "audio", "email", "meeting", "import", "user")
USER_SOURCE = "user"

# Career tracks and the fit score range a job may be registered with.
JOB_TRACKS = ("data", "systems", "product", "ai", "other")
SCORE_MIN = 0
SCORE_MAX = 10

# Stages of an application and their results; a stage without result is still pending.
STAGE_KINDS = ("screening", "test", "culture_fit", "hr", "technical", "manager", "offer")
STAGE_RESULTS = ("pending", "passed", "failed", "cancelled")
DEFAULT_STAGE_RESULT = "pending"
# Stages that count as an interview in the interview rate.
INTERVIEW_STAGE_KINDS = frozenset({"hr", "technical", "manager"})

# Roles of a person in an application; a confirmed referrer makes the job a high priority.
PERSON_ROLES = ("referrer", "recruiter", "hiring_manager", "contact")
REFERRER_ROLE = "referrer"

# Derived job priority (never stored): high with a score of at least HIGH_PRIORITY_SCORE or
# a confirmed referral, medium with a score of at least MEDIUM_PRIORITY_SCORE, low otherwise.
HIGH_PRIORITY = "high"
MEDIUM_PRIORITY = "medium"
LOW_PRIORITY = "low"
HIGH_PRIORITY_SCORE = 7.5
MEDIUM_PRIORITY_SCORE = 7

# Default follow-up days; the local settings (config.py) may change them.
JOB_FOLLOW_UP_DAYS = 7
CONTACT_FOLLOW_UP_DAYS = 6

OVERDUE = "overdue"
DUE_SOON = "due_soon"
ON_TRACK = "on_track"


@dataclass(frozen=True)
class Plan:
    """What a write operation would do, calculated without writing anything.

    `changes` is the preview: one dict per field, with entity, record_id (None for a record
    still to be created), field, old_value and new_value. `base_versions` maps
    "entity:id" to the `version` read from each record the operation depends on. `apply`
    writes the changes without committing (the caller owns the transaction) and returns
    the result of the operation.
    """

    changes: list[dict]
    base_versions: dict[str, int]
    apply: Callable[[], dict]


def error(code: str, detail: str, **extra) -> dict:
    """Build the structured business error every operation returns instead of raising.

    `error` is a stable code (invalid_status, duplicate_url, not_found, invalid_date,
    invalid_input, stale_proposal, expired_proposal, duplicate_company, duplicate_link,
    duplicate_stage) and `detail` a message the agent can relay. Extra keys carry context,
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


def invalid_track(track) -> dict:
    return error(
        "invalid_input",
        f"Invalid track '{track}'. Valid tracks: {', '.join(JOB_TRACKS)}.",
        valid_tracks=list(JOB_TRACKS),
    )


def invalid_priority(priority) -> dict:
    return error(
        "invalid_input",
        f"Invalid priority '{priority}'. Valid priorities: {', '.join(COMPANY_PRIORITIES)}.",
        valid_priorities=list(COMPANY_PRIORITIES),
    )


def invalid_score(score) -> dict:
    return error(
        "invalid_input",
        f"Invalid score '{score}'. Use a number from {SCORE_MIN} to {SCORE_MAX}.",
    )


def invalid_choice(field: str, value, valid: tuple[str, ...]) -> dict:
    """Error 'invalid_input' for a value outside a closed list, with the valid ones."""
    return error(
        "invalid_input",
        f"Invalid {field} '{value}'. Valid values: {', '.join(valid)}.",
        valid_values=list(valid),
    )


def job_priority(score: float | None, confirmed_referral: bool) -> str:
    """Derived priority of a job: high, medium or low (see HIGH_PRIORITY_SCORE)."""
    if confirmed_referral or (score is not None and score >= HIGH_PRIORITY_SCORE):
        return HIGH_PRIORITY
    if score is not None and score >= MEDIUM_PRIORITY_SCORE:
        return MEDIUM_PRIORITY
    return LOW_PRIORITY


def optional_text(value: str | None) -> str | None:
    """Text informed by the user without surrounding spaces; None when missing or blank."""
    if value is None or not value.strip():
        return None
    return value.strip()


def is_valid_score(score) -> bool:
    """A score is a number (not a boolean, not NaN) from SCORE_MIN to SCORE_MAX."""
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return False
    return SCORE_MIN <= score <= SCORE_MAX


def job_follow_up(
    applied_on: str | date | None,
    last_contact_on: str | date | None,
    status: str | None = None,
    days: int = JOB_FOLLOW_UP_DAYS,
) -> date | None:
    """Follow-up date of a job: last contact plus `days`; without contact, application plus it.

    Returns None when there is no date to count from or when the status, if given, is
    closed or does not generate a follow-up.
    """
    if status in JOB_CLOSED_STATUSES or status in JOB_NO_FOLLOW_UP_STATUSES:
        return None
    base = to_date(last_contact_on) or to_date(applied_on)
    return base + timedelta(days=days) if base else None


def contact_follow_up(
    last_contact_on: str | date | None,
    status: str | None = None,
    days: int = CONTACT_FOLLOW_UP_DAYS,
) -> date | None:
    """Follow-up date of a contact: last interaction plus `days`.

    Returns None without a last interaction or when the status, if given, does not
    generate a follow-up (to_contact, closed).
    """
    if status in CONTACT_NO_FOLLOW_UP_STATUSES:
        return None
    base = to_date(last_contact_on)
    return base + timedelta(days=days) if base else None


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
