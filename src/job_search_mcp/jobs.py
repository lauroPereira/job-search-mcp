"""Job operations: list, add and update, recording every change in the history.

A job is read together with its application (1:1) and its company, with the same keys as
in v0.1.0: `company` is the name of the company, plus the additive `company_id`.
"""

import sqlite3
from datetime import date

from job_search_mcp import db, domain, history
from job_search_mcp.config import DEFAULT_SETTINGS, Settings
from job_search_mcp.db import to_date

INITIAL_STATUS = "suggested"
APPLIED_STATUS = "applied"
# The fields of a job that update_job changes: they live in its application.
JOB_UPDATABLE_FIELDS = history.UPDATABLE_FIELDS["application"]

# Job, application and company joined, with the keys (and their order) of v0.1.0.
JOB_SELECT = """
SELECT job.id, company.name AS company, job.title, job.url, job.track, job.score,
    application.status, application.next_step, application.applied_on,
    application.last_contact_on, job.created_at, job.company_id
FROM job
JOIN application ON application.job_id = job.id
JOIN company ON company.id = job.company_id
"""


def job_to_dict(row: sqlite3.Row, settings: Settings | None = None) -> dict:
    """Turn a job row into a plain dict, adding the calculated follow-up date (ISO or None).

    The follow-up days come from `settings` (None: the defaults).
    """
    job = dict(row)
    days = (settings or DEFAULT_SETTINGS).job_follow_up_days
    follow_up = domain.job_follow_up(
        job["applied_on"], job["last_contact_on"], job["status"], days=days
    )
    job["follow_up"] = follow_up.isoformat() if follow_up else None
    return job


def get_job(
    connection: sqlite3.Connection, job_id: int, settings: Settings | None = None
) -> dict | None:
    row = connection.execute(f"{JOB_SELECT} WHERE job.id = ?", (job_id,)).fetchone()
    return job_to_dict(row, settings) if row else None


def list_jobs(
    connection: sqlite3.Connection,
    status: str | None = None,
    track: str | None = None,
    min_score: float | None = None,
    settings: Settings | None = None,
) -> list[dict] | dict:
    """List jobs ordered by id, optionally filtered by status, track and minimum score."""
    if status is not None and status not in domain.JOB_STATUSES:
        return domain.invalid_status(status, domain.JOB_STATUSES)
    conditions, parameters = [], []
    for condition, value in (
        ("application.status = ?", status),
        ("job.track = ?", track),
        ("job.score >= ?", min_score),
    ):
        if value is not None:
            conditions.append(condition)
            parameters.append(value)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = connection.execute(f"{JOB_SELECT}{where} ORDER BY job.id", parameters)
    return [job_to_dict(row, settings) for row in rows]


def add_job(
    connection: sqlite3.Connection,
    company: str,
    title: str,
    url: str,
    track: str | None = None,
    score: float | None = None,
    next_step: str | None = None,
    settings: Settings | None = None,
) -> dict:
    """Register a job in the initial status, refusing a URL that is already registered.

    `track`, when informed, must be one of domain.JOB_TRACKS and `score` a number from
    domain.SCORE_MIN to domain.SCORE_MAX; otherwise nothing is created and the result is
    the error 'invalid_input'.
    """
    for field, value in (("company", company), ("title", title), ("url", url)):
        if not value or not value.strip():
            return domain.error("invalid_input", f"Field '{field}' is required.")
    if track is not None and track not in domain.JOB_TRACKS:
        return domain.invalid_track(track)
    if score is not None and not domain.is_valid_score(score):
        return domain.invalid_score(score)
    url = url.strip()
    existing = connection.execute("SELECT id FROM job WHERE url = ?", (url,)).fetchone()
    if existing:
        return domain.error(
            "duplicate_url",
            f"A job with this URL already exists (id {existing['id']}).",
            job=get_job(connection, existing["id"], settings),
        )
    with connection:
        cursor = connection.execute(
            "INSERT INTO job (company_id, title, url, track, score) VALUES (?, ?, ?, ?, ?)",
            (db.ensure_company(connection, company), title.strip(), url, track, score),
        )
        connection.execute(
            "INSERT INTO application (job_id, status, next_step) VALUES (?, ?, ?)",
            (cursor.lastrowid, INITIAL_STATUS, next_step),
        )
    return get_job(connection, cursor.lastrowid, settings)


def apply_job_changes(
    connection: sqlite3.Connection,
    job: dict,
    changes: dict,
    source_type: str,
    source_ref: str | None,
    changed_on: date,
) -> list[dict]:
    """Write the fields that really change in the application of the job, with history.

    Does not commit: the caller owns the transaction. Returns the history lines created,
    in the v0.1.0 format: job_id, date, field, old_value, new_value and source (the
    reference of the origin when there is one, otherwise its type). A field outside
    JOB_UPDATABLE_FIELDS raises ValueError before anything is written.
    """
    application_id = connection.execute(
        "SELECT id FROM application WHERE job_id = ?", (job["id"],)
    ).fetchone()[0]
    lines = history.record_changes(
        connection, "application", application_id, job, changes, changed_on, source_type, source_ref
    )
    return [
        {
            "job_id": job["id"],
            "date": line["date"],
            "field": line["field"],
            "old_value": line["old_value"],
            "new_value": line["new_value"],
            "source": line["source_ref"] or line["source_type"],
        }
        for line in lines
    ]


def update_job(
    connection: sqlite3.Connection,
    job_id: int,
    source: str,
    reference_date: str | date,
    status: str | None = None,
    next_step: str | None = None,
    applied_on: str | date | None = None,
    last_contact_on: str | date | None = None,
    settings: Settings | None = None,
) -> dict:
    """Update the informed fields of a job and record each change in the history.

    `source` says where the change came from: a known type of origin
    (domain.SOURCE_TYPES) is stored as it is; any other text as the type 'user', with the
    text as the reference. `reference_date` (a date or ISO text) is
    the date written in the history. Fields left as None are not touched. When the status
    changes to applied and the job has no application date, neither stored nor informed,
    `applied_on` is filled with the reference date, so the job starts to have a follow-up.
    Returns the updated job and the history lines created, or a structured error without
    changing anything.
    """
    if not source or not source.strip():
        return domain.error("invalid_input", "Field 'source' is required.")
    try:
        changed_on = to_date(reference_date)
    except (ValueError, TypeError):
        changed_on = None
    if changed_on is None:
        return domain.invalid_date("reference_date", reference_date)
    job = get_job(connection, job_id, settings)
    if job is None:
        return domain.not_found("job", job_id)
    if status is not None and status not in domain.JOB_STATUSES:
        return domain.invalid_status(status, domain.JOB_STATUSES)
    changes = {"status": status, "next_step": next_step}
    for field, value in (("applied_on", applied_on), ("last_contact_on", last_contact_on)):
        try:
            parsed = to_date(value)
        except (ValueError, TypeError):
            return domain.invalid_date(field, value)
        changes[field] = parsed.isoformat() if parsed else None
    becomes_applied = status == APPLIED_STATUS and job["status"] != APPLIED_STATUS
    if becomes_applied and not job["applied_on"] and changes["applied_on"] is None:
        changes["applied_on"] = changed_on.isoformat()
    changes = {field: value for field, value in changes.items() if value is not None}
    with connection:
        lines = apply_job_changes(
            connection, job, changes, *history.split_source(source), changed_on
        )
    return {"job": get_job(connection, job_id, settings), "history": lines}
