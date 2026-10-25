import json
from datetime import date

from helpers import write

from job_search_mcp import db, domain, jobs, summary
from job_search_mcp.config import Settings

ADDED_ON = date(2026, 3, 16)


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
    write(
        connection,
        jobs.plan_update_job(connection, 5, "usuário", reference_date, status="rejected"),
    )
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
        "on_hold": 0,
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
    added = write(
        connection,
        jobs.plan_add_job(
            connection, "Empresa Exemplo", "Data Engineer", url, reference_date=ADDED_ON
        ),
    )
    scored = write(
        connection,
        jobs.plan_add_job(
            connection,
            "Empresa Exemplo",
            "ML Engineer",
            f"{url}-ml",
            score=8.0,
            reference_date=ADDED_ON,
        ),
    )
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


def test_application_queue_puts_score_zero_before_jobs_without_score(connection, reference_date):
    # The job without score is added first (lower id): if a missing score counted as zero,
    # the tie would be broken by id and it would come before the job with score 0.
    url = "https://vagas.example.com/empresa-exemplo/fila"
    without_score = write(
        connection,
        jobs.plan_add_job(
            connection, "Empresa Exemplo", "Sem nota", f"{url}-sem-nota", reference_date=ADDED_ON
        ),
    )
    zero = write(
        connection,
        jobs.plan_add_job(
            connection,
            "Empresa Exemplo",
            "Nota zero",
            f"{url}-zero",
            score=0.0,
            reference_date=ADDED_ON,
        ),
    )
    assert without_score["id"] < zero["id"]
    assert without_score["score"] is None
    assert zero["score"] == 0.0
    queue = summary.daily_summary(connection, reference_date)["application_queue"]
    assert ids(queue) == [8, 9, 10, zero["id"], without_score["id"]]
    assert [job["score"] for job in queue] == [9.5, 7.8, 5.5, 0.0, None]


def test_application_queue_breaks_score_ties_by_id(connection, reference_date):
    url = "https://vagas.example.com/empresa-exemplo/empate"
    first = write(
        connection,
        jobs.plan_add_job(
            connection,
            "Empresa Exemplo",
            "Empate A",
            f"{url}-a",
            score=7.8,
            reference_date=ADDED_ON,
        ),
    )
    second = write(
        connection,
        jobs.plan_add_job(
            connection,
            "Empresa Exemplo",
            "Empate B",
            f"{url}-b",
            score=7.8,
            reference_date=ADDED_ON,
        ),
    )
    no_score_a = write(
        connection,
        jobs.plan_add_job(
            connection, "Empresa Exemplo", "Sem nota A", f"{url}-sem-a", reference_date=ADDED_ON
        ),
    )
    no_score_b = write(
        connection,
        jobs.plan_add_job(
            connection, "Empresa Exemplo", "Sem nota B", f"{url}-sem-b", reference_date=ADDED_ON
        ),
    )
    # Seed job 9 has the same score; moving it to suggested mixes statuses in the tie.
    write(
        connection,
        jobs.plan_update_job(connection, 9, "usuário", reference_date, status="suggested"),
    )
    queue = summary.daily_summary(connection, reference_date)["application_queue"]
    assert [(job["id"], job["score"]) for job in queue] == [
        (8, 9.5),
        (9, 7.8),  # three jobs with 7.8: lowest id first, whatever the status
        (first["id"], 7.8),
        (second["id"], 7.8),
        (10, 5.5),
        (no_score_a["id"], None),  # jobs without score also tie: lowest id first
        (no_score_b["id"], None),
    ]


def test_daily_summary_reads_jobs_and_contacts_only_once(connection, reference_date, monkeypatch):
    calls = {"jobs": 0, "contacts": 0}
    original_jobs, original_contacts = summary.list_jobs, summary.list_contacts

    def counting_jobs(*args, **kwargs):
        calls["jobs"] += 1
        return original_jobs(*args, **kwargs)

    def counting_contacts(*args, **kwargs):
        calls["contacts"] += 1
        return original_contacts(*args, **kwargs)

    monkeypatch.setattr(summary, "list_jobs", counting_jobs)
    monkeypatch.setattr(summary, "list_contacts", counting_contacts)
    summary.daily_summary(connection, reference_date)
    assert calls == {"jobs": 1, "contacts": 1}


