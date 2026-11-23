"""Downloading a started competition's questions and a subject's study materials, end to end
through the test client (milestone 12.10).

See specs/012.10-questions-study-materials/spec.md US2, US4–US6 and contracts/http-routes.md
§2–§4. Every case runs on both engines. The clock is fixed at 1 March 2027 09:00 UTC (11:00 in
Kyiv) by patching `app.services.competitions.utc_now`; no test waits except the two that time a
download.

- Olena: a teacher with **Can manage competitions**, linked (Read) only to Kharkiv Gymnasium;
- Taras: a teacher without it, with **Write** access to Odesa College, which has no team in the
  competition;
- the cast teacher (`TEACHER_EMAIL`): no link at all;
- Chemistry: three questions in the bank, the second one additional, and one deleted question;
  "Spring round", In progress since 1 March 2027 09:30 Kyiv time, holds the first three, in order.

The files are read back with `tests/pdf.py`. The study materials kept in memory are watched by
counting the calls of `question_files_pdf.render_study_materials_pdf`, which the cache calls
through its module.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, MetaData, select, text
from sqlmodel import Session

from app.main import app
from app.models import AccessLevel
from app.services import question_files_pdf
from app.services.questions import delete_question, update_question
from app.services.subjects import set_subject_active
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
    add_competition_question,
    make_competition,
    make_institution,
    make_question,
    make_subject,
    make_teacher,
)
from tests.pdf import pdf_page_texts, pdf_text

TAB = "/teacher/competitions"
OLENA = "olena@example.org"
TARAS = "taras@example.org"
NOW = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
STARTED = datetime(2027, 3, 1, 7, 30, tzinfo=UTC)
"""09:30 in Kyiv."""
MISSING = 999_999

QUESTIONS = (
    ("What is a covalent bond?", "Two atoms share a pair of electrons."),
    ("Which element is the hardest to isolate?", "Fluorine, kept back."),
    ("Name the noble gases.", "He, Ne, Ar, Kr, Xe, Rn."),
)
"""The bank of Chemistry, oldest first; the second one is additional."""
DELETED = ("What was phlogiston?", "A discarded theory.")

COMPETITION_NOT_FOUND = (
    "Competition not found",
    "This competition does not exist, or its subject is deactivated.",
)
SUBJECT_NOT_FOUND = (
    "Subject not found",
    "This subject does not exist, or it is deactivated and has no finished competitions.",
)
STUDY_SUBJECT_NOT_FOUND = ("Subject not found", "This subject does not exist or is deactivated.")


@dataclass(frozen=True)
class Scene:
    engine: Engine
    olena: TestClient
    taras: TestClient
    unlinked: TestClient
    olena_id: int
    chemistry: int
    competition: int
    bank: list[int]
    """The three listed questions of Chemistry, oldest first."""
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
def scene(client: TestClient, client_as: ClientAs, clock: Callable[[timedelta], datetime]) -> Scene:
    engine, settings = app.state.engine, app.state.settings
    gymnasium = make_institution(engine, "Kharkiv Gymnasium", "Kharkiv")
    odesa = make_institution(engine, "Odesa College", "Odesa")
    olena_id = make_teacher(
        engine,
        settings,
        email=OLENA,
        institutions={gymnasium: AccessLevel.READ},
        can_manage=True,
    )
    make_teacher(engine, settings, email=TARAS, institutions={odesa: AccessLevel.WRITE})
    chemistry = make_subject(engine, "Chemistry")
    bank = [
        make_question(engine, chemistry, question, answer, additional=n == 1)
        for n, (question, answer) in enumerate(QUESTIONS)
    ]
    make_question(engine, chemistry, *DELETED, deleted=True)
    competition = make_competition(engine, chemistry, starts_at=STARTED)
    for question in bank:
        add_competition_question(engine, competition, question)
    return Scene(
        engine=engine,
        olena=client_as(OLENA),
        taras=client_as(TARAS),
        unlinked=client_as(TEACHER_EMAIL),
        olena_id=olena_id,
        chemistry=chemistry,
        competition=competition,
        bank=bank,
        clock=clock,
    )


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

SNAPSHOT_TABLES = ("subjects", "questions", "competitions", "competition_questions")


def snapshot(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=SNAPSHOT_TABLES)
    with engine.connect() as connection:
        return {
            name: sorted(tuple(row) for row in connection.execute(select(metadata.tables[name])))
            for name in SNAPSHOT_TABLES
        }


def flat(value: str) -> str:
    return " ".join(value.split())


def questions_file(browser: TestClient, competition: int, subject: int | str) -> Any:
    return browser.get(
        f"{TAB}/{competition}/questions-file?subject={subject}", follow_redirects=False
    )


def study_file(browser: TestClient, subject: int | str | None) -> Any:
    query = "" if subject is None else f"?subject={subject}"
    return browser.get(f"{TAB}/study-materials{query}", follow_redirects=False)


def attachment(response: Any, name: str) -> None:
    """A PDF attachment named `name`, with the headers of every download (downloads.py)."""
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="')
    assert disposition.endswith(f"filename*=UTF-8''{quote(name, safe='')}")


def denied(response: Any, label: str = "Teacher") -> None:
    assert response.status_code == 403
    assert f"Your current role, {label}, cannot open this page." in response.text


def not_found(response: Any, page: tuple[str, str]) -> None:
    assert response.status_code == 404
    assert html.h1(response.text) == page[0]
    assert page[1] in response.text


def uk(browser: TestClient) -> TestClient:
    browser.cookies.set("sc_lang", "uk")
    return browser


def en(browser: TestClient) -> TestClient:
    browser.cookies.set("sc_lang", "en")
    return browser


def teachers(s: Scene) -> dict[str, TestClient]:
    return {"olena": s.olena, "taras": s.taras, "unlinked": s.unlinked}


@pytest.fixture
def renders(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, Any]]:
    """Every study materials file made, as `(materials, language)`, in order."""
    made: list[tuple[Any, Any]] = []
    real = question_files_pdf.render_study_materials_pdf

    def counting(materials: Any, language: Any) -> bytes:
        made.append((materials, language))
        return real(materials, language)

    monkeypatch.setattr(question_files_pdf, "render_study_materials_pdf", counting)
    return made


# ---------------------------------------------------------------------------------------------
# User stories 2 and 3: the questions of a started competition
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["in_progress", "finished", "published"])
@pytest.mark.parametrize("who", ["olena", "taras", "unlinked"])
def test_every_teacher_downloads_the_questions_of_a_started_competition(
    scene: Scene, status: str, who: str
) -> None:
    """US2-1, US2-3, US2-4, US3-1–US3-3, FR-006, FR-009, FR-013–FR-015, FR-019: with or without
    the setting, linked or not; every question in its order, the additional one included, with no
    reference answer, bank number or mark; in the current language."""
    competition = scene.competition
    if status != "in_progress":
        competition = make_competition(
            scene.engine,
            scene.chemistry,
            "Spring round",
            starts_at=STARTED,
            stopped=True,
            published=status == "published",
        )
        for question in scene.bank:
            add_competition_question(scene.engine, competition, question)
    browser = teachers(scene)[who]
    response = questions_file(en(browser), competition, scene.chemistry)
    attachment(response, "Spring round 2027-03-01 questions.pdf")
    found = flat(pdf_text(response.content))
    assert found.startswith(
        "Questions of “Spring round” Chemistry Started: 1 March 2027, 09:30 (Kyiv time) 1. "
    )
    positions = [found.index(f"{n}. {q}") for n, (q, _) in enumerate(QUESTIONS, start=1)]
    assert positions == sorted(positions)
    for _, answer in QUESTIONS:
        assert answer not in found
    for absent in (f"Question {scene.bank[0]}", "Additional", DELETED[0]):
        assert absent not in found
    ukrainian = questions_file(uk(browser), competition, scene.chemistry)
    attachment(ukrainian, "Spring round 2027-03-01 питання.pdf")
    assert flat(pdf_text(ukrainian.content)).startswith(
        "Питання змагань «Spring round» Chemistry Початок: 1 березня 2027, 09:30"
    )


@pytest.mark.parametrize("status", ["upcoming", "cancelled"])
def test_the_questions_of_an_upcoming_or_cancelled_competition_are_not_found(
    scene: Scene, status: str
) -> None:
    """US2-2, FR-007."""
    competition = make_competition(
        scene.engine,
        scene.chemistry,
        "Autumn round",
        starts_at=NOW + timedelta(days=7) if status == "upcoming" else STARTED,
        cancelled=status == "cancelled",
    )
    add_competition_question(scene.engine, competition, scene.bank[0])
    for browser in teachers(scene).values():
        not_found(questions_file(browser, competition, scene.chemistry), COMPETITION_NOT_FOUND)


def test_unknown_and_mismatched_addresses_are_not_found(scene: Scene) -> None:
    """US2-7, FR-007, FR-008, FR-042: the subject first, then the competition."""
    physics = make_subject(scene.engine, "Physics")
    for browser in (scene.olena, scene.taras):
        not_found(questions_file(browser, MISSING, scene.chemistry), COMPETITION_NOT_FOUND)
        not_found(questions_file(browser, scene.competition, physics), COMPETITION_NOT_FOUND)
        for subject in (MISSING, "abc", ""):
            not_found(questions_file(browser, scene.competition, subject), SUBJECT_NOT_FOUND)
        response = browser.get(f"{TAB}/{scene.competition}/questions-file")
        not_found(response, SUBJECT_NOT_FOUND)


def test_a_deactivated_subject_gives_the_questions_of_its_finished_competitions(
    scene: Scene,
) -> None:
    """US2-6, FR-008: Finished and Published download; the In progress one is hidden."""
    done = make_competition(scene.engine, scene.chemistry, "Done", starts_at=STARTED, stopped=True)
    out = make_competition(
        scene.engine, scene.chemistry, "Out", starts_at=STARTED, stopped=True, published=True
    )
    for competition in (done, out):
        add_competition_question(scene.engine, competition, scene.bank[0])
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    for competition, name in ((done, "Done"), (out, "Out")):
        attachment(
            questions_file(scene.taras, competition, scene.chemistry),
            f"{name} 2027-03-01 questions.pdf",
        )
    not_found(
        questions_file(scene.taras, scene.competition, scene.chemistry), COMPETITION_NOT_FOUND
    )


def test_a_deactivated_subject_with_no_finished_competition_is_not_found(scene: Scene) -> None:
    """US2-7, FR-008."""
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    not_found(questions_file(scene.taras, scene.competition, scene.chemistry), SUBJECT_NOT_FOUND)


def test_the_questions_file_is_made_at_every_download(scene: Scene) -> None:
    """US2-8, US3-4, US3-6, FR-016, FR-018: a later bank edit changes nothing; a renamed subject
    shows; once cancelled, the next download is not found."""
    first = questions_file(scene.taras, scene.competition, scene.chemistry)
    with Session(scene.engine) as session:
        update_question(
            session, scene.olena_id, scene.bank[0], "Edited?", "Edited.", is_additional=False
        )
    with scene.engine.begin() as connection:
        connection.execute(
            text("UPDATE subjects SET name = 'Chemistry and Biology' WHERE id = :id"),
            {"id": scene.chemistry},
        )
    second = questions_file(scene.taras, scene.competition, scene.chemistry)
    found = flat(pdf_text(second.content))
    assert "Chemistry and Biology" in found
    assert f"1. {QUESTIONS[0][0]}" in found
    assert "Edited?" not in found
    assert first.headers["content-disposition"] == second.headers["content-disposition"]
    with scene.engine.begin() as connection:
        connection.execute(
            text("UPDATE competitions SET cancelled_at = :now WHERE id = :id"),
            {"now": NOW, "id": scene.competition},
        )
    not_found(
        questions_file(scene.taras, scene.competition, scene.chemistry), COMPETITION_NOT_FOUND
    )


def test_a_competition_with_no_questions_gets_its_sentence(scene: Scene) -> None:
    """US3-5, FR-017."""
    empty = make_competition(scene.engine, scene.chemistry, "Empty", starts_at=STARTED)
    response = questions_file(scene.taras, empty, scene.chemistry)
    assert "This competition has no questions." in flat(pdf_text(response.content))


@pytest.mark.parametrize("email", [ADMIN_EMAIL, STUDENT_EMAIL])
def test_administrators_and_students_are_refused_the_downloads(
    scene: Scene, client_as: ClientAs, email: str
) -> None:
    """US2-9, US4-7, FR-011, FR-021: before any id is read, an unknown one included."""
    browser = client_as(email)
    label = "Administrator" if email == ADMIN_EMAIL else "Student"
    for response in (
        questions_file(browser, scene.competition, scene.chemistry),
        questions_file(browser, MISSING, MISSING),
        study_file(browser, scene.chemistry),
        study_file(browser, MISSING),
    ):
        denied(response, label)


def test_a_download_changes_nothing_and_logs_nothing(
    scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-043: no write, and no line of the application's logger, for a file or a 404."""
    before = snapshot(scene.engine)
    with caplog.at_level(logging.DEBUG, logger="uvicorn.error"):
        caplog.clear()
        questions_file(scene.taras, scene.competition, scene.chemistry)
        questions_file(scene.taras, MISSING, scene.chemistry)
        study_file(scene.taras, scene.chemistry)
        study_file(scene.taras, MISSING)
        assert [r for r in caplog.records if r.name == "uvicorn.error"] == []
    assert snapshot(scene.engine) == before


