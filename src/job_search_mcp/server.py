"""MCP server: registers the tools, converts input and output and delegates to the domain.

No business rule lives here. Every tool reads the local settings, opens the configured
database, creates the schema when the database is new, calls the domain function and closes
the connection. Results and business errors are plain objects, so the client receives them
as structured content. Write tools only store a proposal (proposals.py): changes_confirm
applies it.
"""

import argparse
import datetime
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from job_search_mcp import companies, config, contacts, db, domain, jobs, proposals
from job_search_mcp import summary as summary_queries

mcp = FastMCP(
    "job-search",
    instructions=(
        "Tools to manage a job search: jobs, networking contacts, follow-ups and a daily "
        "summary. Every tool returns an object; a business error is an object with the keys "
        "'error' (a stable code) and 'detail' (a message to relay to the user). Writes take "
        "two steps: add_job, update_job, log_interaction, network_save_company, "
        "network_save_person, jobs_add_stage and jobs_link_person change nothing and "
        "return a proposal with the changes (each field with its current and proposed "
        "value). Show the changes to the user and call "
        "changes_confirm with the proposal id only after the user approves; otherwise call "
        "changes_discard. Proposals expire, and one whose records changed in the meantime is "
        "refused as stale: propose again."
    ),
)

JOB_STATUS_HELP = f"One of: {', '.join(domain.JOB_STATUSES)}."
CONTACT_STATUS_HELP = f"One of: {', '.join(domain.CONTACT_STATUSES)}."
PRIORITY_HELP = f"One of: {', '.join(domain.COMPANY_PRIORITIES)}."
ISO_DATE_HELP = "ISO 8601 date (YYYY-MM-DD)."
STAGE_KIND_HELP = f"One of: {', '.join(domain.STAGE_KINDS)}."
STAGE_RESULT_HELP = f"One of: {', '.join(domain.STAGE_RESULTS)}."
ROLE_HELP = f"One of: {', '.join(domain.PERSON_ROLES)}."
READ_ONLY = {"readOnlyHint": True}
SOURCE_HELP = (
    f"Where the information came from, written in the history: one of "
    f"{', '.join(domain.SOURCE_TYPES)}. Other text is kept as the reference of type 'user'."
)


def today() -> datetime.date:
    """The current date: the server reads the date only here (tests replace it)."""
    return datetime.date.today()


def now() -> datetime.datetime:
    """The current moment in UTC, for proposal expiry: the only other clock read."""
    return datetime.datetime.now(datetime.UTC)


def propose(tool: str, arguments: dict) -> dict:
    """Store a proposal for a write tool and return it, or the structured error."""
    with open_database() as connection:
        return proposals.create(connection, tool, arguments, now(), config.load_settings())


@contextmanager
def open_database() -> Iterator:
    """Open the configured database with the schema in place and always close it.

    A database of v0.1.0 is migrated to the current schema on the first opening (see
    db.create_schema).
    """
    connection = db.connect()
    try:
        db.create_schema(connection)
        yield connection
    finally:
        connection.close()


def past_date(field: str, value: str | None) -> datetime.date | dict | None:
    """Convert an ISO text received by a tool, refusing invalid text and dates after today.

    Returns the date, None when the value was not informed, or a structured error.
    """
    if value is None:
        return None
    try:
        parsed = db.to_date(value)
    except (ValueError, TypeError):
        return domain.invalid_date(field, value)
    if parsed > today():
        return domain.error(
            "invalid_date",
            f"Invalid {field} '{value}': it cannot be after today ({today().isoformat()}).",
        )
    return parsed


@mcp.tool(annotations=READ_ONLY)
def list_jobs(
    status: Annotated[
        str | None, Field(description=f"Keep only jobs in this status. {JOB_STATUS_HELP}")
    ] = None,
    track: Annotated[
        str | None,
        Field(description="Keep only jobs in this track: data, systems, product, ai or other."),
    ] = None,
    min_score: Annotated[
        float | None,
        Field(description="Keep only jobs whose fit score (0 to 10) is at least this value."),
    ] = None,
) -> dict[str, Any]:
    """List the registered jobs, ordered by id, optionally filtered.

    Returns {"jobs": [...]}. Each job has id, company, title, url, track, score, status,
    next_step, applied_on, last_contact_on, created_at, company_id, the calculated
    follow_up date (null when the status does not generate a follow-up), priority (high
    with a score of at least 7.5 or a confirmed referrer, medium with a score of at least
    7, otherwise low), stages (id, kind, date, result, feedback; by date) and people (id,
    name, role, confirmed).
    """
    with open_database() as connection:
        result = jobs.list_jobs(
            connection,
            status=status,
            track=track,
            min_score=min_score,
            settings=config.load_settings(),
        )
    return result if domain.is_error(result) else {"jobs": result}


