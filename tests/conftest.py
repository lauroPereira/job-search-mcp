from datetime import date

import pytest

from job_search_mcp import db


@pytest.fixture
def connection(tmp_path):
    """Temporary database with the schema created and the synthetic seed loaded."""
    conn = db.connect(tmp_path / "job_search_test.db")
    db.create_schema(conn)
    db.load_seed(conn)
    yield conn
    conn.close()


@pytest.fixture
def reference_date():
    """Fixed reference date the seed dates were designed around."""
    return date(2026, 3, 16)