def test_funnel_metrics_match_the_hand_count_over_the_seed(connection, reference_date):
    result = summary.funnel_metrics(connection, reference_date)
    assert result["reference_date"] == "2026-03-16"
    # Active = every status not closed (on_hold included). Seed jobs 1 to 11 are active;
    # 12 hired, 13 rejected, 14 withdrawn and 15 closed are not.
    assert result["active_statuses"] == [
        "suggested",
        "to_apply",
        "blocked",
        "applied",
        "in_review",
        "hr_interview",
        "tech_interview",
        "manager_interview",
        "offer",
        "on_hold",
    ]
    assert result["active_by_status"] == {
        "suggested": 1,  # 10 Escola Mirante
        "to_apply": 2,  # 8 Financeira Colibri, 9 Mercado Jatobá
        "blocked": 1,  # 11 Hospital Arvoredo
        "applied": 2,  # 1 Banco Aurora, 2 Loja Horizonte
        "in_review": 1,  # 3 Seguradora Vértice
        "hr_interview": 1,  # 4 Clínica Boreal
        "tech_interview": 1,  # 5 Transportadora Pampa
        "manager_interview": 1,  # 6 Editora Farol
        "offer": 1,  # 7 Usina Solaris
        "on_hold": 0,
    }
    assert result["active_total"] == 11
    assert result["in_interview"] == 3  # jobs 4, 5 and 6, in an interview status
    # With applied_on: jobs 1 to 7, 12, 13 and 14 = 10. Reached an interview: 4, 5 and 6
    # (status), 6 and 7 (hr, technical and manager stages) and 13 (hr and technical stages,
    # rejected afterwards) = 5. Job 12 was hired without stages recorded: not counted.
    assert result["interview_rate"] == {"reached_interview": 5, "applied": 10, "rate": 0.5}
    # 2026-03-16 is a Monday: the last week is W12 (16 to 22 March), with no application.
    # W11: job 2 (03-11). W10: jobs 1 (03-02) and 3 (03-05). W09: job 4 (03-01, a Sunday).
    assert result["applications_per_week"] == [
        {"week": "2026-W09", "start": "2026-02-23", "end": "2026-03-01", "applications": 1},
        {"week": "2026-W10", "start": "2026-03-02", "end": "2026-03-08", "applications": 2},
        {"week": "2026-W11", "start": "2026-03-09", "end": "2026-03-15", "applications": 1},
        {"week": "2026-W12", "start": "2026-03-16", "end": "2026-03-22", "applications": 0},
    ]
    # Confirmed referrer only on job 1 (Ana Exemplo); job 11's referrer is not confirmed.
    assert result["active_with_referral"] == 1
    assert result["active_without_referral"] == 10
    # Job follow-up = last contact (or applied_on) + 7 days; contact = last contact + 6.
    # Overdue (on or before 03-16): jobs 5 (03-11) and 1 (03-16); contacts 1 (03-14) and
    # 4 (03-16). Due soon (03-17 or 03-18): jobs 7, 2 and 3; contacts 2 and 7.
    assert result["follow_ups"] == {
        "days_ahead": 2,
        "overdue": {"jobs": 2, "contacts": 2},
        "due_soon": {"jobs": 3, "contacts": 2},
    }
    # Without settings: no deadline and no goals.
    assert result["deadline"] is None
    assert result["days_to_deadline"] is None
    assert result["goals"] == {"applications_per_week": None, "interview_rate": None}
    json.dumps(result)