@mcp.tool
def add_job(
    company: Annotated[str, Field(description="Name of the hiring company.")],
    title: Annotated[str, Field(description="Job title.")],
    url: Annotated[
        str, Field(description="Link of the job posting. It identifies the job: no duplicates.")
    ],
    track: Annotated[
        str | None, Field(description="Career track: data, systems, product, ai or other.")
    ] = None,
    score: Annotated[float | None, Field(description="Fit score from 0 to 10.")] = None,
    next_step: Annotated[str | None, Field(description="Next action to take on this job.")] = None,
    source: Annotated[str, Field(description=SOURCE_HELP)] = domain.USER_SOURCE,
) -> dict[str, Any]:
    """Propose registering a new job in the status 'suggested'.

    Changes nothing: returns {"proposal": {"id", "tool", "changes", "expires_at"}};
    each change has entity, record_id (null for a record to be created), field, old_value
    and new_value. Show the changes to the user and, after approval, call changes_confirm
    with the id (or changes_discard). Validation errors come back at once, without a
    proposal. Once confirmed, changes_confirm returns the created job. If a job with
    the same url already exists, the result is the error 'duplicate_url', with the existing
    job in the key 'job'. A track outside the valid ones, a score outside 0 to 10 or an
    empty source is the error 'invalid_input'.
    """
    return propose(
        "add_job",
        {
            "company": company,
            "title": title,
            "url": url,
            "track": track,
            "score": score,
            "next_step": next_step,
            "source": source,
            "reference_date": today().isoformat(),
        },
    )


@mcp.tool
def update_job(
    job_id: Annotated[int, Field(description="Id of the job to update (see list_jobs).")],
    source: Annotated[
        str,
        Field(description=SOURCE_HELP),
    ],
    status: Annotated[str | None, Field(description=f"New status. {JOB_STATUS_HELP}")] = None,
    next_step: Annotated[str | None, Field(description="New next action for this job.")] = None,
    applied_on: Annotated[
        str | None,
        Field(description=f"Date the application was sent. {ISO_DATE_HELP} Not after today."),
    ] = None,
    last_contact_on: Annotated[
        str | None,
        Field(description=f"Date of the last contact about it. {ISO_DATE_HELP} Not after today."),
    ] = None,
) -> dict[str, Any]:
    """Propose updating the informed fields of a job; fields left out are not touched.

    Changes nothing: returns {"proposal": {"id", "tool", "changes", "expires_at"}};
    each change has entity, record_id (null for a record to be created), field, old_value
    and new_value. Show the changes to the user and, after approval, call changes_confirm
    with the id (or changes_discard). Validation errors come back at once, without a
    proposal. Once confirmed, changes_confirm returns {"job": the updated job,
    "history": the history lines created}, one line for each field that really changed,
    dated the day of the proposal. Changing the status to 'applied' on a job without an
    application date sets applied_on to that day.
    """
    arguments = {"job_id": job_id, "source": source, "reference_date": today().isoformat()}
    arguments |= {"status": status, "next_step": next_step}
    for field, value in (("applied_on", applied_on), ("last_contact_on", last_contact_on)):
        parsed = past_date(field, value)
        if domain.is_error(parsed):
            return parsed
        arguments[field] = parsed.isoformat() if parsed else None
    return propose("update_job", arguments)


