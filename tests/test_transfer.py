"""Import and export of the CSV files (docs/import-format.md)."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from job_search_mcp import contacts, db, jobs, server, transfer

ON = date(2026, 3, 16)
TABLES = (
    "company",
    "job",
    "application",
    "application_stage",
    "contact",
    "application_person",
    "interaction",
    "history",
)


def snapshot(connection):
    """Every row of every table, to compare the database before and after."""
    return {
        table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
        for table in TABLES
    }


def count(connection, table):
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def write_files(folder: Path, files: dict[str, str], encoding: str = "utf-8") -> Path:
    folder.mkdir(exist_ok=True)
    for name, text in files.items():
        (folder / name).write_text(text, encoding=encoding)
    return folder


@pytest.fixture
def empty(tmp_path):
    conn = db.connect(tmp_path / "empty.db")
    db.create_schema(conn)
    yield conn
    conn.close()


EXAMPLE = {
    "companies.csv": "name,sector,priority\nEmpresa Alfa,Varejo,A\nEmpresa Beta,,C\n",
    "people.csv": (
        "name,company,status,last_contact_on\n"
        "Pessoa Um,Empresa Alfa,awaiting_reply,2026-03-10\n"
        "Pessoa Dois,,to_contact,\n"
    ),
    "jobs.csv": (
        "url,company,title,track,score,status,applied_on\n"
        "https://vagas.example.com/alfa/1,Empresa Alfa,Analista,data,8,applied,2026-03-02\n"
        "https://vagas.example.com/gama/2,Empresa Gama,Engenheira,,,,\n"
    ),
    "interactions.csv": (
        "person,person_company,date,summary\nPessoa Um,Empresa Alfa,2026-03-10,Conversa rápida\n"
    ),
    "stages.csv": (
        "job_url,kind,date,result\nhttps://vagas.example.com/alfa/1,hr,2026-03-09,passed\n"
    ),
    "links.csv": (
        "job_url,person,person_company,role,confirmed\n"
        "https://vagas.example.com/alfa/1,Pessoa Um,Empresa Alfa,referrer,true\n"
    ),
}


def test_report_without_apply_writes_nothing(empty, tmp_path):
    folder = write_files(tmp_path / "in", EXAMPLE)
    before = snapshot(empty)
    report = transfer.import_folder(empty, folder, ON)
    assert snapshot(empty) == before
    assert not report.applied
    assert {name: len(file.new) for name, file in report.files.items()} == {
        "companies.csv": 2,
        "people.csv": 2,
        "jobs.csv": 2,
        "interactions.csv": 1,
        "stages.csv": 1,
        "links.csv": 1,
    }
    assert report.error_count == 0
    assert report.cited_companies == ["Empresa Gama"]
    assert "Nothing was written" in report.to_text()


def test_apply_writes_every_file_with_import_history(empty, tmp_path):
    folder = write_files(tmp_path / "in", EXAMPLE)
    report = transfer.import_folder(empty, folder, ON, apply=True)
    assert report.applied and report.error_count == 0
    assert count(empty, "company") == 3
    job = jobs.get_job(empty, 1)
    assert (job["company"], job["status"], job["score"], job["applied_on"]) == (
        "Empresa Alfa",
        "applied",
        8.0,
        "2026-03-02",
    )
    assert job["priority"] == "high"
    assert [(stage["kind"], stage["result"]) for stage in job["stages"]] == [("hr", "passed")]
    assert job["people"] == [{"id": 1, "name": "Pessoa Um", "role": "referrer", "confirmed": True}]
    other = jobs.get_job(empty, 2)
    assert (other["company"], other["status"], other["track"]) == (
        "Empresa Gama",
        "suggested",
        None,
    )
    assert contacts.get_contact(empty, 2)["company"] is None
    assert count(empty, "interaction") == 1
    sources = empty.execute("SELECT DISTINCT source_type, date FROM history").fetchall()
    assert [tuple(row) for row in sources] == [("import", "2026-03-16")]
    refs = {row[0] for row in empty.execute("SELECT source_ref FROM history")}
    assert {"companies.csv:2", "jobs.csv:3", "links.csv:2", "stages.csv:2"} <= refs
    link = empty.execute(
        "SELECT new_value FROM history WHERE entity = 'application_person'"
    ).fetchone()[0]
    assert link == "contact_id=1;role=referrer;confirmed=1"


def test_second_import_finds_only_duplicates(empty, tmp_path):
    folder = write_files(tmp_path / "in", EXAMPLE)
    transfer.import_folder(empty, folder, ON, apply=True)
    before = snapshot(empty)
    report = transfer.import_folder(empty, folder, ON, apply=True)
    assert snapshot(empty) == before
    for name, file in report.files.items():
        assert file.new == [] and file.errors == [], name
        assert len(file.duplicates) == EXAMPLE[name].count("\n") - 1, name
    assert report.cited_companies == []
    assert "already in the database" in report.files["jobs.csv"].duplicates[0][1]


def test_invalid_rows_are_reported_and_do_not_stop_the_others(empty, tmp_path):
    folder = write_files(
        tmp_path / "in",
        {
            "companies.csv": "name,priority\nBoa,A\n,B\nRuim,Z\nOutra,\n",
            "jobs.csv": (
                "url,company,title,score,applied_on,status\n"
                "https://vagas.example.com/1,Boa,Vaga 1,11,,\n"
                "https://vagas.example.com/2,Boa,Vaga 2,,02/03/2026,\n"
                "https://vagas.example.com/3,Boa,Vaga 3,,,hired\n"
                "https://vagas.example.com/4,Boa,Vaga 4,,,pending\n"
                "https://vagas.example.com/5,Boa,Vaga 5,7,2026-03-01,applied,extra\n"
            ),
            "stages.csv": "job_url,kind,date\nhttps://vagas.example.com/9,hr,2026-03-01\n",
            "links.csv": ("job_url,person,role\nhttps://vagas.example.com/3,Ninguém,contact\n"),
        },
    )
    report = transfer.import_folder(empty, folder, ON, apply=True)
    files = report.files
    assert files["companies.csv"].new == [2, 5]
    assert files["companies.csv"].errors == [
        (3, "missing required value: name"),
        (4, "invalid priority 'Z': use one of A, B, C"),
    ]
    assert files["jobs.csv"].new == [4]
    reasons = dict(files["jobs.csv"].errors)
    assert "invalid score '11'" in reasons[2]
    assert "invalid applied_on '02/03/2026'" in reasons[3]
    assert "invalid status 'pending'" in reasons[5]
    assert reasons[6] == "more cells than columns in the header"
    assert files["stages.csv"].errors == [(2, "unknown job URL 'https://vagas.example.com/9'")]
    assert files["links.csv"].errors == [(2, "unknown person 'Ninguém' without company")]
    assert not files["people.csv"].present
    assert count(empty, "job") == 1
    assert count(empty, "company") == 2
    assert "line 4: error: invalid priority 'Z'" in report.to_text()


def test_a_file_with_unknown_or_missing_columns_is_refused_whole(empty, tmp_path):
    folder = write_files(
        tmp_path / "in",
        {"companies.csv": "nome,setor\nBoa,Varejo\n", "people.csv": "name,cargo\nAna,x\n"},
    )
    report = transfer.import_folder(empty, folder, ON, apply=True)
    assert report.files["companies.csv"].errors == [
        (1, "missing required columns: name; unknown columns: nome, setor")
    ]
    assert report.files["people.csv"].errors == [(1, "unknown columns: cargo")]
    assert count(empty, "company") == 0
    assert count(empty, "contact") == 0


def test_duplicates_inside_the_same_file_are_skipped(empty, tmp_path):
    folder = write_files(
        tmp_path / "in",
        {
            "companies.csv": "name\nEmpresa Ácida\n  empresa   acida \n",
            "people.csv": (
                "name,company\nAna Exemplo,Empresa Ácida\nana exemplo,EMPRESA ACIDA\n"
                "Ana Exemplo,\nAna Exemplo,Outra Empresa\n"
            ),
            "jobs.csv": (
                "url,company,title\n"
                "https://vagas.example.com/x/1,Empresa Ácida,Vaga\n"
                "HTTPS://Vagas.Example.com/x/1/#topo,Empresa Ácida,Vaga repetida\n"
            ),
            "stages.csv": (
                "job_url,kind,date\nhttps://vagas.example.com/x/1,hr,2026-03-01\n"
                "https://vagas.example.com/x/1/,hr,2026-03-01\n"
            ),
        },
    )
    report = transfer.import_folder(empty, folder, ON, apply=True)
    files = report.files
    assert (files["companies.csv"].new, files["companies.csv"].duplicates) == (
        [2],
        [(3, "company 'empresa   acida' of companies.csv:2")],
    )
    assert files["people.csv"].new == [2, 4, 5]
    assert files["people.csv"].duplicates == [(3, "person 'ana exemplo' of people.csv:2")]
    assert files["jobs.csv"].new == [2]
    assert files["jobs.csv"].duplicates[0][0] == 3
    assert files["stages.csv"].new == [2]
    assert files["stages.csv"].duplicates[0][0] == 3
    assert count(empty, "company") == 2  # Outra Empresa was created by the person row
    assert report.cited_companies == ["Outra Empresa"]
    assert count(empty, "contact") == 3


def test_files_with_bom_and_blank_cells_are_read(empty, tmp_path):
    folder = write_files(
        tmp_path / "in",
        {"companies.csv": "name,sector\n  Empresa BOM  ,  \n"},
        encoding="utf-8-sig",
    )
    report = transfer.import_folder(empty, folder, ON, apply=True)
    assert report.files["companies.csv"].new == [2]
    row = empty.execute("SELECT name, sector FROM company").fetchone()
    assert tuple(row) == ("Empresa BOM", None)


def test_missing_folder_raises(empty, tmp_path):
    with pytest.raises(FileNotFoundError):
        transfer.import_folder(empty, tmp_path / "nowhere", ON)


def test_export_then_import_into_a_new_database_reproduces_the_data(connection, tmp_path):
    # The seed plus an interaction and history, so every file has rows.
    with connection:
        connection.execute(
            "INSERT INTO interaction (contact_id, date, summary, channel, source_type)"
            " VALUES (1, '2026-03-08', 'Pediu indicação', 'linkedin', 'conversation')"
        )
    counts = transfer.export_folder(connection, tmp_path / "out")
    assert counts == {
        "companies.csv": 16,
        "people.csv": 8,
        "jobs.csv": 15,
        "interactions.csv": 1,
        "stages.csv": 9,
        "links.csv": 8,
    }
    copy = db.connect(tmp_path / "copy.db")
    try:
        db.create_schema(copy)
        report = transfer.import_folder(copy, tmp_path / "out", ON, apply=True)
        assert report.error_count == 0
        assert jobs.list_jobs(copy) == jobs.list_jobs(connection)
        assert contacts.list_contacts(copy) == contacts.list_contacts(connection)
        columns = "name, normalized_name, sector, priority, job_platform, notes"
        query = f"SELECT {columns} FROM company ORDER BY id"
        assert copy.execute(query).fetchall() == connection.execute(query).fetchall()
        query = "SELECT * FROM interaction"
        assert copy.execute(query).fetchall() == connection.execute(query).fetchall()
        # Importing the export into the same database finds only duplicates.
        again = transfer.import_folder(connection, tmp_path / "out", ON)
        assert all(not file.new and not file.errors for file in again.files.values())
    finally:
        copy.close()


def test_export_refuses_a_folder_that_already_has_the_files(connection, tmp_path):
    folder = tmp_path / "out"
    folder.mkdir()
    (folder / "jobs.csv").write_text("keep me", encoding="utf-8")
    with pytest.raises(FileExistsError, match="jobs.csv"):
        transfer.export_folder(connection, folder)
    assert (folder / "jobs.csv").read_text(encoding="utf-8") == "keep me"
    assert sorted(path.name for path in folder.iterdir()) == ["jobs.csv"]


def test_normalize_url():
    assert transfer.normalize_url(" HTTPS://Vagas.Example.com/A/1/#x ") == (
        "https://vagas.example.com/A/1"
    )
    assert transfer.normalize_url("https://x.example.com/a?id=2") == "https://x.example.com/a?id=2"
    assert transfer.normalize_url is db.normalize_url  # the same rule as add_job


def test_a_file_that_is_not_utf8_is_refused_alone(empty, tmp_path):
    folder = write_files(tmp_path / "in", {"people.csv": "name\nPessoa Um\n"})
    (folder / "companies.csv").write_bytes("name\nEmpresa Ação\n".encode("cp1252"))
    report = transfer.import_folder(empty, folder, ON, apply=True)
    assert report.files["companies.csv"].errors == [
        (1, "companies.csv is not UTF-8: save it as CSV UTF-8 and import again")
    ]
    assert report.files["people.csv"].new == [2]
    assert count(empty, "contact") == 1


def test_a_broken_csv_is_refused_alone(empty, tmp_path):
    folder = write_files(
        tmp_path / "in",
        # A cell above the csv module's field size limit makes the reader fail.
        {"companies.csv": "name\n" + "x" * 200_000 + "\n", "people.csv": "name\nPessoa Um\n"},
    )
    report = transfer.import_folder(empty, folder, ON, apply=True)
    [(line, reason)] = report.files["companies.csv"].errors
    assert line == 1
    assert reason.startswith("companies.csv is not a valid CSV file")
    assert "save it as CSV UTF-8" in reason
    assert report.files["people.csv"].new == [2]


def test_semicolon_separator_is_detected_from_the_header(empty, tmp_path):
    folder = write_files(
        tmp_path / "in",
        {
            "companies.csv": "name;sector;notes\nEmpresa Alfa;Varejo;Vírgula, aqui\n",
            "jobs.csv": "url,company,title\nhttps://vagas.example.com/a,Empresa Alfa,Analista\n",
        },
    )
    report = transfer.import_folder(empty, folder, ON, apply=True)
    assert report.error_count == 0
    row = empty.execute("SELECT name, sector, notes FROM company").fetchone()
    assert tuple(row) == ("Empresa Alfa", "Varejo", "Vírgula, aqui")
    assert count(empty, "job") == 1


@pytest.mark.parametrize("url", ["-", "vagas.example.com/x", "ftp://vagas.example.com/x"])
def test_a_job_link_that_is_not_a_full_http_link_is_an_error(empty, tmp_path, url):
    folder = write_files(
        tmp_path / "in",
        {
            "jobs.csv": (
                f"url,company,title\n{url},Empresa,Vaga 1\n{url},Empresa,Vaga 2\n"
                "https://vagas.example.com/ok,Empresa,Vaga 3\n"
            ),
            "stages.csv": f"job_url,kind,date\n{url},hr,2026-03-01\n",
        },
    )
    report = transfer.import_folder(empty, folder, ON, apply=True)
    jobs_report = report.files["jobs.csv"]
    assert jobs_report.new == [4] and jobs_report.duplicates == []
    assert [line for line, _ in jobs_report.errors] == [2, 3]
    assert "use a full link starting with http:// or https://" in jobs_report.errors[0][1]
    assert report.files["stages.csv"].errors[0][1].startswith(f"invalid job_url '{url}'")


def test_header_and_blank_cells_are_tolerated(empty, tmp_path):
    folder = write_files(
        tmp_path / "in",
        {
            "companies.csv": (
                " Name , SECTOR ,,\n"
                "Empresa Alfa,Varejo,,\n"
                ",,,\n"
                "\n"
                "Empresa Beta,,ignorada, ,  \n"  # under a blank header cell, blank extra
                "Empresa Gama,,,,cheia\n"  # a filled cell beyond the header
            ),
        },
    )
    report = transfer.import_folder(empty, folder, ON, apply=True)
    companies = report.files["companies.csv"]
    assert companies.new == [2, 5]
    assert companies.errors == [(6, "more cells than columns in the header")]
    names = [row[0] for row in empty.execute("SELECT name FROM company ORDER BY id")]
    assert names == ["Empresa Alfa", "Empresa Beta"]


def test_a_repeated_column_refuses_the_file(empty, tmp_path):
    folder = write_files(tmp_path / "in", {"companies.csv": "name,Name\nA,B\n"})
    report = transfer.import_folder(empty, folder, ON)
    assert report.files["companies.csv"].errors == [(1, "repeated columns: name")]


def test_lines_are_the_first_line_of_each_record(empty, tmp_path):
    folder = write_files(
        tmp_path / "in",
        {"companies.csv": 'name,notes\nEmpresa Alfa,"linha um\nlinha dois"\nEmpresa Beta,\n,x\n'},
    )
    report = transfer.import_folder(empty, folder, ON, apply=True)
    companies = report.files["companies.csv"]
    assert companies.new == [2, 4]
    assert companies.errors == [(5, "missing required value: name")]
    refs = [row[0] for row in empty.execute("SELECT DISTINCT source_ref FROM history ORDER BY id")]
    assert refs == ["companies.csv:2", "companies.csv:4"]


def test_dates_after_the_import_day_are_errors(empty, tmp_path):
    folder = write_files(
        tmp_path / "in",
        {
            "people.csv": "name,last_contact_on\nPessoa Um,2026-03-17\nPessoa Dois,2026-03-16\n",
            "jobs.csv": (
                "url,company,title,applied_on,created_at\n"
                "https://vagas.example.com/1,Empresa,Vaga,2026-03-17,\n"
                "https://vagas.example.com/2,Empresa,Vaga,,2026-03-17 08:00:00\n"
                "https://vagas.example.com/3,Empresa,Vaga,2026-03-16,2026-03-16 08:00:00\n"
            ),
            "stages.csv": "job_url,kind,date\nhttps://vagas.example.com/3,hr,2026-04-01\n",
            "interactions.csv": "person,date,summary\nPessoa Dois,2026-03-20,Conversa\n",
        },
    )
    report = transfer.import_folder(empty, folder, ON, apply=True)
    assert report.files["people.csv"].errors == [
        (2, "invalid last_contact_on '2026-03-17': it cannot be after today (2026-03-16)")
    ]
    assert [line for line, _ in report.files["jobs.csv"].errors] == [2, 3]
    assert report.files["jobs.csv"].new == [4]
    assert "cannot be after today" in report.files["stages.csv"].errors[0][1]
    assert "cannot be after today" in report.files["interactions.csv"].errors[0][1]


def test_export_writes_utf8_with_bom(connection, tmp_path):
    transfer.export_folder(connection, tmp_path / "out")
    raw = (tmp_path / "out" / "companies.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbfname,")
    assert "Clínica Boreal" in raw.decode("utf-8-sig")


@pytest.fixture
def cli_db(tmp_path, monkeypatch):
    path = tmp_path / "cli.db"
    monkeypatch.setenv(db.DB_ENV_VAR, str(path))
    monkeypatch.setattr(server, "today", lambda: ON)
    return path


def test_import_command_without_apply_prints_the_report_and_writes_nothing(
    cli_db, tmp_path, capsys
):
    folder = write_files(tmp_path / "in", EXAMPLE)
    assert server.main(["import", str(folder)]) == 0
    out = capsys.readouterr().out
    assert "jobs.csv: 2 new, 0 duplicates, 0 with errors" in out
    assert "run again with --apply" in out
    conn = sqlite3.connect(cli_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM job").fetchone()[0] == 0
    finally:
        conn.close()


def test_import_command_with_apply_writes_and_a_second_run_finds_duplicates(
    cli_db, tmp_path, capsys
):
    folder = write_files(tmp_path / "in", EXAMPLE)
    assert server.main(["import", str(folder), "--apply"]) == 0
    assert "Applied" in capsys.readouterr().out
    assert server.main(["import", str(folder), "--apply"]) == 0
    assert "jobs.csv: 0 new, 2 duplicates, 0 with errors" in capsys.readouterr().out
    conn = sqlite3.connect(cli_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM job").fetchone()[0] == 2
    finally:
        conn.close()


def test_import_command_reports_a_missing_folder_without_traceback(cli_db, tmp_path, capsys):
    assert server.main(["import", str(tmp_path / "nowhere")]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Could not import")
    assert not cli_db.exists()  # no database is created for a wrong folder


def test_export_command_writes_the_files_and_refuses_to_overwrite(cli_db, tmp_path, capsys):
    assert server.main(["--seed"]) == 0
    out = tmp_path / "out"
    assert server.main(["export", str(out)]) == 0
    assert "jobs.csv: 15 rows" in capsys.readouterr().out
    assert sorted(path.name for path in out.iterdir()) == sorted(transfer.FILES)
    assert server.main(["export", str(out)]) == 1
    assert "Refused" in capsys.readouterr().err


def test_seed_option_uses_the_importer(cli_db, capsys):
    assert server.main(["--seed"]) == 0
    conn = db.connect(cli_db)
    try:
        report = transfer.import_folder(conn, db.SEED_DIR, ON)
        assert all(not file.new and not file.errors for file in report.files.values())
        assert count(conn, "application_stage") == 9
        assert count(conn, "history") == 0
    finally:
        conn.close()
