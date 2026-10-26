"""Company operations: list companies, show one with its people and active applications, and
plan the creation or change of a company, whose normalized name is unique.

The priority of a company is the one the user chose (A, B, C or null); `suggested_priority`
is calculated at reading time: A when the company has an active person or an active
application, null otherwise.
"""

import sqlite3
from datetime import date

from job_search_mcp import contacts, db, domain, history, jobs
from job_search_mcp.config import Settings


def _sql_list(values) -> str:
    """SQL text of a list of fixed domain constants (never user input)."""
    return ", ".join(f"'{value}'" for value in sorted(values))


ACTIVE_APPLICATION = f"application.status NOT IN ({_sql_list(domain.JOB_CLOSED_STATUSES)})"
COMPANY_SELECT = f"""
SELECT company.id, company.name, company.sector, company.priority, company.job_platform,
    company.notes,
    CASE WHEN EXISTS (
        SELECT 1 FROM contact WHERE contact.company_id = company.id
        AND contact.status NOT IN ({_sql_list(domain.CONTACT_CLOSED_STATUSES)})
    ) OR EXISTS (
        SELECT 1 FROM job JOIN application ON application.job_id = job.id
        WHERE job.company_id = company.id AND {ACTIVE_APPLICATION}
    ) THEN '{domain.SUGGESTED_PRIORITY}' END AS suggested_priority
FROM company
"""


def get_company(connection: sqlite3.Connection, company_id: int) -> dict | None:
    row = connection.execute(f"{COMPANY_SELECT} WHERE company.id = ?", (company_id,)).fetchone()
    return dict(row) if row else None


def list_companies(
    connection: sqlite3.Connection, priority: str | None = None
) -> list[dict] | dict:
    """List companies ordered by id, optionally only the ones with this stored priority."""
    if priority is not None and priority not in domain.COMPANY_PRIORITIES:
        return domain.invalid_priority(priority)
    where, parameters = (
        ("", []) if priority is None else (" WHERE company.priority = ?", [priority])
    )
    rows = connection.execute(f"{COMPANY_SELECT}{where} ORDER BY company.id", parameters)
    return [dict(row) for row in rows]


def company_overview(
    connection: sqlite3.Connection, company_id: int, settings: Settings | None = None
) -> dict:
    """The company, every person linked to it and its active applications (with the job).

    People come as in list_contacts and applications as in list_jobs, ordered by id; an
    application is active when its status is not closed (hired, rejected, withdrawn,
    closed).
    """
    company = get_company(connection, company_id)
    if company is None:
        return domain.not_found("company", company_id)
    people = connection.execute(
        f"{contacts.CONTACT_SELECT} WHERE contact.company_id = ? ORDER BY contact.id",
        (company_id,),
    )
    applications = connection.execute(
        f"{jobs.JOB_SELECT} WHERE job.company_id = ? AND {ACTIVE_APPLICATION} ORDER BY job.id",
        (company_id,),
    )
    return {
        "company": company,
        "people": [contacts.contact_to_dict(row, settings) for row in people],
        "applications": jobs.jobs_from_rows(connection, applications.fetchall(), settings),
    }


def duplicate_company(
    connection: sqlite3.Connection, name: str, company_id: int | None = None
) -> dict | None:
    """The error 'duplicate_company' when another company has this normalized name."""
    row = connection.execute(
        "SELECT id FROM company WHERE normalized_name = ? AND id IS NOT ?",
        (db.normalize_name(name), company_id),
    ).fetchone()
    if row is None:
        return None
    return domain.error(
        "duplicate_company",
        f"A company with this name already exists (id {row['id']}).",
        company=get_company(connection, row["id"]),
    )


def plan_save_company(
    connection: sqlite3.Connection,
    name: str | None = None,
    company_id: int | None = None,
    sector: str | None = None,
    priority: str | None = None,
    job_platform: str | None = None,
    notes: str | None = None,
    *,
    source: str,
    reference_date: str | date,
    settings: Settings | None = None,
) -> domain.Plan | dict:
    """Plan the creation of a company (no `company_id`) or the change of one, writing nothing.

    The name is required to create and optional in a change. It is unique by normalized
    name (db.normalize_name): creating or renaming to the name of another company is the
    error 'duplicate_company', with that company in the key 'company'. `priority` is one of domain.COMPANY_PRIORITIES. In a
    change, fields left as None (or blank) are not touched. `source` and `reference_date`
    go to the history, one line per created or changed field. A change depends on the
    version of the company; applying the plan returns {"company": the saved company}.
    """
    name = domain.optional_text(name)
    if name is None and company_id is None:
        return domain.error("invalid_input", "Field 'name' is required to create a company.")
    if priority is not None and priority not in domain.COMPANY_PRIORITIES:
        return domain.invalid_priority(priority)
    origin = jobs.parse_source(source)
    if domain.is_error(origin):
        return origin
    changed_on = jobs.parse_reference_date("reference_date", reference_date)
    if domain.is_error(changed_on):
        return changed_on
    current = None
    if company_id is not None:
        current = get_company(connection, company_id)
        if current is None:
            return domain.not_found("company", company_id)
    duplicate = duplicate_company(connection, name, company_id) if name is not None else None
    if duplicate:
        return duplicate
    informed = {
        "name": name,
        "sector": domain.optional_text(sector),
        "priority": priority,
        "job_platform": domain.optional_text(job_platform),
        "notes": domain.optional_text(notes),
    }
    values = {field: value for field, value in informed.items() if value is not None}

    if current is None:

        def create() -> dict:
            new_id = connection.execute(
                "INSERT INTO company (name, normalized_name, sector, priority, job_platform,"
                " notes) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    name,
                    db.normalize_name(name),
                    informed["sector"],
                    priority,
                    informed["job_platform"],
                    informed["notes"],
                ),
            ).lastrowid
            history.record_creation(connection, "company", new_id, values, changed_on, *origin)
            return {"company": get_company(connection, new_id)}

        return domain.Plan(
            changes=history.creation("company", values), base_versions={}, apply=create
        )

    def update() -> dict:
        lines = history.record_changes(
            connection, "company", company_id, current, values, changed_on, *origin
        )
        if any(line["field"] == "name" for line in lines):
            connection.execute(
                "UPDATE company SET normalized_name = ? WHERE id = ?",
                (db.normalize_name(name), company_id),
            )
        return {"company": get_company(connection, company_id)}

    return domain.Plan(
        changes=history.diff("company", company_id, current, values),
        base_versions={
            f"company:{company_id}": history.read_version(connection, "company", company_id)
        },
        apply=update,
    )