@mcp.tool(annotations=READ_ONLY)
def list_contacts(
    status: Annotated[
        str | None,
        Field(description=f"Keep only contacts in this status. {CONTACT_STATUS_HELP}"),
    ] = None,
    company: Annotated[
        str | None,
        Field(
            description=(
                "Keep only contacts of this company (whole name; case, accents and extra "
                "spaces are ignored)."
            )
        ),
    ] = None,
) -> dict[str, Any]:
    """List the networking contacts, ordered by id, optionally filtered.

    Returns {"contacts": [...]}. Each contact has id, name, company, relationship, channel,
    status, next_step, last_contact_on, job_id (the linked job, or null), company_id,
    role_title and the calculated follow_up date (null when the status does not generate a
    follow-up).
    """
    with open_database() as connection:
        result = contacts.list_contacts(
            connection, status=status, company=company, settings=config.load_settings()
        )
    return result if domain.is_error(result) else {"contacts": result}


@mcp.tool
def log_interaction(
    contact_id: Annotated[int, Field(description="Id of the contact (see list_contacts).")],
    summary: Annotated[str, Field(description="Short summary of what was talked about.")],
    date: Annotated[
        str | None,
        Field(description=f"Date of the interaction. {ISO_DATE_HELP} Defaults to today."),
    ] = None,
    status: Annotated[
        str | None, Field(description=f"New status of the contact. {CONTACT_STATUS_HELP}")
    ] = None,
    next_step: Annotated[str | None, Field(description="New next action for this contact.")] = None,
) -> dict[str, Any]:
    """Propose recording a conversation with a contact and recalculating its follow-up.

    Changes nothing: returns {"proposal": {"id", "tool", "changes", "expires_at"}};
    each change has entity, record_id (null for a record to be created), field, old_value
    and new_value. Show the changes to the user and, after approval, call changes_confirm
    with the id (or changes_discard). Validation errors come back at once, without a
    proposal. Once confirmed, changes_confirm returns {"contact": the updated
    contact, "follow_up": the new follow-up date, "job": the linked job when the contact is
    linked to exactly one, otherwise null, "jobs": every linked job}. Here a linked job is
    one the contact is linked to in any role (see jobs_link_person), while the job_id of
    the contact (list_contacts) only follows the role 'contact'. The last contact date of
    every active linked job is updated too; closed jobs (hired, rejected, withdrawn,
    closed) are left as they are. A contact in 'to_contact' logged without a status moves
    to 'awaiting_reply'.
    """
    interaction_date = past_date("date", date) if date is not None else today()
    if domain.is_error(interaction_date):
        return interaction_date
    return propose(
        "log_interaction",
        {
            "contact_id": contact_id,
            "summary": summary,
            "date": interaction_date.isoformat(),
            "status": status,
            "next_step": next_step,
        },
    )


@mcp.tool(annotations=READ_ONLY)
def network_list_companies(
    priority: Annotated[
        str | None,
        Field(description=f"Keep only companies with this priority. {PRIORITY_HELP}"),
    ] = None,
) -> dict[str, Any]:
    """List the companies, ordered by id, optionally only those with a given priority.

    Returns {"companies": [...]}. Each company has id, name, sector, priority (the one the
    user chose, or null), job_platform, notes and suggested_priority: 'A' when the company
    has an active person (status other than closed) or an active application (status not
    hired, rejected, withdrawn or closed), otherwise null.
    """
    with open_database() as connection:
        result = companies.list_companies(connection, priority=priority)
    return result if domain.is_error(result) else {"companies": result}


@mcp.tool(annotations=READ_ONLY)
def network_company_overview(
    company_id: Annotated[
        int, Field(description="Id of the company (see network_list_companies).")
    ],
) -> dict[str, Any]:
    """Who the user knows at a company and what is open there.

    Returns {"company": as in network_list_companies, "people": every person of the company
    as in list_contacts, "applications": its active applications, each with its job, as in
    list_jobs}.
    """
    with open_database() as connection:
        return companies.company_overview(connection, company_id, config.load_settings())


