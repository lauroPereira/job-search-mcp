"""Job operations: list, add and update, recording every change in job_history."""

import sqlite3
from datetime import date

from job_search_mcp import domain
from job_search_mcp.db import to_date

INITIAL_STATUS = "suggested"
APPLIED_STATUS = "applied"
# The only columns apply_job_changes may write: the column name goes into the UPDATE text.
JOB_UPDATABLE_FIELDS = ("status", "next_step", "applied_on", "last_contact_on")


def job_to_dict(row: sqlite3.Row) -> dict:
    """Turn a job row into a plain dict, adding the calculated follow-up date (ISO or None)."""
    job = dict(row)
    follow_up = domain.job_follow_up(job["applied_on"], job["last_contact_on"], job["status"])
    job["follow_up"] = follow_up.isoformat() if follow_up else None
    return job


def get_job(connection: sqlite3.Connection, job_id: int) -> dict | None:
    row = connection.execute("SELECT * FROM job WHERE id = ?", (job_id,)).fetchone()
    return job_to_dict(row) if row else None


def list_jobs(
    connection: sqlite3.Connection,
    status: str | None = None,
    track: str | None = None,
    min_score: float | None = None,
) -> list[dict] | dict:
    """List jobs ordered by id, optionally filtered by status, track and minimum score."""
    if status is not None and status not in domain.JOB_STATUSES:
        return domain.invalid_status(status, domain.JOB_STATUSES)
    conditions, parameters = [], []
    for condition, value in (
        ("status = ?", status),
        ("track = ?", track),
        ("score >= ?", min_score),
    ):
        if value is not None:
            conditions.append(condition)
            parameters.append(value)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = connection.execute(f"SELECT * FROM job{where} ORDER BY id", parameters)
    return [job_to_dict(row) for row in rows]


def add_job(
    connection: sqlite3.Connection,
    company: str,
    title: str,
    url: str,
    track: str | None = None,
    score: float | None = None,
    next_step: str | None = None,
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
    existing = connection.execute("SELECT * FROM job WHERE url = ?", (url,)).fetchone()
    if existing:
        return domain.error(
            "duplicate_url",
            f"A job with this URL already exists (id {existing['id']}).",
            job=job_to_dict(existing),
        )
    with connection:
        cursor = connection.execute(
            "INSERT INTO job (company, title, url, track, score, status, next_step)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (company.strip(), title.strip(), url, track, score, INITIAL_STATUS, next_step),
        )
    return get_job(connection, cursor.lastrowid)


def apply_job_changes(
    connection: sqlite3.Connection,
    job: dict,
    changes: dict,
    source: str,
    changed_on: date,
) -> list[dict]:
    """Write the fields that really change and one job_history line for each of them.

    Does not commit: the caller owns the transaction. Returns the history lines created.
    A field outside JOB_UPDATABLE_FIELDS raises ValueError before anything is written.
    """
    unknown = [field for field in changes if field not in JOB_UPDATABLE_FIELDS]
    if unknown:
        raise ValueError(f"Fields not allowed in a job update: {', '.join(unknown)}.")
    history = []
    for field, new_value in changes.items():
        old_value = job[field]
        if new_value == old_value:
            continue
        connection.execute(f"UPDATE job SET {field} = ? WHERE id = ?", (new_value, job["id"]))
        entry = {
            "job_id": job["id"],
            "date": changed_on.isoformat(),
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "source": source,
        }
        connection.execute(
            "INSERT INTO job_history (job_id, date, field, old_value, new_value, source)"
            " VALUES (:job_id, :date, :field, :old_value, :new_value, :source)",
            entry,
        )
        history.append(entry)
    return history


def update_job(
    connection: sqlite3.Connection,
    job_id: int,
    source: str,
    reference_date: str | date,
    status: str | None = None,
    next_step: str | None = None,
    applied_on: str | date | None = None,
    last_contact_on: str | date | None = None,
) -> dict:
    """Update the informed fields of a job and record each change in job_history.

    `source` says where the change came from and `reference_date` (a date or ISO text) is
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
    job = get_job(connection, job_id)
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
        history = apply_job_changes(connection, job, changes, source.strip(), changed_on)
    return {"job": get_job(connection, job_id), "history": history}