def test_the_menu_offers_download_questions_as_a_download(scene: Scene) -> None:
    """US2-1, US2-5, FR-009: on the In progress row, for every teacher, a link marked as a
    download that carries the subject."""
    for browser in teachers(scene).values():
        body = browser.get(f"{TAB}?subject={scene.chemistry}").text
        (link,) = [a for a in html.parse(body).find_all("a") if a.text() == "Download questions"]
        assert link.attrs["href"] == (
            f"{TAB}/{scene.competition}/questions-file?subject={scene.chemistry}"
        )
        assert "download" in link.attrs


# ---------------------------------------------------------------------------------------------
# User stories 4 and 5: a subject's study materials
# ---------------------------------------------------------------------------------------------


def aside_links(body: str) -> list[html.Element]:
    return [
        a
        for e in html.parse(body).iter()
        if "selectors-aside" in e.classes()
        for a in e.find_all("a")
    ]


@pytest.mark.parametrize("who", ["olena", "taras", "unlinked"])
def test_the_link_is_shown_once_an_active_subject_is_chosen(scene: Scene, who: str) -> None:
    """US4-1, US4-2, FR-020–FR-022: for every teacher, with or without competitions, a plain link
    marked as a download, with no script; not before a subject is chosen."""
    browser = teachers(scene)[who]
    physics = make_subject(scene.engine, "Physics")
    # With two subjects, nothing is chosen until the teacher chooses (milestone 12.1 US1-8).
    assert aside_links(browser.get(TAB).text) == []
    for subject in (scene.chemistry, physics):
        (link,) = aside_links(browser.get(f"{TAB}?subject={subject}").text)
        assert link.text() == "Download study materials"
        assert link.attrs["href"] == f"{TAB}/study-materials?subject={subject}"
        assert "download" in link.attrs
        assert not any(k.startswith("hx-") or k == "onclick" for k in link.attrs)