@mcp.tool
def network_save_company(
    source: Annotated[str, Field(description=SOURCE_HELP)],
    name: Annotated[
        str | None,
        Field(
            description=(
                "Name of the company; unique, ignoring case, accents and spaces. Required to "
                "create; in a change, leave it out to keep the current name."
            )
        ),
    ] = None,
    company_id: Annotated[
        int | None,
        Field(description="Id of the company to change; leave it out to create a company."),
    ] = None,
    sector: Annotated[str | None, Field(description="Business sector.")] = None,
    priority: Annotated[
        str | None, Field(description=f"Priority the user gives it. {PRIORITY_HELP}")
    ] = None,
    job_platform: Annotated[
        str | None, Field(description="Platform where the company posts its jobs.")
    ] = None,
    notes: Annotated[str | None, Field(description="Free notes about the company.")] = None,
) -> dict[str, Any]:
    """Propose creating a company, or changing the informed fields of one.

    Changes nothing: returns {"proposal": {"id", "tool", "changes", "expires_at"}};
    each change has entity, record_id (null for a record to be created), field, old_value
    and new_value. Show the changes to the user and, after approval, call changes_confirm
    with the id (or changes_discard). Validation errors come back at once, without a
    proposal. Fields left out are not touched. Once confirmed, changes_confirm
    returns {"company": the saved company}. A name already used by another company is the
    error 'duplicate_company', with that company in the key 'company'.
    """
    return propose(
        "network_save_company",
        {
            "company_id": company_id,
            "name": name,
            "sector": sector,
            "priority": priority,
            "job_platform": job_platform,
            "notes": notes,
            "source": source,
            "reference_date": today().isoformat(),
        },
    )


@mcp.tool
def network_save_person(
    source: Annotated[str, Field(description=SOURCE_HELP)],
    name: Annotated[
        str | None,
        Field(
            description=(
                "Name of the person. Required to create; in a change, leave it out to keep "
                "the current name."
            )
        ),
    ] = None,
    contact_id: Annotated[
        int | None,
        Field(
            description="Id of the person to change (see list_contacts); leave it out to "
            "create a person."
        ),
    ] = None,
    company: Annotated[
        str | None,
        Field(
            description=(
                "Name of the person's company, found ignoring case, accents and spaces; "
                "a company not registered yet is created too."
            )
        ),
    ] = None,
    role_title: Annotated[str | None, Field(description="Job title of the person.")] = None,
    relationship: Annotated[str | None, Field(description="How the user knows the person.")] = None,
    channel: Annotated[
        str | None, Field(description="Where to talk to the person, such as linkedin or email.")
    ] = None,
    status: Annotated[
        str | None,
        Field(
            description=(
                f"Status of the person. {CONTACT_STATUS_HELP} A new person defaults to "
                "to_contact; on_hold stops the follow-ups until changed."
            )
        ),
    ] = None,
    next_step: Annotated[str | None, Field(description="Next action with this person.")] = None,
) -> dict[str, Any]:
    """Propose creating a person, or changing the informed fields of one.

    Changes nothing: returns {"proposal": {"id", "tool", "changes", "expires_at"}};
    each change has entity, record_id (null for a record to be created), field, old_value
    and new_value. Show the changes to the user and, after approval, call changes_confirm
    with the id (or changes_discard). Validation errors come back at once, without a
    proposal. Fields left out are not touched. Once confirmed, changes_confirm
    returns {"contact": the saved contact}, as in list_contacts.
    """
    return propose(
        "network_save_person",
        {
            "contact_id": contact_id,
            "name": name,
            "company": company,
            "role_title": role_title,
            "relationship": relationship,
            "channel": channel,
            "status": status,
            "next_step": next_step,
            "source": source,
            "reference_date": today().isoformat(),
        },
    )


@mcp.tool
def jobs_add_stage(
    job_id: Annotated[int, Field(description="Id of the job (see list_jobs).")],
    kind: Annotated[str, Field(description=f"Kind of stage. {STAGE_KIND_HELP}")],
    date: Annotated[str, Field(description=f"Date of the stage. {ISO_DATE_HELP} Not after today.")],
    source: Annotated[str, Field(description=SOURCE_HELP)],
    result: Annotated[
        str | None, Field(description=f"Result of the stage. {STAGE_RESULT_HELP} Default: pending.")
    ] = None,
    feedback: Annotated[str | None, Field(description="Feedback received, if any.")] = None,
    status: Annotated[
        str | None, Field(description=f"New status of the application. {JOB_STATUS_HELP}")
    ] = None,
) -> dict[str, Any]:
    """Propose recording a dated stage of a job application (interview, test, offer...).

    Changes nothing: returns {"proposal": {"id", "tool", "changes", "expires_at"}};
    each change has entity, record_id (null for a record to be created), field, old_value
    and new_value. Show the changes to the user and, after approval, call changes_confirm
    with the id (or changes_discard). Validation errors come back at once, without a
    proposal. A stage of the same kind on the same date is the error 'duplicate_stage'
    (with the existing stage in 'stage'). The proposal holds the stage and, when
    informed, the new status of the application; when the stage is more recent than the
    last contact of the job, the last contact moves to the stage date; a job that becomes 'applied' without an application
    date gets the stage date. Once confirmed, changes_confirm returns {"stage",
    "job": the updated job, "history": the history lines of the job}.
    """
    stage_date = past_date("date", date)
    if domain.is_error(stage_date):
        return stage_date
    return propose(
        "jobs_add_stage",
        {
            "job_id": job_id,
            "kind": kind,
            "date": stage_date.isoformat(),
            "result": result,
            "feedback": feedback,
            "status": status,
            "source": source,
            "reference_date": today().isoformat(),
        },
    )


