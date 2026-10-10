"""MCP server: registers the seven tools, converts input and output and delegates to the domain.

No business rule lives here. Every tool opens the configured database, creates the schema
when the database is new, calls the domain function and closes the connection. Results and
business errors are plain objects, so the client receives them as structured content.
"""

import argparse
import datetime
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from job_search_mcp import contacts, db, domain, jobs
from job_search_mcp import summary as summary_queries

mcp = FastMCP(
    "job-search",
    instructions=(
        "Tools to manage a job search: jobs, networking contacts, follow-ups and a daily "
        "summary. Every tool returns an object; a business error is an object with the keys "
        "'error' (a stable code) and 'detail' (a message to relay to the user)."
    ),
)

JOB_STATUS_HELP = f"One of: {', '.join(domain.JOB_STATUSES)}."
CONTACT_STATUS_HELP = f"One of: {', '.join(domain.CONTACT_STATUSES)}."
ISO_DATE_HELP = "ISO 8601 date (YYYY-MM-DD)."
READ_ONLY = {"readOnlyHint": True}


def today() -> datetime.date:
    """The current date: the only place the server reads the clock (tests replace it)."""
    return datetime.date.today()


@contextmanager
def open_database() -> Iterator:
    """Open the configured database with the schema in place and always close it."""
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
    next_step, applied_on, last_contact_on, created_at and the calculated follow_up date
    (null when the status does not generate a follow-up).
    """
    with open_database() as connection:
        result = jobs.list_jobs(connection, status=status, track=track, min_score=min_score)
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
) -> dict[str, Any]:
    """Register a new job in the status 'suggested'.

    Returns the created job. If a job with the same url already exists, nothing is created
    and the result is the error 'duplicate_url', with the existing job in the key 'job'.
    """
    with open_database() as connection:
        return jobs.add_job(
            connection, company, title, url, track=track, score=score, next_step=next_step
        )


@mcp.tool
def update_job(
    job_id: Annotated[int, Field(description="Id of the job to update (see list_jobs).")],
    source: Annotated[
        str,
        Field(description="Where the change came from, written in the history (e.g. 'user')."),
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
    """Update the informed fields of a job; fields left out are not touched.

    Returns {"job": the updated job, "history": the history lines created}, one line for
    each field that really changed, dated today. Changing the status to 'applied' on a job
    without an application date sets applied_on to today.
    """
    dates = {}
    for field, value in (("applied_on", applied_on), ("last_contact_on", last_contact_on)):
        dates[field] = past_date(field, value)
        if domain.is_error(dates[field]):
            return dates[field]
    with open_database() as connection:
        return jobs.update_job(
            connection, job_id, source, today(), status=status, next_step=next_step, **dates
        )


@mcp.tool(annotations=READ_ONLY)
def list_contacts(
    status: Annotated[
        str | None,
        Field(description=f"Keep only contacts in this status. {CONTACT_STATUS_HELP}"),
    ] = None,
    company: Annotated[
        str | None, Field(description="Keep only contacts of this company (whole name).")
    ] = None,
) -> dict[str, Any]:
    """List the networking contacts, ordered by id, optionally filtered.

    Returns {"contacts": [...]}. Each contact has id, name, company, relationship, channel,
    status, next_step, last_contact_on, job_id (the linked job, or null) and the calculated
    follow_up date (null when the status does not generate a follow-up).
    """
    with open_database() as connection:
        result = contacts.list_contacts(connection, status=status, company=company)
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
    """Record a conversation with a contact and recalculate its follow-up.

    Returns {"contact": the updated contact, "follow_up": the new follow-up date, "job": the
    linked job or null}. The last contact date of a linked job is updated too. A contact in
    'to_contact' logged without a status moves to 'awaiting_reply'.
    """
    interaction_date = past_date("date", date) if date is not None else today()
    if domain.is_error(interaction_date):
        return interaction_date
    with open_database() as connection:
        return contacts.log_interaction(
            connection, contact_id, summary, interaction_date, status=status, next_step=next_step
        )


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
            connection, reference_date if reference_date is not None else today(), days_ahead
        )


@mcp.tool(annotations=READ_ONLY)
def daily_summary(
    reference_date: Annotated[
        str | None,
        Field(description=f"Date the summary is built for. {ISO_DATE_HELP} Default: today."),
    ] = None,
    deadline: Annotated[
        str | None,
        Field(description=f"Date the user wants to be hired by, if any. {ISO_DATE_HELP}"),
    ] = None,
) -> dict[str, Any]:
    """Summary of the day: what the user should do today in the job search.

    Returns {"reference_date", "jobs_by_status" (count for every status), "active_contacts",
    "overdue" and "due_soon" (each with "jobs" and "contacts"), "application_queue" (jobs
    still to apply for, highest score first), "deadline" and "days_to_deadline"}.
    """
    with open_database() as connection:
        return summary_queries.daily_summary(
            connection, reference_date if reference_date is not None else today(), deadline
        )


def seed_database() -> str | None:
    """Load the synthetic demo data into a new database; return a message when it is refused."""
    with open_database() as connection:
        for table in ("job", "contact", "interaction", "job_history"):
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
            f"{db.DB_ENV_VAR} (default: data/local/job_search.db under the project)."
        ),
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="load the synthetic demo data into a new database and exit, without serving",
    )
    arguments = parser.parse_args(argv)
    if arguments.seed:
        refusal = seed_database()
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