def test_no_link_for_a_deactivated_subject_or_without_subjects(scene: Scene) -> None:
    """US4-2, US4-3, FR-020."""
    make_competition(scene.engine, scene.chemistry, "Done", starts_at=STARTED, stopped=True)
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    body = scene.taras.get(f"{TAB}?subject={scene.chemistry}").text
    assert "Deactivated subjects" in body
    assert aside_links(body) == []
    assert aside_links(scene.taras.get(TAB).text) == []


@pytest.mark.parametrize("who", ["olena", "taras", "unlinked"])
def test_every_teacher_downloads_the_study_materials(scene: Scene, who: str) -> None:
    """US4-4, US5-1–US5-4, FR-021, FR-026–FR-028, FR-031: the same file for every teacher, a
    teacher with the setting included: the ordinary questions with their answers, oldest first,
    with no additional or deleted question and no bank number."""
    response = study_file(en(teachers(scene)[who]), scene.chemistry)
    attachment(response, "Chemistry 2027-03-01 study materials.pdf")
    found = flat(pdf_text(response.content))
    assert found.startswith("Study materials Chemistry Downloaded: 1 March 2027 1. ")
    assert f"1. {QUESTIONS[0][0]} Answer: {QUESTIONS[0][1]}" in found
    assert f"2. {QUESTIONS[2][0]} Answer: {QUESTIONS[2][1]}" in found
    for absent in (*QUESTIONS[1], *DELETED, "Question ", "Additional", "3."):
        assert absent not in found
    assert response.content == study_file(en(scene.olena), scene.chemistry).content
    ukrainian = study_file(uk(teachers(scene)[who]), scene.chemistry)
    attachment(ukrainian, "Chemistry 2027-03-01 навчальні матеріали.pdf")
    assert flat(pdf_text(ukrainian.content)).startswith(
        "Навчальні матеріали Chemistry Завантажено: 1 березня 2027"
    )


