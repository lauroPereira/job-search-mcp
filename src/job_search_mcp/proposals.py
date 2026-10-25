"""Two-step writes (decision 0006): a write tool proposes, and only changes_confirm writes.

A proposal keeps the tool, its arguments, the preview of the changes and the versions of
the records read. Confirming recalculates the plan with the same function that built the
preview and applies it only when the versions and the preview are still the same; otherwise
the proposal is stale. Proposals expire after `proposal_ttl_hours` (local settings) and
expired ones never change anything. No function here reads the clock: `now` comes in.
"""

import json
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

from job_search_mcp import contacts, domain, jobs
from job_search_mcp.config import DEFAULT_SETTINGS, Settings

# The write operations that go through a proposal: tool name -> planning function.
PLANNERS = {
    "add_job": jobs.plan_add_job,
    "update_job": jobs.plan_update_job,
    "log_interaction": contacts.plan_log_interaction,
}
PENDING = "pending"
# Timestamps in UTC, in the format of the created_at columns, so text order is time order.
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _timestamp(moment: datetime) -> str:
    """UTC text of a moment; a naive datetime is taken as UTC."""
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC)
    return moment.strftime(TIMESTAMP_FORMAT)


def _canonical(value) -> str:
    """JSON text used both to store and to compare previews, versions and arguments."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _plan(connection: sqlite3.Connection, tool: str, arguments: dict, settings: Settings):
    return PLANNERS[tool](connection, **arguments, settings=settings)


def create(
    connection: sqlite3.Connection,
    tool: str,
    arguments: dict,
    now: datetime,
    settings: Settings | None = None,
) -> dict:
    """Validate and plan a write without applying it, and store it as a pending proposal.

    `arguments` are the keyword arguments of the planning function of `tool` (see
    PLANNERS), as JSON values. Returns {"proposal": {"id", "tool", "changes",
    "expires_at"}}, or the structured error of the operation, in which case no proposal
    is stored. Only the proposal table is written.
    """
    settings = settings or DEFAULT_SETTINGS
    plan = _plan(connection, tool, arguments, settings)
    if domain.is_error(plan):
        return plan
    proposal_id = secrets.token_urlsafe(16)
    expires_at = _timestamp(now + timedelta(hours=settings.proposal_ttl_hours))
    with connection:
        connection.execute(
            "INSERT INTO proposal (id, tool, arguments, preview, base_versions, status,"
            " created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                proposal_id,
                tool,
                _canonical(arguments),
                _canonical(plan.changes),
                _canonical(plan.base_versions),
                PENDING,
                _timestamp(now),
                expires_at,
            ),
        )
    return {
        "proposal": {
            "id": proposal_id,
            "tool": tool,
            "changes": json.loads(_canonical(plan.changes)),
            "expires_at": expires_at,
        }
    }


def _set_status(connection: sqlite3.Connection, proposal_id: str, status: str) -> None:
    connection.execute("UPDATE proposal SET status = ? WHERE id = ?", (status, proposal_id))


def _expire(connection: sqlite3.Connection, now: datetime) -> None:
    connection.execute(
        "UPDATE proposal SET status = 'expired' WHERE status = ? AND expires_at <= ?",
        (PENDING, _timestamp(now)),
    )


def _pending(connection: sqlite3.Connection, proposal_id: str, now: datetime):
    """The pending proposal with this id, or the structured error that explains why not.

    Marks the proposals that are past their expiry as expired. Runs inside the caller's
    transaction.
    """
    _expire(connection, now)
    row = connection.execute("SELECT * FROM proposal WHERE id = ?", (proposal_id,)).fetchone()
    if row is None:
        return domain.not_found("proposal", proposal_id)
    status = row["status"]
    if status == "expired":
        return domain.error(
            "expired_proposal",
            f"Proposal {proposal_id} expired at {row['expires_at']} (UTC) and changed "
            "nothing. Make the change again to get a new proposal.",
        )
    if status == "stale":
        return _stale(proposal_id)
    if status != PENDING:
        return domain.error(
            "not_found",
            f"No pending proposal with id {proposal_id}: it was already {status}.",
            status=status,
        )
    return row


def _stale(proposal_id: str, reason: dict | None = None) -> dict:
    extra = {"reason": reason} if reason else {}
    return domain.error(
        "stale_proposal",
        f"Proposal {proposal_id} is out of date: the records changed since it was made, so "
        "nothing was changed. Make the change again to get a new proposal.",
        **extra,
    )


def confirm(
    connection: sqlite3.Connection,
    proposal_id: str,
    now: datetime,
    settings: Settings | None = None,
) -> dict:
    """Apply a pending proposal in a single transaction and mark it applied.

    The plan is recalculated under the write lock with the stored arguments; when a version
    or the preview differs from the stored ones (or the operation now fails, such as a URL
    registered in the meantime), nothing is applied, the proposal is marked stale and the
    result is the error 'stale_proposal'. An expired proposal gives 'expired_proposal', an
    unknown or already applied or discarded one 'not_found'. On success, returns the
    result the tool returned in v0.1.0.
    """
    settings = settings or DEFAULT_SETTINGS
    connection.execute("BEGIN IMMEDIATE")
    with connection:
        proposal = _pending(connection, proposal_id, now)
        if domain.is_error(proposal):
            return proposal
        plan = _plan(connection, proposal["tool"], json.loads(proposal["arguments"]), settings)
        if domain.is_error(plan):
            _set_status(connection, proposal_id, "stale")
            return _stale(proposal_id, plan)
        if (
            _canonical(plan.changes) != proposal["preview"]
            or _canonical(plan.base_versions) != proposal["base_versions"]
        ):
            _set_status(connection, proposal_id, "stale")
            return _stale(proposal_id)
        result = plan.apply()
        _set_status(connection, proposal_id, "applied")
    return result


def discard(connection: sqlite3.Connection, proposal_id: str, now: datetime) -> dict:
    """Mark a pending proposal as discarded; nothing else changes.

    Returns {"proposal": {"id", "tool", "status"}}, or the same errors as confirm.
    """
    with connection:
        proposal = _pending(connection, proposal_id, now)
        if domain.is_error(proposal):
            return proposal
        _set_status(connection, proposal_id, "discarded")
    return {"proposal": {"id": proposal_id, "tool": proposal["tool"], "status": "discarded"}}


def list_pending(connection: sqlite3.Connection, now: datetime) -> list[dict]:
    """The pending proposals, oldest first, after marking the expired ones.

    Each one has id, tool, changes (the preview), created_at and expires_at.
    """
    with connection:
        _expire(connection, now)
    rows = connection.execute(
        "SELECT id, tool, preview, created_at, expires_at FROM proposal WHERE status = ?"
        " ORDER BY created_at, rowid",
        (PENDING,),
    )
    return [
        {
            "id": row["id"],
            "tool": row["tool"],
            "changes": json.loads(row["preview"]),
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
        }
        for row in rows
    ]
