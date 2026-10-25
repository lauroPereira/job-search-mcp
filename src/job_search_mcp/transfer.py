"""Import and export of the CSV files documented in docs/import-format.md.

A folder holds up to six files (FILES), all optional. The files point to each other without
internal ids: jobs and people name their company, interactions name the person (name and
company), stages and links name the job by its URL and the person by name and company.

The import reads and checks every row, skips the duplicates (also inside the same file) and
reports, per file, the new rows, the duplicates and the rows with an error, with the line
and the reason. An invalid row never stops the others. Everything runs in one transaction:
it is committed only when `apply` is true, so a report without apply writes nothing. Every
created record gets history lines with source_type 'import' and the file and line as the
reference. The import only creates records: a duplicate is skipped even when its other
columns differ.
"""

import csv
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from job_search_mcp import db, domain, history, jobs

IMPORT_SOURCE = "import"
DEFAULT_JOB_STATUS = "suggested"
DEFAULT_PERSON_STATUS = "to_contact"
TRUE_TEXTS = ("true", "1", "yes", "sim")
FALSE_TEXTS = ("false", "0", "no", "nao", "não")

# Columns of each file, in the order the export writes them; the required ones (REQUIRED)
# must be in the header and filled in on every row.
COLUMNS = {
    "companies.csv": ("name", "sector", "priority", "job_platform", "notes"),
    "people.csv": (
        "name",
        "company",
        "role_title",
        "relationship",
        "channel",
        "status",
        "next_step",
        "last_contact_on",
    ),
    "jobs.csv": (
        "url",
        "company",
        "title",
        "track",
        "score",
        "created_at",
        "status",
        "applied_on",
        "last_contact_on",
        "next_step",
        "resume_track",
        "salary_ask",
        "contract_type",
    ),
    "interactions.csv": ("person", "person_company", "date", "summary", "channel", "source_type"),
    "stages.csv": ("job_url", "kind", "date", "result", "feedback"),
    "links.csv": ("job_url", "person", "person_company", "role", "confirmed"),
}
REQUIRED = {
    "companies.csv": ("name",),
    "people.csv": ("name",),
    "jobs.csv": ("url", "company", "title"),
    "interactions.csv": ("person", "date", "summary"),
    "stages.csv": ("job_url", "kind", "date"),
    "links.csv": ("job_url", "person", "role"),
}
# Import order: a file only points to records of the files before it (or of the database).
FILES = tuple(COLUMNS)


class RowError(ValueError):
    """A row that cannot be imported; the message is the reason shown in the report."""


@dataclass
class FileReport:
    """What the import did (or would do) with one file; lines are the lines of the file."""

    present: bool = False
    new: list[int] = field(default_factory=list)
    duplicates: list[tuple[int, str]] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class ImportReport:
    """Report of an import: one FileReport per file and the companies created because a
    job or person named them without a row in companies.csv."""

    folder: Path
    applied: bool
    files: dict[str, FileReport] = field(default_factory=dict)
    cited_companies: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(len(report.errors) for report in self.files.values())

    def to_text(self) -> str:
        lines = [f"Import of {self.folder}"]
        for name, report in self.files.items():
            if not report.present:
                lines.append(f"{name}: not found, skipped")
                continue
            lines.append(
                f"{name}: {len(report.new)} new, {len(report.duplicates)} duplicates, "
                f"{len(report.errors)} with errors"
            )
            lines += [f"  line {line}: duplicate: {reason}" for line, reason in report.duplicates]
            lines += [f"  line {line}: error: {reason}" for line, reason in report.errors]
        if self.cited_companies:
            lines.append(
                "Companies created because a job or person names them: "
                + ", ".join(self.cited_companies)
            )
        if self.applied:
            lines.append("Applied: the new rows were written to the database.")
        else:
            lines.append("Nothing was written: run again with --apply to write the new rows.")
        return "\n".join(lines)


def normalize_url(url: str) -> str:
    """Job URL used to find duplicates: trimmed, scheme and host in lowercase, without the
    fragment (#...) and without a trailing slash on the path."""
    parts = urlsplit(url.strip())
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, "")
    )


