"""The single place that writes changes of any entity together with their history lines.

History covers the records that can be changed (the tables with `version`): every field a
write creates or changes gets one line with its origin. Interactions are an append-only
log, so their own row is the trace and they get no history lines.
"""

import sqlite3
from datetime import date

from job_search_mcp import domain

# The only tables and fields record_changes may write: both go into the UPDATE text. A field
# is its column, except the reference fields (REFERENCE_FIELDS): contact.company is written
# to the column company_id.
UPDATABLE_FIELDS = {
    "application": (
        "status",
        "next_step",
        "applied_on",
        "last_contact_on",
        "resume_track",
        "salary_ask",
        "contract_type",
    ),
    "contact": (
        "status",
        "next_step",
        "last_contact_on",
        "name",
        "company",
        "role_title",
        "relationship",
        "channel",
    ),
    "company": ("name", "sector", "priority", "job_platform", "notes"),
}
# Fields shown and recorded by name whose stored column is a reference to another record:
# (entity, field) -> column. The id to store comes in the `references` of record_changes.
REFERENCE_FIELDS = {("contact", "company"): "company_id"}
# The tables whose `version` may be read: they go into the SELECT text.
VERSIONED_TABLES = ("company", "job", "application", "contact")


def split_source(source: str) -> tuple[str, str | None]:
    """Turn a source given by the user into (source_type, source_ref).

    A known type of origin is used as it is, without reference; any other text becomes
    the type 'user', with the text kept as the reference.
    """
    source = source.strip()
    if source in domain.SOURCE_TYPES:
        return source, None
    return domain.USER_SOURCE, source


def change(entity: str, record_id: int | None, field: str, old_value, new_value) -> dict:
    """One line of a preview: a field of a record with its current and proposed value."""
    return {
        "entity": entity,
        "record_id": record_id,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
    }


def creation(entity: str, values: dict) -> list[dict]:
    """Preview of a record still to be created: one line per informed (not None) field."""
    return [
        change(entity, None, field, None, value)
        for field, value in values.items()
        if value is not None
    ]


def diff(entity: str, record_id: int, current: dict, changes: dict) -> list[dict]:
    """Preview of an update: one line per field whose new value differs from the stored one.

    An unknown entity or field raises ValueError.
    """
    allowed = UPDATABLE_FIELDS.get(entity)
    if allowed is None:
        raise ValueError(f"Entity not allowed in an update: {entity}.")
    unknown = [field for field in changes if field not in allowed]
    if unknown:
        raise ValueError(f"Fields not allowed in a {entity} update: {', '.join(unknown)}.")
    return [
        change(entity, record_id, field, current[field], value)
        for field, value in changes.items()
        if value != current[field]
    ]


def read_version(connection: sqlite3.Connection, entity: str, record_id: int) -> int | None:
    """The stored `version` of a record, or None when it does not exist."""
    if entity not in VERSIONED_TABLES:
        raise ValueError(f"Entity without version: {entity}.")
    row = connection.execute(f"SELECT version FROM {entity} WHERE id = ?", (record_id,))
    found = row.fetchone()
    return found[0] if found else None


def _check_source(source_type: str) -> None:
    if source_type not in domain.SOURCE_TYPES:
        raise ValueError(f"Unknown source type: {source_type}.")


def _insert_lines(
    connection: sqlite3.Connection,
    lines: list[dict],
    record_id: int,
    changed_on: date,
    source_type: str,
    source_ref: str | None,
) -> list[dict]:
    written = []
    for line in lines:
        full = {
            **line,
            "record_id": record_id,
            "date": changed_on.isoformat(),
            "source_type": source_type,
            "source_ref": source_ref,
        }
        connection.execute(
            "INSERT INTO history (entity, record_id, field, old_value, new_value, date,"
            " source_type, source_ref) VALUES (:entity, :record_id, :field, :old_value,"
            " :new_value, :date, :source_type, :source_ref)",
            full,
        )
        written.append(full)
    return written


def record_changes(
    connection: sqlite3.Connection,
    entity: str,
    record_id: int,
    current: dict,
    changes: dict,
    changed_on: date,
    source_type: str,
    source_ref: str | None = None,
    references: dict | None = None,
) -> list[dict]:
    """Write the fields that really change and one history line for each of them.

    `current` holds the stored values of the record and `changes` the new ones. When at
    least one field changes, the record is updated once and its `version` goes up by one.
    A reference field (REFERENCE_FIELDS, such as the company of a contact) is compared and
    recorded by name, and its column gets the id given in `references`. Does not commit:
    the caller owns the transaction. Returns the history lines created. An unknown entity
    or field, an unknown source type or a changed reference field without its id raises
    ValueError before anything is written.
    """
    lines = diff(entity, record_id, current, changes)
    _check_source(source_type)
    references = references or {}
    assignments, values = [], []
    for line in lines:
        column = REFERENCE_FIELDS.get((entity, line["field"]))
        if column is None:
            assignments.append(f"{line['field']} = ?")
            values.append(line["new_value"])
        elif line["field"] in references:
            assignments.append(f"{column} = ?")
            values.append(references[line["field"]])
        else:
            raise ValueError(f"Missing the id of the reference field: {line['field']}.")
    if not lines:
        return []
    connection.execute(
        f"UPDATE {entity} SET {', '.join(assignments)}, version = version + 1 WHERE id = ?",
        (*values, record_id),
    )
    return _insert_lines(connection, lines, record_id, changed_on, source_type, source_ref)


def record_lines(
    connection: sqlite3.Connection,
    lines: list[dict],
    record_id: int,
    changed_on: date,
    source_type: str,
    source_ref: str | None = None,
) -> list[dict]:
    """Write preview lines as they are (see change), all for the record `record_id`.

    For records that have no `version` and no column to update, such as the link of a
    person to an application. Does not commit. An unknown source type raises ValueError
    before anything is written.
    """
    _check_source(source_type)
    return _insert_lines(connection, lines, record_id, changed_on, source_type, source_ref)


def record_creation(
    connection: sqlite3.Connection,
    entity: str,
    record_id: int,
    values: dict,
    changed_on: date,
    source_type: str,
    source_ref: str | None = None,
) -> list[dict]:
    """Write one history line for each informed field of a record just created.

    The record itself is inserted by the caller; does not commit. Returns the lines
    created. An unknown source type raises ValueError before anything is written.
    """
    _check_source(source_type)
    lines = creation(entity, values)
    return _insert_lines(connection, lines, record_id, changed_on, source_type, source_ref)