def test_a_subject_with_no_questions_gets_its_sentence(scene: Scene) -> None:
    """US5-5, FR-030: none at all, or only additional or deleted ones."""
    astronomy = make_subject(scene.engine, "Astronomy")
    make_question(scene.engine, astronomy, "Hidden?", additional=True)
    make_question(scene.engine, astronomy, "Gone?", deleted=True)
    response = study_file(scene.taras, astronomy)
    assert "This subject has no questions yet." in flat(pdf_text(response.content))


@pytest.mark.parametrize("subject", ["unknown", "abc", "missing", "empty", "deactivated"])
def test_an_unknown_or_deactivated_subject_is_not_found(scene: Scene, subject: str) -> None:
    """US4-6, FR-023: with or without finished competitions."""
    make_competition(scene.engine, scene.chemistry, "Done", starts_at=STARTED, stopped=True)
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    value = {
        "unknown": MISSING,
        "abc": "abc",
        "missing": None,
        "empty": "",
        "deactivated": scene.chemistry,
    }[subject]
    not_found(study_file(scene.olena, value), STUDY_SUBJECT_NOT_FOUND)


def test_150_questions_continue_across_pages(scene: Scene) -> None:
    """US5-6: a subject of 150 questions gives a file of several numbered pages."""
    history = make_subject(scene.engine, "History")
    for n in range(150):
        make_question(scene.engine, history, f"Question text {n} " + "why " * 20, "Because. " * 10)
    pages = pdf_page_texts(study_file(scene.taras, history).content)
    assert len(pages) > 3
    assert all(f"Page {n} of {len(pages)}" in page for n, page in enumerate(pages, start=1))
    assert flat(pages[1]).startswith("Study materials: History")


