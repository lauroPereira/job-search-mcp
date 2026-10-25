from datetime import date, timedelta
from pathlib import Path

import pytest

from job_search_mcp import domain
from job_search_mcp.db import to_date


def test_status_lists_match_the_plan():
    assert len(domain.JOB_STATUSES) == 14
    assert len(domain.CONTACT_STATUSES) == 7
    assert domain.JOB_CLOSED_STATUSES == {"hired", "rejected", "withdrawn", "closed"}
    assert domain.JOB_NO_FOLLOW_UP_STATUSES == {"suggested", "to_apply", "blocked", "on_hold"}
    assert domain.CONTACT_NO_FOLLOW_UP_STATUSES == {"to_contact", "on_hold", "closed"}
    assert domain.JOB_CLOSED_STATUSES | domain.JOB_NO_FOLLOW_UP_STATUSES < set(domain.JOB_STATUSES)
    assert domain.CONTACT_NO_FOLLOW_UP_STATUSES < set(domain.CONTACT_STATUSES)


def test_to_date_converts_iso_text_and_keeps_dates_and_none():
    assert to_date("2026-03-16") == date(2026, 3, 16)
    assert to_date(date(2026, 3, 16)) == date(2026, 3, 16)
    assert to_date(None) is None
    with pytest.raises(ValueError):
        to_date("16/03/2026")


def test_job_follow_up_is_last_contact_plus_seven_days():
    assert domain.job_follow_up("2026-03-02", "2026-03-09") == date(2026, 3, 16)
    assert domain.job_follow_up(date(2026, 3, 2), date(2026, 3, 9)) == date(2026, 3, 16)


def test_job_follow_up_without_contact_uses_application_date():
    assert domain.job_follow_up("2026-03-11", None) == date(2026, 3, 18)


def test_job_follow_up_without_any_date_is_none():
    assert domain.job_follow_up(None, None) is None


@pytest.mark.parametrize(
    "status", sorted(domain.JOB_CLOSED_STATUSES | domain.JOB_NO_FOLLOW_UP_STATUSES)
)
def test_job_in_closed_or_not_started_status_has_no_follow_up(status):
    assert domain.job_follow_up("2026-03-02", "2026-03-09", status) is None


def test_job_in_active_status_has_follow_up():
    assert domain.job_follow_up("2026-03-02", "2026-03-09", "applied") == date(2026, 3, 16)


def test_contact_follow_up_is_last_interaction_plus_six_days():
    assert domain.contact_follow_up("2026-03-08") == date(2026, 3, 14)
    assert domain.contact_follow_up("2026-03-08", "awaiting_reply") == date(2026, 3, 14)
    assert domain.contact_follow_up(None) is None


@pytest.mark.parametrize("status", ["to_contact", "closed"])
def test_contact_in_status_without_follow_up(status):
    assert domain.contact_follow_up("2026-03-08", status) is None


@pytest.mark.parametrize(
    ("days_since_contact", "expected"),
    [
        (10, "overdue"),
        (8, "overdue"),
        (7, "overdue"),
        (6, "due_soon"),
        (5, "due_soon"),
        (4, "on_track"),
        (2, "on_track"),
        (0, "on_track"),
    ],
)
def test_classify_job_by_days_since_last_contact(reference_date, days_since_contact, expected):
    last_contact_on = reference_date - timedelta(days=days_since_contact)
    follow_up = domain.job_follow_up(None, last_contact_on)
    assert domain.classify(follow_up, reference_date) == expected


def test_classify_job_without_last_contact_uses_application_date(reference_date):
    applied_on = reference_date - timedelta(days=5)
    follow_up = domain.job_follow_up(applied_on, None)
    assert follow_up == reference_date + timedelta(days=2)
    assert domain.classify(follow_up, reference_date) == "due_soon"


def test_classify_respects_days_ahead(reference_date):
    follow_up = reference_date + timedelta(days=4)
    assert domain.classify(follow_up, reference_date) == "on_track"
    assert domain.classify(follow_up, reference_date, days_ahead=4) == "due_soon"
    assert domain.classify(follow_up, reference_date, days_ahead=0) == "on_track"
    assert domain.classify(reference_date, reference_date, days_ahead=0) == "overdue"


def test_error_has_code_detail_and_context():
    result = domain.error("duplicate_url", "Already there.", job={"id": 1})
    assert result == {"error": "duplicate_url", "detail": "Already there.", "job": {"id": 1}}
    assert domain.is_error(result)
    assert not domain.is_error({"job": {"id": 1}})
    assert not domain.is_error([])


def test_invalid_status_error_lists_the_valid_statuses():
    result = domain.invalid_status("done", domain.JOB_STATUSES)
    assert result["error"] == "invalid_status"
    assert result["valid_statuses"] == list(domain.JOB_STATUSES)
    for status in domain.JOB_STATUSES:
        assert status in result["detail"]


def test_tracks_and_score_range_match_the_plan():
    assert domain.JOB_TRACKS == ("data", "systems", "product", "ai", "other")
    assert (domain.SCORE_MIN, domain.SCORE_MAX) == (0, 10)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, True),
        (10, True),
        (9.5, True),
        (-0.01, False),
        (10.01, False),
        (float("nan"), False),
        (True, False),
        ("9", False),
        (None, False),
    ],
)
def test_is_valid_score(score, expected):
    assert domain.is_valid_score(score) is expected


def test_invalid_track_and_score_errors_are_invalid_input():
    track = domain.invalid_track("dados")
    assert track["error"] == "invalid_input"
    assert "'dados'" in track["detail"]
    assert track["valid_tracks"] == list(domain.JOB_TRACKS)
    score = domain.invalid_score(11)
    assert score["error"] == "invalid_input"
    assert "'11'" in score["detail"]


def test_domain_modules_do_not_read_the_current_date():
    """No domain module calls the clock: the reference date always comes in as a parameter."""
    source_dir = Path(domain.__file__).parent
    forbidden = ("today(", "now(", "utcnow(", "time.time(", "localtime(", "CURRENT_")
    checked = []
    for path in sorted(source_dir.glob("*.py")):
        # db.py only declares the schema default of created_at; server.py is the edge (task 06).
        if path.name in ("db.py", "server.py"):
            continue
        text = path.read_text(encoding="utf-8")
        for call in forbidden:
            assert call not in text, f"{path.name} reads the current date with {call}"
        checked.append(path.name)
    assert {"domain.py", "jobs.py"} <= set(checked)
