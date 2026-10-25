"""Job operations: list, add and update, stages and people, recording every change.

A job is read together with its application (1:1) and its company, with the same keys as
in v0.1.0: `company` is the name of the company. The keys `company_id`, `priority` (derived,
see domain.job_priority), `stages` and `people` are additive.
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


STAGE_SELECT = """
SELECT application.job_id, application_stage.id, application_stage.kind, application_stage.date,
    application_stage.result, application_stage.feedback
FROM application_stage
JOIN application ON application.id = application_stage.application_id
"""
PERSON_SELECT = """
SELECT application.job_id, contact.id, contact.name, application_person.role,
    application_person.confirmed
FROM application_person
JOIN application ON application.id = application_person.application_id
JOIN contact ON contact.id = application_person.contact_id
"""


def jobs_from_rows(
    connection: sqlite3.Connection, rows: list[sqlite3.Row], settings: Settings | None = None
) -> list[dict]:
    """Turn job rows into dicts with follow-up, priority, stages and people.

    Stages (id, kind, date, result, feedback) come ordered by date and id; people (id,
    name, role, confirmed as a boolean) by person id and role.
    """
    found = [job_to_dict(row, settings) for row in rows]
    if not found:
        return []
    by_id = {job["id"]: {"stages": [], "people": []} for job in found}
    marks = ", ".join("?" * len(by_id))
    stages = connection.execute(
        f"{STAGE_SELECT} WHERE application.job_id IN ({marks})"
        " ORDER BY application_stage.date, application_stage.id",
        list(by_id),
    )
    for row in stages:
        stage = dict(row)
        by_id[stage.pop("job_id")]["stages"].append(stage)
    people = connection.execute(
        f"{PERSON_SELECT} WHERE application.job_id IN ({marks})"
        " ORDER BY contact.id, application_person.role",
        list(by_id),
    )
    for row in people:
        person = dict(row)
        person["confirmed"] = bool(person["confirmed"])
        by_id[person.pop("job_id")]["people"].append(person)
    for job in found:
        details = by_id[job["id"]]
        referred = any(
            person["role"] == domain.REFERRER_ROLE and person["confirmed"]
            for person in details["people"]
        )
        job["priority"] = domain.job_priority(job["score"], referred)
        job |= details
    return found


def get_job(
    connection: sqlite3.Connection, job_id: int, settings: Settings | None = None
) -> dict | None:
    row = connection.execute(f"{JOB_SELECT} WHERE job.id = ?", (job_id,)).fetchone()
    return jobs_from_rows(connection, [row], settings)[0] if row else None


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
    return jobs_from_rows(connection, rows.fetchall(), settings)


def parse_reference_date(field: str, value: str | date) -> date | dict:
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
    changed_on = parse_reference_date("reference_date", reference_date)
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
    changed_on = parse_reference_date("reference_date", reference_date)
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


def plan_add_stage(
    connection: sqlite3.Connection,
    job_id: int,
    kind: str,
    date: str | date,
    result: str | None = None,
    feedback: str | None = None,
    status: str | None = None,
    *,
    source: str,
    reference_date: str | date,
    settings: Settings | None = None,
) -> domain.Plan | dict:
    """Plan the record of a dated stage of the application of a job, writing nothing.

    `kind` is one of domain.STAGE_KINDS and `result` one of domain.STAGE_RESULTS (default
    pending); the stage date cannot be after `reference_date`, and a stage of the same kind
    on the same date of the same application is refused with 'duplicate_stage' (with the
    existing stage). When `status` is informed, the application moves to it (as in
    plan_update_job); an application that becomes applied without an application date
    gets the stage date as its application date. When the stage is more recent than the last contact
    of the application, the last contact moves to the stage date. The stage and every
    changed field of the application get history lines, with `source` and dated
    `reference_date`. The stage has no version: the plan depends on the version of the
    application. Applying it returns {"stage": the created stage, "job": the updated job,
    "history": the lines of the application, as in update_job}. Errors are structured and
    nothing is planned.
    """
    if kind not in domain.STAGE_KINDS:
        return domain.invalid_choice("kind", kind, domain.STAGE_KINDS)
    result = domain.DEFAULT_STAGE_RESULT if result is None else result
    if result not in domain.STAGE_RESULTS:
        return domain.invalid_choice("result", result, domain.STAGE_RESULTS)
    origin = parse_source(source)
    if domain.is_error(origin):
        return origin
    changed_on = parse_reference_date("reference_date", reference_date)
    if domain.is_error(changed_on):
        return changed_on
    try:
        stage_date = to_date(date)
    except (ValueError, TypeError):
        stage_date = None
    if stage_date is None:
        return domain.invalid_date("date", date)
    if stage_date > changed_on:
        return domain.error(
            "invalid_date",
            f"Invalid date '{date}': it cannot be after today ({changed_on.isoformat()}).",
        )
    job = get_job(connection, job_id, settings)
    if job is None:
        return domain.not_found("job", job_id)
    stage_on = stage_date.isoformat()
    record_id = application_id(connection, job_id)
    existing = connection.execute(
        "SELECT id, kind, date, result, feedback FROM application_stage"
        " WHERE application_id = ? AND kind = ? AND date = ?",
        (record_id, kind, stage_on),
    ).fetchone()
    if existing is not None:
        return domain.error(
            "duplicate_stage",
            f"Job {job_id} already has a {kind} stage on {stage_on} (id {existing['id']}).",
            stage=dict(existing),
        )
    newer = stage_on > (job["last_contact_on"] or "")
    # An application that becomes applied through a stage was sent on the stage date, not
    # on the day it is recorded (that one only dates the history lines).
    becomes_applied = status == APPLIED_STATUS and job["status"] != APPLIED_STATUS
    update = plan_update_job(
        connection,
        job_id,
        source,
        changed_on,
        status=status,
        applied_on=stage_on if becomes_applied and not job["applied_on"] else None,
        last_contact_on=stage_on if newer else None,
        settings=settings,
    )
    if domain.is_error(update):
        return update
    stage = {
        "application_id": record_id,
        "kind": kind,
        "date": stage_on,
        "result": result,
        "feedback": domain.optional_text(feedback),
    }

    def apply() -> dict:
        stage_id = connection.execute(
            "INSERT INTO application_stage (application_id, kind, date, result, feedback)"
            " VALUES (:application_id, :kind, :date, :result, :feedback)",
            stage,
        ).lastrowid
        history.record_creation(
            connection, "application_stage", stage_id, stage, changed_on, *origin
        )
        updated = update.apply()
        created = connection.execute(
            "SELECT id, kind, date, result, feedback FROM application_stage WHERE id = ?",
            (stage_id,),
        ).fetchone()
        return {"stage": dict(created), **updated}

    return domain.Plan(
        changes=history.creation("application_stage", stage) + update.changes,
        base_versions=update.base_versions,
        apply=apply,
    )


def describe_link(name: str, contact_id: int, role: str, confirmed: bool) -> str:
    """How a link of a person to an application appears in the preview shown to the user."""
    state = "confirmed" if confirmed else "not confirmed"
    return f"{name} (contact {contact_id}) as {role}, {state}"


def link_value(contact_id: int, role: str, confirmed: bool) -> str:
    """How a link is stored in the history: stable text, without the name, to be queried."""
    return f"contact_id={contact_id};role={role};confirmed={int(confirmed)}"


def plan_link_person(
    connection: sqlite3.Connection,
    job_id: int,
    contact_id: int,
    role: str,
    confirmed: bool | None = None,
    *,
    source: str,
    reference_date: str | date,
    settings: Settings | None = None,
) -> domain.Plan | dict:
    """Plan linking a person to the application of a job with a role, writing nothing.

    `role` is one of domain.PERSON_ROLES. A new link is not confirmed unless `confirmed` is
    true. The same person with the same role in the same application is refused with
    'duplicate_link' (with the existing link), except when that link is not confirmed yet
    and `confirmed` is true: then the plan confirms it. A link has no columns of its own
    to diff, so its history is a single line: entity application_person, the application
    as the record, field 'link' and the link before and after as link_value
    (contact_id=N;role=R;confirmed=0|1). The preview shows it with the name (describe_link).
    The plan depends on the versions of the application and of the person; applying it
    returns {"link": {job_id, contact_id, name, role, confirmed}, "job": the job}.
    """
    if role not in domain.PERSON_ROLES:
        return domain.invalid_choice("role", role, domain.PERSON_ROLES)
    if confirmed is not None and not isinstance(confirmed, bool):
        return domain.error("invalid_input", f"Invalid confirmed '{confirmed}'. Use true or false.")
    origin = parse_source(source)
    if domain.is_error(origin):
        return origin
    changed_on = parse_reference_date("reference_date", reference_date)
    if domain.is_error(changed_on):
        return changed_on
    if get_job(connection, job_id, settings) is None:
        return domain.not_found("job", job_id)
    contact = connection.execute("SELECT name FROM contact WHERE id = ?", (contact_id,)).fetchone()
    if contact is None:
        return domain.not_found("contact", contact_id)
    record_id = application_id(connection, job_id)
    existing = connection.execute(
        "SELECT confirmed FROM application_person"
        " WHERE application_id = ? AND contact_id = ? AND role = ?",
        (record_id, contact_id, role),
    ).fetchone()
    link = {"job_id": job_id, "contact_id": contact_id, "name": contact["name"], "role": role}
    if existing is not None and (existing["confirmed"] or confirmed is not True):
        return domain.error(
            "duplicate_link",
            f"{contact['name']} is already linked to job {job_id} as {role}.",
            link={**link, "confirmed": bool(existing["confirmed"])},
        )
    new_confirmed = bool(confirmed)
    old_value = (
        None if existing is None else describe_link(contact["name"], contact_id, role, False)
    )
    new_value = describe_link(contact["name"], contact_id, role, new_confirmed)
    changes = [history.change("application_person", record_id, "link", old_value, new_value)]
    lines = [
        history.change(
            "application_person",
            record_id,
            "link",
            None if existing is None else link_value(contact_id, role, False),
            link_value(contact_id, role, new_confirmed),
        )
    ]

    def apply() -> dict:
        if existing is None:
            connection.execute(
                "INSERT INTO application_person (application_id, contact_id, role, confirmed)"
                " VALUES (?, ?, ?, ?)",
                (record_id, contact_id, role, int(new_confirmed)),
            )
        else:
            connection.execute(
                "UPDATE application_person SET confirmed = 1"
                " WHERE application_id = ? AND contact_id = ? AND role = ?",
                (record_id, contact_id, role),
            )
        history.record_lines(connection, lines, record_id, changed_on, *origin)
        return {
            "link": {**link, "confirmed": new_confirmed},
            "job": get_job(connection, job_id, settings),
        }

    return domain.Plan(
        changes=changes,
        base_versions={
            f"application:{record_id}": history.read_version(connection, "application", record_id),
            f"contact:{contact_id}": history.read_version(connection, "contact", contact_id),
        },
        apply=apply,
    )