def _iso_date(column: str, value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise RowError(f"invalid {column} '{value}': use YYYY-MM-DD") from None


def _timestamp(column: str, value: str | None) -> str | None:
    """created_at as stored (YYYY-MM-DD HH:MM:SS); a date alone gets midnight."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise RowError(
            f"invalid {column} '{value}': use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS"
        ) from None


def _choice(column: str, value: str | None, valid: tuple[str, ...], default=None):
    if value is None:
        return default
    if value not in valid:
        raise RowError(f"invalid {column} '{value}': use one of {', '.join(valid)}")
    return value


def _score(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        score = float(value)
    except ValueError:
        score = None
    if not domain.is_valid_score(score):
        raise RowError(
            f"invalid score '{value}': use a number from {domain.SCORE_MIN} to "
            f"{domain.SCORE_MAX}, with a dot as decimal separator"
        )
    return score


def _confirmed(value: str | None) -> bool:
    if value is None:
        return False
    text = value.lower()
    if text in TRUE_TEXTS:
        return True
    if text in FALSE_TEXTS:
        return False
    raise RowError(f"invalid confirmed '{value}': use true or false")


def _read(path: Path, name: str) -> tuple[list[tuple[int, dict]], str | None]:
    """Rows of a file as (line, {column: text or None}), or the reason the file is refused."""
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        header = [column.strip() for column in reader.fieldnames or []]
        unknown = [column for column in header if column not in COLUMNS[name]]
        missing = [column for column in REQUIRED[name] if column not in header]
        if unknown or missing:
            problems = []
            if missing:
                problems.append(f"missing required columns: {', '.join(missing)}")
            if unknown:
                problems.append(f"unknown columns: {', '.join(unknown)}")
            return [], "; ".join(problems)
        reader.fieldnames = header
        rows = []
        for row in reader:
            values = {column: None for column in COLUMNS[name]}
            for column in header:
                values[column] = domain.optional_text(row.get(column))
            if None in row:
                values = {"__extra__": True}
            rows.append((reader.line_num, values))
    return rows, None


class _Importer:
    """Imports the files of one folder through one connection, inside its transaction."""

    def __init__(
        self, connection: sqlite3.Connection, changed_on: date | None, record_history: bool
    ):
        self.connection = connection
        self.changed_on = changed_on
        self.record_history = record_history
        self.cited: list[str] = []
        self.created_here: dict[tuple, str] = {}
        self.jobs = {
            normalize_url(row["url"]): row["id"]
            for row in connection.execute("SELECT id, url FROM job")
        }
        self.people = {
            (db.normalize_name(row["name"]), row["company_id"]): row["id"]
            for row in connection.execute("SELECT id, name, company_id FROM contact")
        }

    def _history(self, entity: str, record_id: int, values: dict, ref: str) -> None:
        if not self.record_history:
            return
        history.record_creation(
            self.connection, entity, record_id, values, self.changed_on, IMPORT_SOURCE, ref
        )

    def _duplicate(self, key: tuple, what: str) -> str:
        where = self.created_here.get(key)
        return f"{what} {'of ' + where if where else 'already in the database'}"

    def _find_company(self, name: str) -> int | None:
        row = self.connection.execute(
            "SELECT id FROM company WHERE normalized_name = ?", (db.normalize_name(name),)
        ).fetchone()
        return row[0] if row else None

    def _company_id(self, name: str | None, ref: str) -> int | None:
        """Id of the company with this name, creating it (as cited) when missing."""
        if name is None:
            return None
        found = self._find_company(name)
        if found is not None:
            return found
        company_id = db.ensure_company(self.connection, name)
        self._history("company", company_id, {"name": name}, ref)
        self.cited.append(name)
        return company_id

    def _existing_company_id(self, name: str | None) -> int | None:
        """Id of a company named by a person reference; a missing one is an error."""
        if name is None:
            return None
        found = self._find_company(name)
        if found is None:
            raise RowError(f"unknown company '{name}'")
        return found

    def _person_id(self, name: str, company: str | None) -> int:
        key = (db.normalize_name(name), self._existing_company_id(company))
        if key not in self.people:
            at = f" at '{company}'" if company else " without company"
            raise RowError(f"unknown person '{name}'{at}")
        return self.people[key]

    def _job_application(self, url: str) -> tuple[int, int]:
        job_id = self.jobs.get(normalize_url(url))
        if job_id is None:
            raise RowError(f"unknown job URL '{url}'")
        return job_id, jobs.application_id(self.connection, job_id)

    def companies(self, row: dict, ref: str) -> str | None:
        priority = _choice("priority", row["priority"], domain.COMPANY_PRIORITIES)
        normalized = db.normalize_name(row["name"])
        if self._find_company(row["name"]) is not None:
            return self._duplicate(("company", normalized), f"company '{row['name']}'")
        values = {
            "name": row["name"],
            "sector": row["sector"],
            "priority": priority,
            "job_platform": row["job_platform"],
            "notes": row["notes"],
        }
        company_id = self.connection.execute(
            "INSERT INTO company (name, normalized_name, sector, priority, job_platform, notes)"
            " VALUES (:name, :normalized, :sector, :priority, :job_platform, :notes)",
            {**values, "normalized": normalized},
        ).lastrowid
        self._history("company", company_id, values, ref)
        self.created_here[("company", normalized)] = ref
        return None

    def people_csv(self, row: dict, ref: str) -> str | None:
        status = _choice("status", row["status"], domain.CONTACT_STATUSES, DEFAULT_PERSON_STATUS)
        last_contact_on = _iso_date("last_contact_on", row["last_contact_on"])
        company = row["company"]
        company_id = None if company is None else self._find_company(company)
        key = (db.normalize_name(row["name"]), company_id)
        # A company still missing is created below, so nobody can be a duplicate there.
        if (company is None or company_id is not None) and key in self.people:
            return self._duplicate(("person", key), f"person '{row['name']}'")
        company_id = self._company_id(company, ref)
        key = (key[0], company_id)
        values = {
            "name": row["name"],
            "company": company,
            "role_title": row["role_title"],
            "relationship": row["relationship"],
            "channel": row["channel"],
            "status": status,
            "next_step": row["next_step"],
            "last_contact_on": last_contact_on,
        }
        person_id = self.connection.execute(
            "INSERT INTO contact (name, company_id, role_title, relationship, channel, status,"
            " next_step, last_contact_on) VALUES (:name, :company_id, :role_title,"
            " :relationship, :channel, :status, :next_step, :last_contact_on)",
            {**values, "company_id": company_id},
        ).lastrowid
        self._history("contact", person_id, values, ref)
        self.people[key] = person_id
        self.created_here[("person", key)] = ref
        return None

    def jobs_csv(self, row: dict, ref: str) -> str | None:
        track = _choice("track", row["track"], domain.JOB_TRACKS)
        score = _score(row["score"])
        created_at = _timestamp("created_at", row["created_at"])
        status = _choice("status", row["status"], domain.JOB_STATUSES, DEFAULT_JOB_STATUS)
        applied_on = _iso_date("applied_on", row["applied_on"])
        last_contact_on = _iso_date("last_contact_on", row["last_contact_on"])
        normalized = normalize_url(row["url"])
        if normalized in self.jobs:
            return self._duplicate(("job", normalized), f"job URL '{row['url']}'")
        company_id = self._company_id(row["company"], ref)
        job_values = {
            "company": row["company"],
            "title": row["title"],
            "url": row["url"],
            "track": track,
            "score": score,
        }
        job = (company_id, row["title"], row["url"], track, score)
        if created_at is None:  # the schema default: the moment of the import
            sql = "INSERT INTO job (company_id, title, url, track, score) VALUES (?, ?, ?, ?, ?)"
        else:
            job += (created_at,)
            sql = (
                "INSERT INTO job (company_id, title, url, track, score, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)"
            )
        job_id = self.connection.execute(sql, job).lastrowid
        application = {
            "status": status,
            "applied_on": applied_on,
            "last_contact_on": last_contact_on,
            "next_step": row["next_step"],
            "resume_track": row["resume_track"],
            "salary_ask": row["salary_ask"],
            "contract_type": row["contract_type"],
        }
        application_id = self.connection.execute(
            "INSERT INTO application (job_id, status, applied_on, last_contact_on, next_step,"
            " resume_track, salary_ask, contract_type) VALUES (:job_id, :status, :applied_on,"
            " :last_contact_on, :next_step, :resume_track, :salary_ask, :contract_type)",
            {**application, "job_id": job_id},
        ).lastrowid
        self._history("job", job_id, job_values, ref)
        self._history("application", application_id, application, ref)
        self.jobs[normalized] = job_id
        self.created_here[("job", normalized)] = ref
        return None

    def interactions(self, row: dict, ref: str) -> str | None:
        on = _iso_date("date", row["date"])
        source_type = _choice("source_type", row["source_type"], domain.SOURCE_TYPES, IMPORT_SOURCE)
        person_id = self._person_id(row["person"], row["person_company"])
        key = ("interaction", person_id, on, row["summary"])
        if self.connection.execute(
            "SELECT 1 FROM interaction WHERE contact_id = ? AND date = ? AND summary = ?",
            key[1:],
        ).fetchone():
            return self._duplicate(key, f"interaction of '{row['person']}' on {on}")
        # Interactions are an append-only log: their own row is the trace (see history.py).
        self.connection.execute(
            "INSERT INTO interaction (contact_id, date, summary, channel, source_type)"
            " VALUES (?, ?, ?, ?, ?)",
            (person_id, on, row["summary"], row["channel"], source_type),
        )
        self.created_here[key] = ref
        return None

    def stages(self, row: dict, ref: str) -> str | None:
        kind = _choice("kind", row["kind"], domain.STAGE_KINDS)
        on = _iso_date("date", row["date"])
        result = _choice("result", row["result"], domain.STAGE_RESULTS, domain.DEFAULT_STAGE_RESULT)
        job_id, application_id = self._job_application(row["job_url"])
        key = ("stage", application_id, kind, on)
        if self.connection.execute(
            "SELECT 1 FROM application_stage WHERE application_id = ? AND kind = ? AND date = ?",
            key[1:],
        ).fetchone():
            return self._duplicate(key, f"{kind} stage of job {job_id} on {on}")
        stage = {
            "application_id": application_id,
            "kind": kind,
            "date": on,
            "result": result,
            "feedback": row["feedback"],
        }
        stage_id = self.connection.execute(
            "INSERT INTO application_stage (application_id, kind, date, result, feedback)"
            " VALUES (:application_id, :kind, :date, :result, :feedback)",
            stage,
        ).lastrowid
        self._history("application_stage", stage_id, stage, ref)
        self.created_here[key] = ref
        return None

    def links(self, row: dict, ref: str) -> str | None:
        role = _choice("role", row["role"], domain.PERSON_ROLES)
        confirmed = _confirmed(row["confirmed"])
        job_id, application_id = self._job_application(row["job_url"])
        person_id = self._person_id(row["person"], row["person_company"])
        key = ("link", application_id, person_id, role)
        if self.connection.execute(
            "SELECT 1 FROM application_person"
            " WHERE application_id = ? AND contact_id = ? AND role = ?",
            key[1:],
        ).fetchone():
            return self._duplicate(key, f"link of '{row['person']}' to job {job_id} as {role}")
        self.connection.execute(
            "INSERT INTO application_person (application_id, contact_id, role, confirmed)"
            " VALUES (?, ?, ?, ?)",
            (application_id, person_id, role, int(confirmed)),
        )
        line = history.change(
            "application_person",
            application_id,
            "link",
            None,
            jobs.link_value(person_id, role, confirmed),
        )
        if self.record_history:
            history.record_lines(
                self.connection, [line], application_id, self.changed_on, IMPORT_SOURCE, ref
            )
        self.created_here[key] = ref
        return None


HANDLERS = {
    "companies.csv": _Importer.companies,
    "people.csv": _Importer.people_csv,
    "jobs.csv": _Importer.jobs_csv,
    "interactions.csv": _Importer.interactions,
    "stages.csv": _Importer.stages,
    "links.csv": _Importer.links,
}


def import_folder(
    connection: sqlite3.Connection,
    folder: Path,
    changed_on: date | None,
    apply: bool = False,
    record_history: bool = True,
) -> ImportReport:
    """Import the CSV files of `folder` (see the module docstring) and return the report.

    `changed_on` dates the history lines (needed only with `record_history`). Without
    `apply` the transaction is rolled back, so the database is left as it was. A folder
    that does not exist raises FileNotFoundError; a file that cannot be read raises OSError
    or UnicodeDecodeError, and nothing is written. The connection must have no open
    transaction.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")
    report = ImportReport(folder=folder, applied=apply)
    if connection.in_transaction:
        raise RuntimeError("Import needs a connection without an open transaction.")
    try:
        importer = _Importer(connection, changed_on, record_history)
        for name in FILES:
            file_report = report.files.setdefault(name, FileReport())
            path = folder / name
            if not path.is_file():
                continue
            file_report.present = True
            rows, refusal = _read(path, name)
            if refusal:
                file_report.errors.append((1, refusal))
                continue
            for line, row in rows:
                _import_row(importer, name, row, line, file_report)
        report.cited_companies = importer.cited
        if apply:
            connection.commit()
        else:
            connection.rollback()
    except BaseException:
        connection.rollback()
        raise
    return report


def _import_row(importer: _Importer, name: str, row: dict, line: int, report: FileReport):
    if "__extra__" in row:
        report.errors.append((line, "more cells than columns in the header"))
        return
    missing = [column for column in REQUIRED[name] if row[column] is None]
    if missing:
        report.errors.append((line, f"missing required value: {', '.join(missing)}"))
        return
    try:
        duplicate = HANDLERS[name](importer, row, f"{name}:{line}")
    except RowError as failure:
        report.errors.append((line, str(failure)))
        return
    if duplicate:
        report.duplicates.append((line, duplicate))
    else:
        report.new.append(line)


def load_seed(connection: sqlite3.Connection, seed_dir: Path = db.SEED_DIR) -> ImportReport:
    """Import the synthetic demo data (data/seed/) through the importer and write it.

    The demo data is a starting state, not a change the user made, so it gets no history
    lines (as the v0.1.0 seed). Meant for a new database; a second load finds only
    duplicates. A seed row with an error raises ValueError and nothing is written.
    """
    report = import_folder(connection, seed_dir, None, record_history=False)
    if report.error_count:
        raise ValueError("The demo data has errors:\n" + report.to_text())
    return import_folder(connection, seed_dir, None, apply=True, record_history=False)


def _text(value) -> str:
    return "" if value is None else str(value)


EXPORT_QUERIES = {
    "companies.csv": "SELECT name, sector, priority, job_platform, notes FROM company ORDER BY id",
    "people.csv": """
        SELECT contact.name, company.name, contact.role_title, contact.relationship,
            contact.channel, contact.status, contact.next_step, contact.last_contact_on
        FROM contact LEFT JOIN company ON company.id = contact.company_id ORDER BY contact.id
    """,
    "jobs.csv": """
        SELECT job.url, company.name, job.title, job.track, job.score, job.created_at,
            application.status, application.applied_on, application.last_contact_on,
            application.next_step, application.resume_track, application.salary_ask,
            application.contract_type
        FROM job JOIN application ON application.job_id = job.id
        JOIN company ON company.id = job.company_id ORDER BY job.id
    """,
    "interactions.csv": """
        SELECT contact.name, company.name, interaction.date, interaction.summary,
            interaction.channel, interaction.source_type
        FROM interaction JOIN contact ON contact.id = interaction.contact_id
        LEFT JOIN company ON company.id = contact.company_id ORDER BY interaction.id
    """,
    "stages.csv": """
        SELECT job.url, application_stage.kind, application_stage.date,
            application_stage.result, application_stage.feedback
        FROM application_stage
        JOIN application ON application.id = application_stage.application_id
        JOIN job ON job.id = application.job_id ORDER BY application_stage.id
    """,
    "links.csv": """
        SELECT job.url, contact.name, company.name, application_person.role,
            CASE WHEN application_person.confirmed THEN 'true' ELSE 'false' END
        FROM application_person
        JOIN application ON application.id = application_person.application_id
        JOIN job ON job.id = application.job_id
        JOIN contact ON contact.id = application_person.contact_id
        LEFT JOIN company ON company.id = contact.company_id
        ORDER BY application.id, contact.id, application_person.role
    """,
}


def export_folder(connection: sqlite3.Connection, folder: Path) -> dict[str, int]:
    """Write the six CSV files into `folder` (created when missing) and return the number
    of rows of each one.

    Refuses (FileExistsError, before writing anything) when any of the six files already
    exists in the folder: an export never overwrites a file.
    """
    folder = Path(folder)
    existing = [name for name in FILES if (folder / name).exists()]
    if existing:
        raise FileExistsError(
            f"Refused: {folder} already has {', '.join(existing)}. Export into an empty or "
            "new folder; nothing was written."
        )
    folder.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name in FILES:
        rows = connection.execute(EXPORT_QUERIES[name]).fetchall()
        with (folder / name).open("x", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(COLUMNS[name])
            writer.writerows([_text(value) for value in row] for row in rows)
        counts[name] = len(rows)
    return counts