@mcp.tool
def jobs_link_person(
    job_id: Annotated[int, Field(description="Id of the job (see list_jobs).")],
    contact_id: Annotated[int, Field(description="Id of the person (see list_contacts).")],
    role: Annotated[str, Field(description=f"Role of the person in the application. {ROLE_HELP}")],
    source: Annotated[str, Field(description=SOURCE_HELP)],
    confirmed: Annotated[
        bool | None,
        Field(
            description=(
                "Whether the link is confirmed (for a referrer: the referral was really made). "
                "A new link defaults to false; true on an existing unconfirmed link confirms it."
            )
        ),
    ] = None,
) -> dict[str, Any]:
    """Propose linking a person to a job application with a role, or confirming a link.

    Changes nothing: returns {"proposal": {"id", "tool", "changes", "expires_at"}};
    each change has entity, record_id (null for a record to be created), field, old_value
    and new_value. Show the changes to the user and, after approval, call changes_confirm
    with the id (or changes_discard). Validation errors come back at once, without a
    proposal. The same person with the same role is the error 'duplicate_link' (with the
    existing link in 'link'), unless the link is not confirmed yet and confirmed is true.
    A confirmed referrer makes the job a high priority. Once confirmed, changes_confirm
    returns {"link": {job_id, contact_id, name, role, confirmed}, "job": the job}.
    """
    return propose(
        "jobs_link_person",
        {
            "job_id": job_id,
            "contact_id": contact_id,
            "role": role,
            "confirmed": confirmed,
            "source": source,
            "reference_date": today().isoformat(),
        },
    )


@mcp.tool
def changes_confirm(
    proposal_id: Annotated[
        str, Field(description="Id of the proposal the user approved (from a write tool).")
    ],
) -> dict[str, Any]:
    """Apply a proposal the user approved, exactly as it was shown.

    Returns what the proposing tool returns once applied (add_job: the created job;
    update_job: {"job", "history"}; log_interaction: {"contact", "follow_up", "job",
    "jobs"}; network_save_company: {"company"}; network_save_person: {"contact"};
    jobs_add_stage: {"stage", "job", "history"}; jobs_link_person: {"link", "job"}).
    Errors: 'stale_proposal' when the records changed since the proposal (nothing is
    written: propose again), 'expired_proposal' when it is past its expiry, and
    'not_found' for an unknown id or a proposal already applied or discarded.
    """
    with open_database() as connection:
        return proposals.confirm(connection, proposal_id, now(), config.load_settings())


@mcp.tool
def changes_discard(
    proposal_id: Annotated[str, Field(description="Id of the proposal to drop.")],
) -> dict[str, Any]:
    """Drop a pending proposal the user did not approve; nothing else changes.

    Returns {"proposal": {"id", "tool", "status": "discarded"}}, or the errors of
    changes_confirm.
    """
    with open_database() as connection:
        return proposals.discard(connection, proposal_id, now())


@mcp.tool(annotations=READ_ONLY)
def changes_list_pending() -> dict[str, Any]:
    """List the proposals still waiting for the user's decision, oldest first.

    Returns {"proposals": [...]}, each with id, tool, changes, created_at and expires_at
    (UTC). Proposals past their expiry are marked expired and left out.
    """
    with open_database() as connection:
        return {"proposals": proposals.list_pending(connection, now())}


