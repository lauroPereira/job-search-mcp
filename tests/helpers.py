"""Shared helpers for the domain tests."""

from job_search_mcp import domain


def write(connection, plan):
    """Apply a plan at once, in its own transaction, as changes_confirm does after checking it.

    A structured error (no plan) is returned as it is.
    """
    if domain.is_error(plan):
        return plan
    with connection:
        return plan.apply()
