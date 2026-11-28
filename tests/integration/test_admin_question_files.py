"""A subject's question bank as a CSV file over HTTP: the export, the import page and the import.

See specs/012.11-question-bank-csv/spec.md User Stories 1–4, 6 and 7, and
contracts/http-routes.md §3–§5. Every test runs once per engine. The format itself is tested in
`tests/unit/test_question_csv.py`; the service and its lock in
`tests/integration/test_question_bank_files_service.py`; the access of other roles in
`tests/integration/test_access_control.py`.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.main import app
from app.models import AccessLevel, Question
from app.services.question_csv import MAX_FILE_BYTES
from tests import html
from tests.conftest import (
    ClientAs,
    add_competition_question,
    make_competition,
    make_institution,
    make_question,
    make_subject,
    make_teacher,
)
from tests.pdf import pdf_text
from tests.unit.test_question_csv import readme_example

TAB = "/admin/subjects"
OLENA = "olena@example.org"
NOW = datetime(2026, 11, 28, 9, 0, tzinfo=UTC)
LATER = datetime(2100, 1, 1, 9, 0, tzinfo=UTC)
MISSING = 999_999
BOM = b"\xef\xbb\xbf"

HISTORY = (
    ("Хто написав «Кобзар»?", "Тарас Шевченко.", False),
    ('Name a, "b"\nand c', "Line one\nline two", True),
    ("=SUM(A1)", "A formula-like text.", False),
)
"""The bank of History, oldest first; the second is additional."""


@dataclass(frozen=True)
class Scene:
    engine: Engine
    admin: TestClient
    olena: TestClient
    """A teacher with **Can manage competitions**."""
    history: int
    latin: int
    """Deactivated, with no questions."""
    bank: list[int]
    clock: Callable[[timedelta], datetime]


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[timedelta], datetime]:
    now = [NOW]
    monkeypatch.setattr("app.services.competitions.utc_now", lambda: now[0])

    def advance(by: timedelta = timedelta(0)) -> datetime:
        now[0] += by
        return now[0]

    return advance


@pytest.fixture
def scene(
    admin_client: TestClient, client_as: ClientAs, clock: Callable[[timedelta], datetime]
) -> Scene:
    engine, settings = app.state.engine, app.state.settings
    lyceum = make_institution(engine, "Kyiv Lyceum", "Kyiv")
    make_teacher(
        engine, settings, email=OLENA, institutions={lyceum: AccessLevel.READ}, can_manage=True
    )
    history = make_subject(engine, "History")
    bank = [make_question(engine, history, t, a, additional=m) for t, a, m in HISTORY]
    make_question(engine, history, "Gone?", "Deleted.", deleted=True)
    return Scene(
        engine=engine,
        admin=admin_client,
        olena=client_as(OLENA),
        history=history,
        latin=make_subject(engine, "Latin", active=False),
        bank=bank,
        clock=clock,
    )


def stored(engine: Engine) -> list[tuple[object, ...]]:
    """Every question of every subject, deleted ones included, by id."""
    with Session(engine) as session:
        return [
            (q.id, q.subject_id, q.text, q.reference_answer, q.is_additional, q.deleted_at)
            for q in session.exec(select(Question).order_by(col(Question.id)))
        ]


def listed(engine: Engine, subject: int) -> list[tuple[int, str, str, bool]]:
    with Session(engine) as session:
        return [
            (q.id, q.text, q.reference_answer, q.is_additional)
            for q in session.exec(
                select(Question)
                .where(Question.subject_id == subject, col(Question.deleted_at).is_(None))
                .order_by(col(Question.id))
            )
        ]


def export(browser: TestClient, subject: int | str) -> Any:
    return browser.get(f"{TAB}/{subject}/questions/export", follow_redirects=False)


def send(browser: TestClient, subject: int | str, data: bytes, name: str = "bank.csv") -> Any:
    return browser.post(
        f"{TAB}/{subject}/questions/import",
        files={"file": (name, data, "text/csv")},
        follow_redirects=False,
    )


def summary(body: str) -> list[tuple[str, bool]]:
    """`(text, linked)` of every entry of the error summary."""
    (box,) = [e for e in html.parse(body).iter() if "error-summary" in e.classes()]
    return [(li.text(), bool(li.find_all("a"))) for li in box.find_all("li")]


def more_line(body: str) -> str | None:
    found = [e.text() for e in html.parse(body).iter() if "error-summary-more" in e.classes()]
    return found[0] if found else None


def file_input(body: str) -> html.Element:
    (found,) = [e for e in html.parse(body).iter() if e.attrs.get("type") == "file"]
    return found


def uk(browser: TestClient) -> TestClient:
    browser.cookies.set("sc_lang", "uk")
    return browser


def en(browser: TestClient) -> TestClient:
    browser.cookies.set("sc_lang", "en")
    return browser


def csv_lines(response: Any) -> list[str]:
    return response.content.decode("utf-8-sig").split("\r\n")


# ---------------------------------------------------------------------------------------------
# User Story 1: the export
# ---------------------------------------------------------------------------------------------


def test_the_export_is_a_download_of_every_listed_question(scene: Scene) -> None:
    """US1-1–US1-4, FR-013–FR-019."""
    links = [link for link in html.links(scene.admin.get(TAB).text, "main")]
    (link,) = [link for link in links if link.href == f"{TAB}/{scene.history}/questions/export"]
    assert "download" in link.attrs
    response = export(scene.admin, scene.history)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content.startswith(BOM)
    assert response.content.decode("utf-8-sig") == (
        "question,answer,additional\r\n"
        "Хто написав «Кобзар»?,Тарас Шевченко.,0\r\n"
        '"Name a, ""b""\nand c","Line one\nline two",1\r\n'
        "=SUM(A1),A formula-like text.,0\r\n"
    )


def test_the_export_follows_the_ids_not_the_texts(scene: Scene) -> None:
    make_question(scene.engine, scene.history, "Aardvark?", "First letter.")
    assert csv_lines(export(scene.admin, scene.history))[-2].startswith("Aardvark?")


def test_a_deactivated_and_an_empty_subject(scene: Scene) -> None:
    """US1-6: the header only; a deactivated subject exports too."""
    response = export(scene.admin, scene.latin)
    assert response.status_code == 200
    assert response.content == BOM + b"question,answer,additional\r\n"
    make_question(scene.engine, scene.latin, "Salve?", "Hello.")
    assert csv_lines(export(scene.admin, scene.latin))[1] == "Salve?,Hello.,0"


@pytest.mark.parametrize(
    ("language", "name", "expected"),
    [
        (en, "Geography", "Geography 2026-11-28 question bank.csv"),
        (uk, "Історія", "Історія 2026-11-28 банк питань.csv"),
        (en, "A/B: History?", "A_B_ History_ 2026-11-28 question bank.csv"),
    ],
)
def test_the_file_name(
    scene: Scene, language: Callable[[TestClient], TestClient], name: str, expected: str
) -> None:
    """US1-7, FR-016: the subject and the Kyiv date, in the site language."""
    subject = make_subject(scene.engine, name)
    disposition = export(language(scene.admin), subject).headers["content-disposition"]
    assert disposition.startswith('attachment; filename="')
    assert disposition.endswith(f"filename*=UTF-8''{quote(expected, safe='')}")


def test_the_date_is_kyivs(scene: Scene) -> None:
    scene.clock(datetime(2026, 11, 27, 22, 30, tzinfo=UTC) - NOW)
    disposition = export(en(scene.admin), scene.history).headers["content-disposition"]
    assert quote("History 2026-11-28 question bank.csv", safe="") in disposition


def test_the_export_is_read_now_and_changes_nothing(
    scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    """US1-8, FR-010, FR-015: nothing stored or logged; a later question is in the next file."""
    before = stored(scene.engine)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        export(scene.admin, scene.history)
    assert stored(scene.engine) == before
    assert not [r for r in caplog.records if r.name == "uvicorn.error"]
    make_question(scene.engine, scene.history, "New?", "Yes.")
    assert csv_lines(export(scene.admin, scene.history))[-2] == "New?,Yes.,0"


def test_an_unknown_subject_is_not_found(scene: Scene) -> None:
    response = export(scene.admin, MISSING)
    assert response.status_code == 404
    assert html.h1(response.text) == "Subject not found"


# ---------------------------------------------------------------------------------------------
# User Story 2: the import page and the replacement
# ---------------------------------------------------------------------------------------------


def test_the_import_page(scene: Scene) -> None:
    """US2-1, FR-030, FR-031."""
    response = scene.admin.get(f"{TAB}/{scene.history}/questions/import")
    assert response.status_code == 200
    body = response.text
    assert html.h1(body) == "Import questions: History"
    text = html.text(body, "main")
    assert "History has 3 questions now." in text
    assert (
        "Importing deletes all of them and replaces them with the questions of the file. This"
        " cannot be undone. Export the current questions first to keep them."
    ) in text
    (form,) = [
        e
        for e in html.parse(body).find_all("form")
        if "questions/import" in e.attrs.get("action", "")
    ]
    assert form.attrs["method"] == "post"
    assert form.attrs["action"] == f"{TAB}/{scene.history}/questions/import"
    assert form.attrs["enctype"] == "multipart/form-data"
    field = file_input(body)
    assert field.attrs["name"] == "file" and field.attrs["accept"] == ".csv,text/csv"
    assert "value" not in field.attrs
    assert "A CSV file in the format described in the README, at most 2 MB" in text
    (button,) = form.find_all("button")
    assert button.text() == "Replace questions" and button.classes() == ["destructive"]
    assert (TAB, "Cancel") in html.link_pairs(body, "main")
    assert html.error_summary(body) is None


@pytest.mark.parametrize(
    ("count", "sentence"),
    [(0, "Latin has no questions yet."), (1, "Latin has 1 question now.")],
)
def test_the_count_on_a_deactivated_subject(scene: Scene, count: int, sentence: str) -> None:
    if count:
        make_question(scene.engine, scene.latin, "Salve?", "Hello.")
    response = scene.admin.get(f"{TAB}/{scene.latin}/questions/import")
    assert response.status_code == 200
    assert sentence in html.text(response.text, "main")


def test_the_import_page_of_an_unknown_subject(scene: Scene) -> None:
    for response in (
        scene.admin.get(f"{TAB}/{MISSING}/questions/import"),
        send(scene.admin, MISSING, b"question,answer,additional\nQ,A,0\n"),
    ):
        assert response.status_code == 404
        assert html.h1(response.text) == "Subject not found"


NEW = (
    "question,answer,additional\r\n"
    "Перше питання?,Перша відповідь.,0\r\n"
    '"Друге, з комою?","Друга\r\nвідповідь.",1\r\n'
    "Третє питання?,Третя відповідь.,\r\n"
)


def test_a_valid_import_replaces_the_bank(scene: Scene) -> None:
    """US2-2, US2-3, FR-033, FR-041: back to the tab, which shows the new count."""
    other = make_subject(scene.engine, "Physics")
    make_question(scene.engine, other, "Physics?")
    others = [row for row in stored(scene.engine) if row[1] == other]
    response = send(scene.admin, scene.history, BOM + NEW.encode())
    assert response.status_code == 303
    assert response.headers["location"] == TAB
    rows = html.table_rows(scene.admin.get(TAB).text)
    assert {row["Name"]: row["Questions"] for row in rows}["History"] == "3"
    new = listed(scene.engine, scene.history)
    assert [(t, a, m) for _, t, a, m in new] == [
        ("Перше питання?", "Перша відповідь.", False),
        ("Друге, з комою?", "Друга\nвідповідь.", True),
        ("Третє питання?", "Третя відповідь.", False),
    ]
    assert min(q for q, *_ in new) > max(scene.bank)
    assert [row for row in stored(scene.engine) if row[1] == other] == others
    page = scene.olena.get(f"/teacher/questions?subject={scene.history}").text
    assert "Третє питання?" in page and "=SUM(A1)" not in page


def test_an_upcoming_competition_keeps_its_replaced_question(scene: Scene) -> None:
    """US2-6, FR-043: the copy stays, marked deleted from the bank."""
    competition = make_competition(scene.engine, scene.history, starts_at=LATER)
    add_competition_question(scene.engine, competition, scene.bank[0])
    send(scene.admin, scene.history, NEW.encode())
    url = f"/teacher/competitions/{competition}/questions?subject={scene.history}"
    body = scene.olena.get(url).text
    assert "Хто написав «Кобзар»?" in body
    assert "Deleted from the question bank" in body


def test_the_round_trip(scene: Scene) -> None:
    """US2-5: an exported file imported unchanged gives the same bank under new ids."""
    before = listed(scene.engine, scene.history)
    response = send(scene.admin, scene.history, export(scene.admin, scene.history).content)
    assert response.status_code == 303
    after = listed(scene.engine, scene.history)
    assert [row[1:] for row in after] == [row[1:] for row in before]
    assert not {row[0] for row in after} & {row[0] for row in before}


def test_the_study_materials_show_the_new_bank(scene: Scene) -> None:
    """US2-9, FR-046: at the next download, without the additional question."""
    send(scene.admin, scene.history, NEW.encode())
    response = scene.olena.get(f"/teacher/competitions/study-materials?subject={scene.history}")
    assert response.status_code == 200
    text = pdf_text(response.content)
    assert "Перше питання?" in text and "Третє питання?" in text
    assert "Друге, з комою?" not in text and "Кобзар" not in text


# ---------------------------------------------------------------------------------------------
# User Stories 3 and 4: refused files and spreadsheet files, through the page
# ---------------------------------------------------------------------------------------------


def test_a_refused_file_lists_every_error_and_changes_nothing(scene: Scene) -> None:
    """US3-1–US3-4, US3-10, FR-032, FR-034: row errors unlinked, the field empty again."""
    before = stored(scene.engine)
    data = b"question,answer,additional\nok,1,0\n,,yes\nok,2,0\nq,,0\n"
    response = send(scene.admin, scene.history, data)
    assert response.status_code == 400
    body = response.text
    assert html.h1(body) == "Import questions: History"
    assert summary(body) == [
        ("Row 3: Enter the question text.", False),
        ("Row 3: Enter the reference answer.", False),
        ("Row 3: Additional must be 0, 1 or empty.", False),
        ("Row 5: Enter the reference answer.", False),
    ]
    assert "value" not in file_input(body).attrs
    assert "History has 3 questions now." in html.text(body, "main")
    assert stored(scene.engine) == before


def test_a_whole_file_error_is_on_the_field(scene: Scene) -> None:
    before = stored(scene.engine)
    response = send(scene.admin, scene.history, b"question;answer\nQ;A\n")
    assert response.status_code == 400
    message = "The first row must be the header: question, answer, additional."
    assert summary(response.text) == [(message, True)]
    assert html.field_error(response.text, "file") == message
    assert file_input(response.text).attrs.get("aria-invalid") == "true"
    assert stored(scene.engine) == before


def test_twenty_errors_and_how_many_more(scene: Scene) -> None:
    """US3-5."""
    lines = ["question,answer,additional"] + [f"Q{n},A,bad" for n in range(25)]
    response = send(scene.admin, scene.history, "\n".join(lines).encode())
    entries = summary(response.text)
    assert len(entries) == 20
    assert entries[0] == ("Row 2: Additional must be 0, 1 or empty.", False)
    assert more_line(response.text) == "And 5 more errors."


def test_no_file_chosen(scene: Scene) -> None:
    """A browser sends an empty file field as a part with no name and no content."""
    before = stored(scene.engine)
    response = scene.admin.post(
        f"{TAB}/{scene.history}/questions/import",
        files={"file": ("", b"", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert summary(response.text) == [("Choose a CSV file.", True)]
    response = scene.admin.post(f"{TAB}/{scene.history}/questions/import", data={})
    assert summary(response.text) == [("Choose a CSV file.", True)]
    assert stored(scene.engine) == before


@pytest.mark.parametrize("size", [MAX_FILE_BYTES + 1, MAX_FILE_BYTES + 64 * 1024])
def test_a_file_too_large(scene: Scene, size: int) -> None:
    """Just over the limit is read and refused; far over it is drained and never kept."""
    before = stored(scene.engine)
    response = send(scene.admin, scene.history, b"question,answer,additional\n" + b"x" * size)
    assert response.status_code == 400
    assert summary(response.text) == [("The file can be at most 2 MB.", True)]
    assert stored(scene.engine) == before


def test_an_unclosed_quote(scene: Scene) -> None:
    response = send(scene.admin, scene.history, b'question,answer,additional\nok,1,0\n"open,x,1\n')
    assert summary(response.text) == [("A quote opened in row 3 is never closed.", False)]


def test_a_cross_site_import_is_refused(scene: Scene) -> None:
    before = stored(scene.engine)
    response = scene.admin.post(
        f"{TAB}/{scene.history}/questions/import",
        files={"file": ("bank.csv", NEW.encode(), "text/csv")},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403
    assert stored(scene.engine) == before


def test_an_excel_file_with_semicolons_imports(scene: Scene) -> None:
    """US4: semicolons, no byte-order mark, CRLF, an empty `;;` row, spaces around `additional`,
    a quote inside an unquoted field, a header in other case."""
    data = (
        "Question;Answer;Additional\r\n"
        'Хто написав «Іліаду»?;The "Iliad" — Гомер;0\r\n'
        ";;\r\n"
        "=1+1;Two; 1 \r\n"
    ).encode()
    assert send(scene.admin, scene.history, data).status_code == 303
    assert [(t, a, m) for _, t, a, m in listed(scene.engine, scene.history)] == [
        ("Хто написав «Іліаду»?", 'The "Iliad" — Гомер', False),
        ("=1+1", "Two", True),
    ]


def test_a_file_in_ukrainian_shows_ukrainian_errors(scene: Scene) -> None:
    response = send(uk(scene.admin), scene.history, b"question,answer,additional\nQ,,0\n")
    assert summary(response.text) == [("Рядок 2: Введіть еталонну відповідь.", False)]


# ---------------------------------------------------------------------------------------------
# User Story 7: a teacher's change around an import (both engines)
# ---------------------------------------------------------------------------------------------


def test_a_replaced_question_is_gone_for_a_teacher(scene: Scene) -> None:
    """US7-4, FR-049: the edit and the deletion of a replaced question get "Question not found"."""
    send(scene.admin, scene.history, NEW.encode())
    before = stored(scene.engine)
    question = scene.bank[0]
    for path, data in (
        (f"/teacher/questions/{question}/edit", {"text": "Edited?", "reference_answer": "Yes."}),
        (f"/teacher/questions/{question}/delete", {}),
    ):
        response = scene.olena.post(path, data=data, follow_redirects=False)
        assert response.status_code == 404, path
        assert "Question not found" in response.text
    assert stored(scene.engine) == before


def test_a_question_added_after_the_import_is_the_newest(scene: Scene) -> None:
    """FR-049: never beside the imported ones in the file's place, but after them."""
    send(scene.admin, scene.history, NEW.encode())
    response = scene.olena.post(
        "/teacher/questions",
        data={"subject": str(scene.history), "text": "Added later?", "reference_answer": "Yes."},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert [t for _, t, _, _ in listed(scene.engine, scene.history)][-1] == "Added later?"


# ---------------------------------------------------------------------------------------------
# User Story 6: the README's example, through the page
# ---------------------------------------------------------------------------------------------


def test_the_readme_example_imports_through_the_page(scene: Scene) -> None:
    """FR-058: the example file of the README section imports with no error, in order."""
    response = send(scene.admin, scene.history, BOM + readme_example())
    assert response.status_code == 303, response.text
    imported = listed(scene.engine, scene.history)
    assert [m for *_, m in imported].count(True) == 1
    assert imported[0][1] == "Хто написав поему «Кавказ»?"