# ---------------------------------------------------------------------------------------------
# User story 6: the study materials kept in memory, never out of date
# ---------------------------------------------------------------------------------------------


def test_a_second_download_gives_the_kept_file(scene: Scene, renders: list[Any]) -> None:
    """US6-1, FR-032, FR-033."""
    first = study_file(scene.taras, scene.chemistry)
    second = study_file(scene.olena, scene.chemistry)
    assert len(renders) == 1
    assert first.content == second.content


def change_text(s: Scene) -> None:
    with Session(s.engine) as session:
        update_question(
            session, s.olena_id, s.bank[0], "A new text?", QUESTIONS[0][1], is_additional=False
        )


def change_by_form(s: Scene) -> None:
    response = s.olena.post(
        f"/teacher/questions/{s.bank[2]}/edit",
        data={"page": "1", "text": QUESTIONS[2][0], "reference_answer": "A new answer."},
        follow_redirects=False,
    )
    assert response.status_code == 303


def add(s: Scene) -> None:
    make_question(s.engine, s.chemistry, "A new question?", "A new answer.")


def delete(s: Scene) -> None:
    with Session(s.engine) as session:
        delete_question(session, s.olena_id, s.bank[0])


def mark(s: Scene) -> None:
    with Session(s.engine) as session:
        update_question(session, s.olena_id, s.bank[0], *QUESTIONS[0], is_additional=True)


