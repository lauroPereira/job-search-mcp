import json
from datetime import date

from job_search_mcp import domain, jobs, summary


def ids(items):
    return [item["id"] for item in items]


def test_pending_followups_lists_overdue_and_due_soon_from_the_seed(connection, reference_date):
    result = summary.pending_followups(connection, reference_date)
    assert result["reference_date"] == "2026-03-16"
    assert result["days_ahead"] == 2
    assert [(job["id"], job["follow_up"], job["state"]) for job in result["jobs"]] == [
        (5, "2026-03-11", "overdue"),
        (1, "2026-03-16", "overdue"),  # last contact exactly 7 days before the reference date
        (7, "2026-03-17", "due_soon"),
        (2, "2026-03-18", "due_soon"),  # no last contact: counted from applied_on
        (3, "2026-03-18", "due_soon"),  # last contact 5 days before the reference date
    ]
    assert [(c["id"], c["follow_up"], c["state"]) for c in result["contacts"]] == [
        (1, "2026-03-14", "overdue"),
        (4, "2026-03-16", "overdue"),
        (2, "2026-03-17", "due_soon"),
        (7, "2026-03-18", "due_soon"),
    ]
    assert result["jobs"][0]["company"] == "Transportadora Pampa"
    assert result["contacts"][0]["name"] == "Ana Exemplo"
    json.dumps(result)  # serializable: plain dicts and lists, dates as ISO text


def test_pending_followups_are_ordered_from_oldest_to_most_recent(connection, reference_date):
    result = summary.pending_followups(connection, reference_date, days_ahead=10)
    for items in (result["jobs"], result["contacts"]):
        follow_ups = [item["follow_up"] for item in items]
        assert follow_ups == sorted(follow_ups)
        assert len(follow_ups) > 2


def test_closed_and_not_started_jobs_and_contacts_are_left_out(connection):
    # Far in the future every follow-up is overdue, so only the status can leave an item out.
    result = summary.pending_followups(connection, date(2027, 1, 1))
    assert sorted(ids(result["jobs"])) == [1, 2, 3, 4, 5, 6, 7]
    assert sorted(ids(result["contacts"])) == [1, 2, 3, 4, 7]
    excluded = domain.JOB_CLOSED_STATUSES | domain.JOB_NO_FOLLOW_UP_STATUSES
    assert all(job["status"] not in excluded for job in result["jobs"])
    assert all(job["state"] == "overdue" for job in result["jobs"])
    # Jobs 12, 13 and 14 are closed and do have a last contact date in the seed.
    assert jobs.get_job(connection, 13)["last_contact_on"] == "2026-02-25"


def test_job_that_gets_closed_leaves_the_pending_followups(connection, reference_date):
    assert 5 in ids(summary.pending_followups(connection, reference_date)["jobs"])
    jobs.update_job(connection, 5, "usuário", reference_date, status="rejected")
    assert 5 not in ids(summary.pending_followups(connection, reference_date)["jobs"])


def test_pending_followups_respects_days_ahead(connection, reference_date):
    none_ahead = summary.pending_followups(connection, reference_date, days_ahead=0)
    assert ids(none_ahead["jobs"]) == [5, 1]
    assert ids(none_ahead["contacts"]) == [1, 4]
    wider = summary.pending_followups(connection, reference_date, days_ahead=4)
    assert ids(wider["jobs"]) == [5, 1, 7, 2, 3, 4]  # job 4 follows up on 2026-03-20
    assert ids(wider["contacts"]) == [1, 4, 2, 7, 3]


def test_pending_followups_accepts_iso_text_and_rejects_invalid_date(connection, reference_date):
    assert summary.pending_followups(connection, "2026-03-16") == summary.pending_followups(
        connection, reference_date
    )
    assert summary.pending_followups(connection, "hoje")["error"] == "invalid_date"
    assert summary.pending_followups(connection, None)["error"] == "invalid_date"


def test_daily_summary_counts_match_the_seed(connection, reference_date):
    result = summary.daily_summary(connection, reference_date)
    assert result["reference_date"] == "2026-03-16"
    assert list(result["jobs_by_status"]) == list(domain.JOB_STATUSES)
    assert result["jobs_by_status"] == {
        "suggested": 1,
        "to_apply": 2,
        "blocked": 1,
        "applied": 2,
        "in_review": 1,
        "hr_interview": 1,
        "tech_interview": 1,
        "manager_interview": 1,
        "offer": 1,
        "hired": 1,
        "rejected": 1,
        "withdrawn": 1,
        "closed": 1,
    }
    assert sum(result["jobs_by_status"].values()) == 15
    assert result["active_contacts"] == 7  # 8 contacts, 1 closed
    assert ids(result["overdue"]["jobs"]) == [5, 1]
    assert ids(result["overdue"]["contacts"]) == [1, 4]
    assert ids(result["due_soon"]["jobs"]) == [7, 2, 3]
    assert ids(result["due_soon"]["contacts"]) == [2, 7]
    assert result["deadline"] is None
    assert result["days_to_deadline"] is None
    json.dumps(result)


def test_daily_summary_overdue_and_due_soon_match_pending_followups(connection, reference_date):
    result = summary.daily_summary(connection, reference_date)
    pending = summary.pending_followups(connection, reference_date)
    for kind in ("jobs", "contacts"):
        assert result["overdue"][kind] + result["due_soon"][kind] == pending[kind]
        assert all(item["state"] == "overdue" for item in result["overdue"][kind])
        assert all(item["state"] == "due_soon" for item in result["due_soon"][kind])


def test_application_queue_is_ordered_by_score_from_highest_to_lowest(connection, reference_date):
    queue = summary.daily_summary(connection, reference_date)["application_queue"]
    assert [(job["id"], job["score"], job["status"]) for job in queue] == [
        (8, 9.5, "to_apply"),
        (9, 7.8, "to_apply"),
        (10, 5.5, "suggested"),
    ]


def test_application_queue_puts_jobs_without_score_last(connection, reference_date):
    url = "https://vagas.example.com/empresa-exemplo/data-engineer"
    added = jobs.add_job(connection, "Empresa Exemplo", "Data Engineer", url)
    scored = jobs.add_job(connection, "Empresa Exemplo", "ML Engineer", f"{url}-ml", score=8.0)
    result = summary.daily_summary(connection, reference_date)
    assert ids(result["application_queue"]) == [8, scored["id"], 9, 10, added["id"]]
    assert result["jobs_by_status"]["suggested"] == 3


def test_daily_summary_with_deadline_returns_days_left(connection, reference_date):
    result = summary.daily_summary(connection, reference_date, deadline=date(2026, 3, 31))
    assert result["deadline"] == "2026-03-31"
    assert result["days_to_deadline"] == 15
    assert summary.daily_summary(connection, reference_date, "2026-03-16")["days_to_deadline"] == 0
    assert summary.daily_summary(connection, reference_date, "2026-03-10")["days_to_deadline"] == -6


def test_daily_summary_rejects_invalid_dates(connection, reference_date):
    assert summary.daily_summary(connection, "16/03/2026")["error"] == "invalid_date"
    result = summary.daily_summary(connection, reference_date, deadline="fim do mês")
    assert result["error"] == "invalid_date"
    assert "deadline" in result["detail"]


def test_summary_does_not_write_to_the_database(connection, reference_date):
    before = connection.total_changes
    summary.pending_followups(connection, reference_date)
    summary.daily_summary(connection, reference_date, deadline="2026-03-31")
    assert connection.total_changes == before