def test_funnel_metrics_count_more_weeks_including_empty_ones(connection, reference_date):
    weeks = summary.funnel_metrics(connection, reference_date, weeks=8)["applications_per_week"]
    # W05: job 13 (02-01, a Sunday). W06: job 14 (02-05). W07: jobs 7 (02-10) and 6 (02-15).
    # W08: job 5 (02-20). Job 12 (01-10) is older than the eight weeks.
    assert [(week["week"], week["applications"]) for week in weeks] == [
        ("2026-W05", 1),
        ("2026-W06", 1),
        ("2026-W07", 2),
        ("2026-W08", 1),
        ("2026-W09", 1),
        ("2026-W10", 2),
        ("2026-W11", 1),
        ("2026-W12", 0),
    ]
    one = summary.funnel_metrics(connection, date(2026, 3, 15), weeks=1)["applications_per_week"]
    assert one == [  # a Sunday: its week started on Monday 03-09
        {"week": "2026-W11", "start": "2026-03-09", "end": "2026-03-15", "applications": 1}
    ]
    across_years = summary.funnel_metrics(connection, date(2026, 1, 1), weeks=1)
    assert across_years["applications_per_week"][0]["week"] == "2026-W01"
    assert across_years["applications_per_week"][0]["start"] == "2025-12-29"


def test_funnel_metrics_without_applications_give_a_null_rate(tmp_path, reference_date):
    empty = db.connect(tmp_path / "empty.db")
    try:
        db.create_schema(empty)
        result = summary.funnel_metrics(empty, reference_date)
    finally:
        empty.close()
    assert result["interview_rate"] == {"reached_interview": 0, "applied": 0, "rate": None}
    assert result["active_total"] == 0
    assert set(result["active_by_status"].values()) == {0}
    assert [week["applications"] for week in result["applications_per_week"]] == [0, 0, 0, 0]
    assert result["active_with_referral"] == result["active_without_referral"] == 0


def test_funnel_metrics_bring_the_goals_and_the_deadline_of_the_settings(
    connection, reference_date
):
    settings = Settings(deadline=date(2026, 4, 30), applications_per_week=5, interview_rate=0.3)
    result = summary.funnel_metrics(connection, reference_date, settings=settings)
    assert result["deadline"] == "2026-04-30"
    assert result["days_to_deadline"] == 45  # 15 days left in March + 30 in April
    assert result["goals"] == {"applications_per_week": 5, "interview_rate": 0.3}
    past = summary.funnel_metrics(connection, date(2026, 5, 2), settings=settings)
    assert past["days_to_deadline"] == -2


def test_funnel_metrics_count_on_hold_and_a_new_stage(connection, reference_date):
    # Job 2 goes on hold (still active) and job 3 gets an hr stage: it reached an interview.
    write(
        connection,
        jobs.plan_update_job(connection, 2, "usuário", reference_date, status="on_hold"),
    )
    write(
        connection,
        jobs.plan_add_stage(
            connection, 3, "hr", reference_date, source="user", reference_date=reference_date
        ),
    )
    result = summary.funnel_metrics(connection, reference_date)
    assert result["active_by_status"]["on_hold"] == 1
    assert result["active_by_status"]["applied"] == 1
    assert result["active_total"] == 11
    assert result["interview_rate"] == {"reached_interview": 6, "applied": 10, "rate": 0.6}


def test_funnel_metrics_reject_invalid_date_and_weeks(connection, reference_date):
    assert summary.funnel_metrics(connection, "16/03/2026")["error"] == "invalid_date"
    for weeks in (0, 53, -1, True, 2.0, "4"):
        result = summary.funnel_metrics(connection, reference_date, weeks=weeks)
        assert result["error"] == "invalid_input", weeks
        assert "weeks" in result["detail"]
    assert (
        len(summary.funnel_metrics(connection, reference_date, weeks=52)["applications_per_week"])
        == 52
    )


def test_funnel_metrics_do_not_write_to_the_database(connection, reference_date):
    before = connection.total_changes
    summary.funnel_metrics(connection, reference_date, weeks=52)
    assert connection.total_changes == before