def unmark(s: Scene) -> None:
    with Session(s.engine) as session:
        update_question(session, s.olena_id, s.bank[1], *QUESTIONS[1], is_additional=False)


def rename(s: Scene) -> None:
    with s.engine.begin() as connection:
        connection.execute(
            text("UPDATE subjects SET name = 'Chemistry and Biology' WHERE id = :id"),
            {"id": s.chemistry},
        )


def outside(s: Scene) -> None:
    """A fix written straight to the database, without the application."""
    with s.engine.begin() as connection:
        connection.execute(
            text("UPDATE questions SET reference_answer = 'A new answer.' WHERE id = :id"),
            {"id": s.bank[0]},
        )


CHANGES: dict[str, tuple[Callable[[Scene], None], str, bool]] = {
    "edit": (change_text, "A new text?", True),
    "edit-form": (change_by_form, "A new answer.", True),
    "add": (add, "A new question?", True),
    "delete": (delete, QUESTIONS[0][0], False),
    "mark": (mark, QUESTIONS[0][0], False),
    "unmark": (unmark, QUESTIONS[1][0], True),
    "rename": (rename, "Chemistry and Biology", True),
    "outside": (outside, "A new answer.", True),
}
"""Each change, a text it touches, and whether the next file holds that text."""


@pytest.mark.parametrize("change", list(CHANGES))
def test_every_change_gives_a_new_file(scene: Scene, renders: list[Any], change: str) -> None:
    """US6-2, US6-3, FR-033, FR-034, SC-006: adding, editing (in the application or straight in
    the database), deleting, marking, unmarking and renaming each make a new file at the next
    download, which shows the change."""
    apply, touched, shown = CHANGES[change]
    before = flat(pdf_text(study_file(scene.taras, scene.chemistry).content))
    assert (touched in before) is not shown
    apply(scene)
    after = flat(pdf_text(study_file(scene.taras, scene.chemistry).content))
    assert len(renders) == 2
    assert (touched in after) is shown


def test_each_language_is_kept_on_its_own(scene: Scene, renders: list[Any]) -> None:
    """US6-4, FR-032."""
    english = study_file(en(scene.taras), scene.chemistry).content
    ukrainian = study_file(uk(scene.olena), scene.chemistry).content
    assert len(renders) == 2
    assert english != ukrainian
    assert study_file(en(scene.olena), scene.chemistry).content == english
    assert study_file(uk(scene.taras), scene.chemistry).content == ukrainian
    assert len(renders) == 2


def test_a_new_day_in_kyiv_gives_a_new_file(scene: Scene, renders: list[Any]) -> None:
    """US6-5, FR-033: 21:59 UTC is still 1 March in Kyiv; 22:00 UTC is 2 March."""
    study_file(scene.taras, scene.chemistry)
    scene.clock(timedelta(hours=12, minutes=59))
    study_file(scene.taras, scene.chemistry)
    assert len(renders) == 1
    scene.clock(timedelta(minutes=1))
    response = study_file(scene.taras, scene.chemistry)
    assert len(renders) == 2
    assert "Downloaded: 2 March 2027" in flat(pdf_text(response.content))
    attachment(response, "Chemistry 2027-03-02 study materials.pdf")


