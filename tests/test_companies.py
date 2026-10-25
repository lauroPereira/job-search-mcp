"""Companies: listing with the suggested priority, overview and planned creation or change."""

from datetime import date

import pytest
from helpers import write

from job_search_mcp import companies, domain

ON = date(2026, 3, 16)


def save(connection, **arguments):
    return companies.plan_save_company(
        connection, **{"source": "conversation", "reference_date": ON, **arguments}
    )


def history_lines(connection, entity, record_id):
    query = (
        "SELECT field, old_value, new_value, source_type FROM history"
        " WHERE entity = ? AND record_id = ? ORDER BY id"
    )
    return [tuple(row) for row in connection.execute(query, (entity, record_id))]


def test_suggested_priority_is_a_with_an_active_person_or_application(connection):
    result = {company["name"]: company for company in companies.list_companies(connection)}
    assert len(result) == 16
    # Banco Aurora: active person and applied job.
    assert result["Banco Aurora"]["suggested_priority"] == "A"
    # Consultoria Tangará: only an active person, no job.
    assert result["Consultoria Tangará"]["suggested_priority"] == "A"
    # Seguradora Vértice: only an active application, no person.
    assert result["Seguradora Vértice"]["suggested_priority"] == "A"
    # Construtora Granito: its person is closed and its job rejected.
    assert result["Construtora Granito"]["suggested_priority"] is None
    # Hired, withdrawn and closed jobs, without people.
    for name in ("Pousada Maré Alta", "Rádio Planalto", "Telecom Alvorada"):
        assert result[name]["suggested_priority"] is None
    assert set(result["Banco Aurora"]) == {
        "id",
        "name",
        "sector",
        "priority",
        "job_platform",
        "notes",
        "suggested_priority",
    }


def test_suggested_priority_follows_the_person_status(connection):
    with connection:
        connection.execute("UPDATE contact SET status = 'closed' WHERE id = 7")
    tangara = companies.get_company(connection, 16)
    assert tangara["suggested_priority"] is None
    with connection:
        connection.execute("UPDATE contact SET status = 'on_hold' WHERE id = 7")
    assert companies.get_company(connection, 16)["suggested_priority"] == "A"


def test_list_companies_filters_by_the_stored_priority(connection):
    assert companies.list_companies(connection, priority="B") == []
    write(connection, save(connection, company_id=3, name="Seguradora Vértice", priority="B"))
    assert [company["id"] for company in companies.list_companies(connection, "B")] == [3]
    error = companies.list_companies(connection, priority="Z")
    assert error["error"] == "invalid_input"
    assert error["valid_priorities"] == ["A", "B", "C"]


def test_company_overview_brings_people_and_active_applications(connection):
    overview = companies.company_overview(connection, 1)
    assert overview["company"]["name"] == "Banco Aurora"
    assert [person["name"] for person in overview["people"]] == ["Ana Exemplo"]
    assert overview["people"][0]["follow_up"] == "2026-03-14"
    assert [(job["id"], job["title"], job["status"]) for job in overview["applications"]] == [
        (1, "Data Engineer", "applied")
    ]
    assert overview["applications"][0]["follow_up"]


def test_company_overview_leaves_closed_applications_out_but_keeps_every_person(connection):
    granito = companies.company_overview(connection, 13)
    assert [person["status"] for person in granito["people"]] == ["closed"]
    assert granito["applications"] == []
    assert companies.company_overview(connection, 99)["error"] == "not_found"


def test_save_company_creates_it_with_history(connection):
    plan = save(connection, name="  Empresa Nova ", sector="Varejo", priority="C")
    assert plan.base_versions == {}
    assert [(c["field"], c["new_value"]) for c in plan.changes] == [
        ("name", "Empresa Nova"),
        ("sector", "Varejo"),
        ("priority", "C"),
    ]
    company = write(connection, plan)["company"]
    assert company["name"] == "Empresa Nova"
    assert company["suggested_priority"] is None
    stored = connection.execute(
        "SELECT normalized_name, version FROM company WHERE id = ?", (company["id"],)
    ).fetchone()
    assert tuple(stored) == ("empresa nova", 1)
    assert history_lines(connection, "company", company["id"]) == [
        ("name", None, "Empresa Nova", "conversation"),
        ("sector", None, "Varejo", "conversation"),
        ("priority", None, "C", "conversation"),
    ]


@pytest.mark.parametrize("name", ["Banco Aurora", "banco  aurora", "BANCO AURÓRA"])
def test_a_duplicate_name_is_refused_with_the_existing_company(connection, name):
    error = save(connection, name=name)
    assert error["error"] == "duplicate_company"
    assert error["company"]["id"] == 1
    renamed = save(connection, company_id=2, name=name)
    assert renamed["error"] == "duplicate_company"


def test_change_touches_only_the_informed_fields_and_bumps_the_version(connection):
    write(connection, save(connection, company_id=1, name="Banco Aurora", sector="Finanças"))
    plan = save(connection, company_id=1, priority="A")
    assert plan.base_versions == {"company:1": 2}
    assert plan.changes == [
        {
            "entity": "company",
            "record_id": 1,
            "field": "priority",
            "old_value": None,
            "new_value": "A",
        }
    ]
    company = write(connection, plan)["company"]
    assert (company["sector"], company["priority"]) == ("Finanças", "A")
    assert companies.get_company(connection, 1)["name"] == "Banco Aurora"
    version = connection.execute("SELECT version FROM company WHERE id = 1").fetchone()[0]
    assert version == 3


def test_rename_updates_the_normalized_name(connection):
    write(connection, save(connection, company_id=1, name="Banco Aurora S.A."))
    stored = connection.execute("SELECT name, normalized_name FROM company WHERE id = 1")
    assert tuple(stored.fetchone()) == ("Banco Aurora S.A.", "banco aurora s.a.")
    # Its own name, written another way, is not a duplicate.
    assert not domain.is_error(save(connection, company_id=1, name="banco aurora s.a."))
    # The old name is free again.
    assert not domain.is_error(save(connection, name="Banco Aurora"))


@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ({"name": " "}, "invalid_input"),
        ({"sector": "Varejo"}, "invalid_input"),
        ({"name": "Empresa X", "priority": "D"}, "invalid_input"),
        ({"name": "Empresa X", "source": " "}, "invalid_input"),
        ({"name": "Empresa X", "reference_date": "ontem"}, "invalid_date"),
        ({"name": "Empresa X", "company_id": 99}, "not_found"),
    ],
)
def test_save_company_validation_errors_plan_nothing(connection, arguments, code):
    assert save(connection, **arguments)["error"] == code