@mcp.tool(annotations=READ_ONLY)
def pending_followups(
    reference_date: Annotated[
        str | None,
        Field(description=f"Date the follow-ups are compared to. {ISO_DATE_HELP} Default: today."),
    ] = None,
    days_ahead: Annotated[
        int,
        Field(description="How many days ahead still count as due soon. Integer, 0 or more."),
    ] = summary_queries.DEFAULT_DAYS_AHEAD,
) -> dict[str, Any]:
    """Jobs and contacts whose follow-up is overdue or due soon: who the user has to chase.

    Returns {"reference_date", "days_ahead", "jobs": [...], "contacts": [...]}. Each item is
    the job or contact plus 'follow_up' and 'state' ('overdue' or 'due_soon'), from the
    oldest follow-up to the most recent. Closed jobs and contacts are left out.
    """
    if days_ahead < 0:
        return domain.error(
            "invalid_input", f"Invalid days_ahead '{days_ahead}'. Use an integer of 0 or more."
        )
    with open_database() as connection:
        return summary_queries.pending_followups(
            connection,
            reference_date if reference_date is not None else today(),
            days_ahead,
            settings=config.load_settings(),
        )


@mcp.tool(annotations=READ_ONLY)
def daily_summary(
    reference_date: Annotated[
        str | None,
        Field(description=f"Date the summary is built for. {ISO_DATE_HELP} Default: today."),
    ] = None,
    deadline: Annotated[
        str | None,
        Field(
            description=(
                f"Date the user wants to be hired by, if any. {ISO_DATE_HELP} "
                "Default: goals.deadline from the local settings, if set."
            )
        ),
    ] = None,
) -> dict[str, Any]:
    """Summary of the day: what the user should do today in the job search.

    Returns {"reference_date", "jobs_by_status" (count for every status), "active_contacts",
    "overdue" and "due_soon" (each with "jobs" and "contacts"), "application_queue" (jobs
    still to apply for, highest score first), "deadline" and "days_to_deadline"}.
    """
    with open_database() as connection:
        return summary_queries.daily_summary(
            connection,
            reference_date if reference_date is not None else today(),
            deadline,
            settings=config.load_settings(),
        )


def seed_database() -> str | None:
    """Load the synthetic demo data into a new database; return a message when it is refused."""
    # Checked before the database is opened: missing demo data is not a JOB_SEARCH_DB problem,
    # and no empty database file is left behind.
    for name in ("jobs.csv", "contacts.csv"):
        try:
            (db.SEED_DIR / name).open(encoding="utf-8").close()
        except OSError as failure:
            return (
                f"Could not read the demo data in {db.SEED_DIR}: {failure}. The demo data "
                "comes with the repository (data/seed/): install from a clone, with "
                "pip install -e ."
            )
    with open_database() as connection:
        for table in ("company", "job", "contact", "interaction", "history"):
            if connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                return (
                    f"Refused: the database at {db.default_db_path()} already has data. "
                    f"The demo data only goes into a new database; point {db.DB_ENV_VAR} to "
                    "another file."
                )
        db.load_seed(connection)
    return None


def main(argv: list[str] | None = None) -> int:
    """Command line entry point: run the server over stdio, or load the demo data and exit."""
    parser = argparse.ArgumentParser(
        prog="job-search-mcp",
        description=(
            "MCP server for managing a job search, over stdio. The database path comes from "
            f"{db.DB_ENV_VAR} (default: data/local/job_search.db under the project); the "
            f"optional local settings file, from {config.CONFIG_ENV_VAR}."
        ),
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="load the synthetic demo data into a new database and exit, without serving",
    )
    arguments = parser.parse_args(argv)
    try:
        config.load_settings()
    except config.ConfigError as failure:
        # Checked at startup, so a broken settings file is reported once, without traceback.
        print(failure, file=sys.stderr)
        return 1
    if arguments.seed:
        try:
            refusal = seed_database()
        except (OSError, sqlite3.Error) as failure:
            # Invalid path, a directory in place of the file, no permission: no traceback.
            print(
                f"Could not load the demo data into {db.default_db_path()}: {failure}. "
                f"Check the path in {db.DB_ENV_VAR}.",
                file=sys.stderr,
            )
            return 1
        if refusal:
            print(refusal, file=sys.stderr)
            return 1
        print(f"Demo data loaded into {db.default_db_path()}.", file=sys.stderr)
        return 0
    # stdout carries the protocol: nothing else may be written to it.
    mcp.run(transport="stdio", show_banner=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
