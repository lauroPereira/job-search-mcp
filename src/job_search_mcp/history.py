"""The single place that writes changes of any entity together with their history lines."""

import sqlite3
from datetime import date

from job_search_mcp import domain

# The only tables and columns record_changes may write: both go into the UPDATE text.
UPDATABLE_FIELDS = {
    "application": ("status", "next_step", "applied_on", "last_contact_on"),
    "contact": ("status", "next_step", "last_contact_on"),
}


def split_source(source: str) -> tuple[str, str | None]:
    """Turn a source given by the user into (source_type, source_ref).

    A known type of origin is used as it is, without reference; any other text becomes
    the type 'user', with the text kept as the reference.
    """
    source = source.strip()
    if source in domain.SOURCE_TYPES:
        return source, None
    return domain.USER_SOURCE, source


def record_changes(
    connection: sqlite3.Connection,
    entity: str,
    record_id: int,
    current: dict,
    changes: dict,
    changed_on: date,
    source_type: str,
    source_ref: str | None = None,
) -> list[dict]:
    """Write the fields that really change and one history line for each of them.

    `current` holds the stored values of the record and `changes` the new ones. When at
    least one field changes, the record is updated once and its `version` goes up by one.
    Does not commit: the caller owns the transaction. Returns the history lines created.
    An unknown entity or field, or an unknown source type, raises ValueError before
    anything is written.
    """
    allowed = UPDATABLE_FIELDS.get(entity)
    if allowed is None:
        raise ValueError(f"Entity not allowed in an update: {entity}.")
    unknown = [field for field in changes if field not in allowed]
    if unknown:
        raise ValueError(f"Fields not allowed in a {entity} update: {', '.join(unknown)}.")
    if source_type not in domain.SOURCE_TYPES:
        raise ValueError(f"Unknown source type: {source_type}.")
    changed = {field: value for field, value in changes.items() if value != current[field]}
    if not changed:
        return []
    assignments = ", ".join(f"{field} = ?" for field in changed)
    connection.execute(
        f"UPDATE {entity} SET {assignments}, version = version + 1 WHERE id = ?",
        (*changed.values(), record_id),
    )
    lines = []
    for field, new_value in changed.items():
        line = {
            "entity": entity,
            "record_id": record_id,
            "field": field,
            "old_value": current[field],
            "new_value": new_value,
            "date": changed_on.isoformat(),
            "source_type": source_type,
            "source_ref": source_ref,
        }
        connection.execute(
            "INSERT INTO history (entity, record_id, field, old_value, new_value, date,"
            " source_type, source_ref) VALUES (:entity, :record_id, :field, :old_value,"
            " :new_value, :date, :source_type, :source_ref)",
            line,
        )
        lines.append(line)
    return lines