def test_a_file_made_while_the_bank_changed_is_not_given_after_it(
    scene: Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    """US6-6, FR-035: the change is committed while the first file is being made; the next
    download makes the file again and shows it."""
    made: list[Any] = []
    real = question_files_pdf.render_study_materials_pdf

    def changing(materials: Any, language: Any) -> bytes:
        made.append(materials)
        if len(made) == 1:
            outside(scene)
        return real(materials, language)

    monkeypatch.setattr(question_files_pdf, "render_study_materials_pdf", changing)
    first = flat(pdf_text(study_file(scene.taras, scene.chemistry).content))
    assert "A new answer." not in first
    second = flat(pdf_text(study_file(scene.taras, scene.chemistry).content))
    assert len(made) == 2
    assert "A new answer." in second


def test_a_deactivated_subject_is_not_found_whatever_is_kept(
    scene: Scene, renders: list[Any]
) -> None:
    """US6-7, FR-033."""
    attachment(study_file(scene.taras, scene.chemistry), "Chemistry 2027-03-01 study materials.pdf")
    with Session(scene.engine) as session:
        set_subject_active(session, scene.chemistry, False)
    not_found(study_file(scene.taras, scene.chemistry), STUDY_SUBJECT_NOT_FOUND)
    assert len(renders) == 1


def test_simultaneous_downloads_make_the_file_once(
    scene: Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    """US6-8, FR-036, SC-007: the second request waits on the subject's lock while the first one
    makes the file, then gets the kept file. (A two-party barrier inside the renderer would
    deadlock: the second request never enters it.)"""
    made: list[Any] = []
    entered, release = threading.Event(), threading.Event()
    real = question_files_pdf.render_study_materials_pdf

    def slow(materials: Any, language: Any) -> bytes:
        made.append(materials)
        entered.set()
        assert release.wait(10)
        return real(materials, language)

    monkeypatch.setattr(question_files_pdf, "render_study_materials_pdf", slow)
    results: list[Any] = []

    def download() -> None:
        results.append(study_file(scene.taras, scene.chemistry))

    first = threading.Thread(target=download)
    first.start()
    assert entered.wait(10)
    second = threading.Thread(target=download)
    second.start()
    time.sleep(0.3)  # long enough for the second request to queue on the lock
    release.set()
    first.join(10)
    second.join(10)
    assert len(made) == 1
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].content == results[1].content


def test_a_new_start_makes_the_file_again(scene: Scene, renders: list[Any]) -> None:
    """US6-9, FR-037: every start of the application begins with an empty cache."""
    study_file(scene.taras, scene.chemistry)
    kept = app.state.study_materials
    with TestClient(app):
        assert app.state.study_materials is not kept
    study_file(scene.taras, scene.chemistry)
    assert len(renders) == 2


# ---------------------------------------------------------------------------------------------
# Speed (SC-005, SC-008)
# ---------------------------------------------------------------------------------------------


def test_the_downloads_are_quick(scene: Scene) -> None:
    """SC-005: a kept file of 150 questions within 1 s; SC-008: the questions file of a
    competition of 10 questions within 1 s."""
    history = make_subject(scene.engine, "History")
    for n in range(150):
        make_question(scene.engine, history, f"Question {n}? " + "why " * 30, "Because. " * 20)
    study_file(scene.taras, history)
    started = time.perf_counter()
    response = study_file(scene.taras, history)
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert elapsed < 1, f"a kept file of 150 questions took {elapsed:.2f} s"
    ten = make_competition(scene.engine, history, "Ten", starts_at=STARTED)
    for n in range(10):
        add_competition_question(
            scene.engine, ten, make_question(scene.engine, history, f"Q{n}? " + "why " * 40)
        )
    started = time.perf_counter()
    response = questions_file(scene.taras, ten, history)
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert elapsed < 1, f"a questions file of 10 questions took {elapsed:.2f} s"
