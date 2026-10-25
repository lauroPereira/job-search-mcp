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


def _changed_on(field: str, value: str | date) -> date | dict:
    """The date written in the history, or a structured error when it is not a valid date."""
    try:
        parsed = to_date(value)
    except (ValueError, TypeError):
        parsed = None
    return parsed if parsed is not None else domain.invalid_date(field, value)


def parse_source(source: str) -> tuple[str, str | None] | dict:
    """(source_type, source_ref) of a source given by the user, or an error when it is empty."""
    if not isinstance(source, str) or not source.strip():
        return domain.error("invalid_input", "Field 'source' is required.")
    return history.split_source(source)


def plan_add_job(
    connection: sqlite3.Connection,
    company: str,
    title: str,
    url: str,
    track: str | None = None,
    score: float | None = None,
    next_step: str | None = None,
    *,
    reference_date: str | date,
    source: str = domain.USER_SOURCE,
    settings: Settings | None = None,
) -> domain.Plan | dict:
    """Plan the registration of a job in the initial status, without writing anything.

    Refuses a URL that is already registered (duplicate_url). `track`, when informed, must
    be one of domain.JOB_TRACKS and `score` a number from domain.SCORE_MIN to
    domain.SCORE_MAX; otherwise the result is the error 'invalid_input'. `source` says
    where the job came from (see history.split_source) and `reference_date` is the date
    written in the history. The plan creates the company when no company has the same
    normalized name, the job and its application, with one history line per informed
    field; applying it returns the created job.
    """
    for field, value in (("company", company), ("title", title), ("url", url)):
        if not value or not value.strip():
            return domain.error("invalid_input", f"Field '{field}' is required.")
    if track is not None and track not in domain.JOB_TRACKS:
        return domain.invalid_track(track)
    if score is not None and not domain.is_valid_score(score):
        return domain.invalid_score(score)
    origin = parse_source(source)
    if domain.is_error(origin):
        return origin
    changed_on = _changed_on("reference_date", reference_date)
    if domain.is_error(changed_on):
        return changed_on
    url = url.strip()
    existing = connection.execute("SELECT id FROM job WHERE url = ?", (url,)).fetchone()
    if existing:
        return domain.error(
            "duplicate_url",
            f"A job with this URL already exists (id {existing['id']}).",
            job=get_job(connection, existing["id"], settings),
        )
    stored_company = connection.execute(
        "SELECT name FROM company WHERE normalized_name = ?", (db.normalize_name(company),)
    ).fetchone()
    company_name = stored_company[0] if stored_company else company.strip()
    job_values = {
        "company": company_name,
        "title": title.strip(),
        "url": url,
        "track": track,
        "score": score,
    }
    application_values = {"status": INITIAL_STATUS, "next_step": next_step}
    changes = [] if stored_company else history.creation("company", {"name": company_name})
    changes += history.creation("job", job_values)
    changes += history.creation("application", application_values)

    def apply() -> dict:
        company_id = db.ensure_company(connection, company_name)
        if not stored_company:
            history.record_creation(
                connection, "company", company_id, {"name": company_name}, changed_on, *origin
            )
        job_id = connection.execute(
            "INSERT INTO job (company_id, title, url, track, score) VALUES (?, ?, ?, ?, ?)",
            (company_id, job_values["title"], url, track, score),
        ).lastrowid
        new_application_id = connection.execute(
            "INSERT INTO application (job_id, status, next_step) VALUES (?, ?, ?)",
            (job_id, INITIAL_STATUS, next_step),
        ).lastrowid
        history.record_creation(connection, "job", job_id, job_values, changed_on, *origin)
        history.record_creation(
            connection,
            "application",
            new_application_id,
            application_values,
            changed_on,
            *origin,
        )
        return get_job(connection, job_id, settings)

    return domain.Plan(changes=changes, base_versions={}, apply=apply)


def application_id(connection: sqlite3.Connection, job_id: int) -> int:
    """Id of the application of a job (every job has exactly one)."""
    row = connection.execute("SELECT id FROM application WHERE job_id = ?", (job_id,))
    return row.fetchone()[0]


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
    lines = history.record_changes(
        connection,
        "application",
        application_id(connection, job["id"]),
        job,
        changes,
        changed_on,
        source_type,
        source_ref,
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


def plan_update_job(
    connection: sqlite3.Connection,
    job_id: int,
    source: str,
    reference_date: str | date,
    status: str | None = None,
    next_step: str | None = None,
    applied_on: str | date | None = None,
    last_contact_on: str | date | None = None,
    settings: Settings | None = None,
) -> domain.Plan | dict:
    """Plan the update of the informed fields of a job, without writing anything.

    `source` says where the change came from: a known type of origin
    (domain.SOURCE_TYPES) is stored as it is; any other text as the type 'user', with the
    text as the reference. `reference_date` (a date or ISO text) is the date written in
    the history. Fields left as None are not touched. When the status changes to applied
    and the job has no application date, neither stored nor informed, `applied_on` is
    filled with the reference date, so the job starts to have a follow-up. The plan
    depends on the version of the application; applying it returns the updated job and
    the history lines created. Errors are structured and nothing is planned.
    """
    origin = parse_source(source)
    if domain.is_error(origin):
        return origin
    changed_on = _changed_on("reference_date", reference_date)
    if domain.is_error(changed_on):
        return changed_on
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
    record_id = application_id(connection, job_id)

    def apply() -> dict:
        lines = apply_job_changes(connection, job, changes, *origin, changed_on)
        return {"job": get_job(connection, job_id, settings), "history": lines}

    return domain.Plan(
        changes=history.diff("application", record_id, job, changes),
        base_versions={
            f"application:{record_id}": history.read_version(connection, "application", record_id)
        },
        apply=apply,
    )
