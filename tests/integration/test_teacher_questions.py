"""The Questions tab, end to end through the test client.

See specs/011-question-bank/spec.md US1–US5, contracts/http-routes.md and research R15. Every case
runs on both engines. The scene:

- the manager: a real teacher with **Can manage competitions**;
- the reader: a real teacher without it;
- "Mathematics": 25 questions; "Physics": 3; "Chemistry": deactivated, with a question;
- "Biology": no question; "Geography": only a deleted question.

The access sweep is built from the router's own route table, with real subject and question ids
(the generic sweeps in `test_routes.py` and `test_teacher_access.py` leave this tab out).
"""

import re
from dataclasses import dataclass
from typing import Any, NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, MetaData, select
from sqlmodel import Session, col

import app.routers.teacher_questions as teacher_questions
from app.core.db import utc_now
from app.main import app
from app.models import AccessLevel, Question, Role
from app.services.questions import delete_question
from app.services.subjects import set_subject_active
from app.services.teachers import get_teacher, update_teacher
from app.services.users import get_user_by_email
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    STUDENT_EMAIL,
    ClientAs,
    make_institution,
    make_question,
    make_subject,
    make_teacher,
)
from tests.integration.test_routes import ALL_ROUTES

MANAGER = "manager@example.org"
READER = "reader@example.org"
TAB = "/teacher/questions"
MISSING = 999_999

SUBJECT_NOT_FOUND = ("Subject not found", "This subject does not exist or is deactivated.")
QUESTION_NOT_FOUND = (
    "Question not found",
    "This question does not exist, was deleted, or its subject is deactivated.",
)
DELETE_CONSEQUENCE = (
    "The question will be hidden from this list and can no longer be added to new competitions. "
    "It is not erased, but it cannot be restored."
)

QUESTION_ROUTES = sorted(
    (method, path)
    for path, methods, _ in ALL_ROUTES
    if path.startswith(TAB)
    for method in methods
    if method in ("GET", "POST")
)
MANAGE_ROUTES = [route for route in QUESTION_ROUTES if route != ("GET", TAB)]


@dataclass(frozen=True)
class Scene:
    engine: Engine
    manager: TestClient
    reader: TestClient
    manager_id: int
    maths: int
    maths_ids: list[int]
    """In creation order: the list shows them reversed."""
    physics: int
    physics_ids: list[int]
    chemistry: int
    """Deactivated."""
    chemistry_question: int
    biology: int
    geography: int
    deleted: int
    """Geography's only question, deleted."""

    def newest_first(self) -> list[int]:
        return self.maths_ids[::-1]


def bulk_questions(engine: Engine, subject_id: int, n: int, prefix: str = "Q") -> list[int]:
    """`n` questions of the subject in one transaction ("Q0", "Q1", …); their ids, in order."""
    now = utc_now()
    with Session(engine) as session:
        rows = [
            Question(
                subject_id=subject_id,
                text=f"{prefix}{i}",
                reference_answer=f"A{i}",
                created_at=now,
                updated_at=now,
            )
            for i in range(n)
        ]
        for row in rows:
            session.add(row)
            session.flush()
        session.commit()
        return [row.id for row in rows if row.id is not None]


@pytest.fixture
def scene(client: TestClient, client_as: ClientAs) -> Scene:
    engine, settings = app.state.engine, app.state.settings
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    manager_id = make_teacher(
        engine,
        settings,
        email=MANAGER,
        institutions={institution: AccessLevel.READ},
        can_manage=True,
    )
    make_teacher(engine, settings, email=READER, institutions={institution: AccessLevel.WRITE})
    maths = make_subject(engine, "Mathematics")
    physics = make_subject(engine, "Physics")
    chemistry = make_subject(engine, "Chemistry")
    biology = make_subject(engine, "Biology")
    geography = make_subject(engine, "Geography")
    maths_ids = bulk_questions(engine, maths, 25)
    physics_ids = bulk_questions(engine, physics, 3, prefix="P")
    chemistry_question = make_question(engine, chemistry, "Chemical?", "Yes.")
    deleted = make_question(engine, geography, "Gone?", "Gone.", deleted=True)
    with Session(engine) as session:
        set_subject_active(session, chemistry, False)
    return Scene(
        engine=engine,
        manager=client_as(MANAGER),
        reader=client_as(READER),
        manager_id=manager_id,
        maths=maths,
        maths_ids=maths_ids,
        physics=physics,
        physics_ids=physics_ids,
        chemistry=chemistry,
        chemistry_question=chemistry_question,
        biology=biology,
        geography=geography,
        deleted=deleted,
    )


SNAPSHOT_TABLES = ("questions", "teacher_profiles")


def snapshot(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=SNAPSHOT_TABLES)
    with engine.connect() as connection:
        return {
            name: sorted(tuple(row) for row in connection.execute(select(metadata.tables[name])))
            for name in SNAPSHOT_TABLES
        }


def stored(engine: Engine, question_id: int) -> Question:
    with Session(engine) as session:
        question = session.get(Question, question_id)
        assert question is not None
        return question


def count_questions(engine: Engine) -> int:
    with Session(engine) as session:
        return len(session.exec(select(Question.id)).all())


class Card(NamedTuple):
    id: str
    heading: str
    boxes: list[tuple[str, str]]
    """`(label, raw inner HTML)` of each text box: escaped, line breaks kept."""
    actions: list[tuple[str, str]]
    """`(text, href)` of each action link."""


def cards(body: str) -> list[Card]:
    found = []
    for article in html.parse(body).find_all("article"):
        if "text-card" not in article.classes():
            continue
        (heading,) = article.find_all("h3")
        boxes = []
        for box in article.find_all("section"):
            (label,) = box.find_all("h4")
            (text,) = box.find_all("p")
            boxes.append((label.text(), body[text.inner_start : text.inner_end]))
        actions = [(a.text(), a.attrs["href"]) for a in article.find_all("a")]
        found.append(Card(article.attrs.get("id", ""), heading.text(), boxes, actions))
    return found


def card_ids(body: str) -> list[int]:
    return [int(card.id.removeprefix("question-")) for card in cards(body)]


def empty_state(body: str) -> tuple[str, str | None] | None:
    states = [d for d in html.parse(body).find_all("div") if "empty-state" in d.classes()]
    if not states:
        return None
    (state,) = states
    message = [p.text() for p in state.find_all("p") if "empty-state-message" in p.classes()]
    hint = [p.text() for p in state.find_all("p") if "empty-state-hint" in p.classes()]
    return message[0], hint[0] if hint else None


def subject_options(body: str) -> list[tuple[str, str, bool]]:
    return [(o.value, o.text, o.selected) for o in html.options(body, "subject")]


def textarea(body: str, name: str) -> str:
    """The value a browser shows in the textarea named `name`: HTML drops one leading line
    break, which Python's parser keeps."""
    value = next(i.value for f in html.forms(body, "main") for i in f.inputs if i.name == name)
    return value.removeprefix("\n")


def not_found(response: Any, page: tuple[str, str]) -> None:
    assert response.status_code == 404
    assert html.h1(response.text) == page[0]
    assert page[1] in response.text
    assert ("/teacher/questions", "Back to the questions") in html.link_pairs(response.text)
    current = [t for t in html.nav(response.text, "Teacher area") if t.attrs.get("aria-current")]
    assert [t.text for t in current] == ["Questions"]


def denied(response: Any) -> None:
    assert response.status_code == 403
    assert "Your current role, Teacher, cannot open this page." in response.text


# ---------------------------------------------------------------------------------------------
# User story 2: reading the bank
# ---------------------------------------------------------------------------------------------


def test_the_tab_row_and_the_area_address(scene: Scene) -> None:
    """US2-1, FR-010: three tabs, Questions current here; `/teacher` still opens Students."""
    body = scene.reader.get(TAB).text
    tabs = html.nav(body, "Teacher area")
    assert [(t.href, t.text) for t in tabs] == [
        ("/teacher/students", "Students"),
        (TAB, "Questions"),
        ("/teacher/competitions", "Competitions"),
    ]
    assert [t.text for t in tabs if t.attrs.get("aria-current") == "page"] == ["Questions"]
    response = scene.reader.get("/teacher", follow_redirects=False)
    assert response.headers["location"] == "/teacher/students"


def test_the_subject_list_offers_the_active_subjects_in_order(scene: Scene) -> None:
    """US2-2, US2-4: Chemistry is deactivated; with no selection, "Select a subject"."""
    body = scene.reader.get(TAB).text
    assert html.h1(body) == "Questions"
    assert subject_options(body) == [
        ("", "Choose a subject", False),
        (str(scene.biology), "Biology", False),
        (str(scene.geography), "Geography", False),
        (str(scene.maths), "Mathematics", False),
        (str(scene.physics), "Physics", False),
    ]
    assert empty_state(body) == (
        "Select a subject",
        "Choose a subject in the list above to see its questions.",
    )
    assert cards(body) == []


def test_the_only_active_subject_is_selected_automatically(
    client: TestClient, client_as: ClientAs
) -> None:
    """US2-3, US2-6: with one active subject the page opens on it, also from an invalid
    address."""
    engine, settings = app.state.engine, app.state.settings
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    make_teacher(engine, settings, email=READER, institutions={institution: AccessLevel.READ})
    physics = make_subject(engine, "Physics")
    make_subject(engine, "Chemistry", active=False)
    question = make_question(engine, physics, "Why?", "Because.")
    reader = client_as(READER)
    for url in (TAB, f"{TAB}?subject=abc", f"{TAB}?subject={MISSING}"):
        body = reader.get(url).text
        assert subject_options(body)[1:] == [(str(physics), "Physics", True)]
        assert card_ids(body) == [question]


def test_no_subjects_yet(client: TestClient, client_as: ClientAs) -> None:
    """US2-5: no active subject, here only a deactivated one."""
    engine, settings = app.state.engine, app.state.settings
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    make_teacher(
        engine,
        settings,
        email=MANAGER,
        institutions={institution: AccessLevel.READ},
        can_manage=True,
    )
    make_subject(engine, "Chemistry", active=False)
    body = client_as(MANAGER).get(TAB).text
    assert empty_state(body) == ("No subjects yet", "Ask an administrator to add a subject.")
    assert "Add question" not in body


def test_an_invalid_subject_in_the_address_is_no_selection(scene: Scene) -> None:
    """US2-6, FR-016: never an error on the list page."""
    for value in ("abc", "%D9%A2", "9" * 40, str(MISSING), str(scene.chemistry), "", "-1"):
        response = scene.reader.get(f"{TAB}?subject={value}")
        assert response.status_code == 200, value
        assert empty_state(response.text) == (
            "Select a subject",
            "Choose a subject in the list above to see its questions.",
        ), value
        assert not any(selected for _, _, selected in subject_options(response.text))


@pytest.mark.parametrize("subject", ["biology", "geography"], ids=["none", "only-deleted"])
def test_no_questions_yet(scene: Scene, subject: str) -> None:
    """US2-7: the hint only for a teacher who may add."""
    url = f"{TAB}?subject={getattr(scene, subject)}"
    assert empty_state(scene.manager.get(url).text) == (
        "No questions yet",
        "Add the first question with Add question.",
    )
    assert empty_state(scene.reader.get(url).text) == ("No questions yet", None)


def test_the_questions_newest_first_ten_per_page(scene: Scene) -> None:
    """US2-8: 10, 10 and 5, nothing from Physics."""
    newest = scene.newest_first()
    pages = [
        card_ids(scene.reader.get(f"{TAB}?subject={scene.maths}&page={p}").text) for p in (1, 2, 3)
    ]
    assert pages == [newest[:10], newest[10:20], newest[20:]]
    assert not set(scene.physics_ids) & {q for page in pages for q in page}


def test_each_question_shows_its_number_text_and_reference_answer(scene: Scene) -> None:
    """US2-9: the anchor, the heading, the full text then the answer, line breaks kept and
    markup escaped."""
    question = make_question(
        scene.engine, scene.biology, "<b>Bold?</b>\nSecond line & more", "Yes,\n\nreally."
    )
    body = scene.reader.get(f"{TAB}?subject={scene.biology}").text
    assert cards(body) == [
        Card(
            f"question-{question}",
            f"Question {question}",
            [
                ("Question", "&lt;b&gt;Bold?&lt;/b&gt;\nSecond line &amp; more"),
                ("Reference answer", "Yes,\n\nreally."),
            ],
            [],
        )
    ]
    assert "<b>Bold?</b>" not in body


def test_the_page_navigation(scene: Scene) -> None:
    """US2-10, SC-005: with 200 questions, page 4."""
    history = make_subject(scene.engine, "History")
    bulk_questions(scene.engine, history, 200)
    body = scene.reader.get(f"{TAB}?subject={history}&page=4").text
    prefix = f"{TAB}?subject={history}&page="
    for label in ("Pages, top", "Pages, bottom"):
        found = html.pagination(body, label)
        assert found is not None, label
        range_text, entries = found
        assert range_text == "Questions 31–40 of 200"
        assert [e.text for e in entries] == ["Previous", "1", "2", "3", "4", "5", "…", "20", "Next"]
        assert entries[0].href == prefix + "3"
        assert entries[-1].href == prefix + "5"
        assert [e.text for e in entries if e.current] == ["4"]
        assert entries[6].href is None
    assert len(cards(body)) == 10


@pytest.mark.parametrize(
    ("page", "shown"),
    [(None, 1), ("abc", 1), ("0", 1), ("-1", 1), ("", 1), ("2", 2), ("999", 3), ("9" * 50, 3)],
)
def test_odd_page_values(scene: Scene, page: str | None, shown: int) -> None:
    """US2-11, FR-024: an invalid page is the first, one past the end the last, with no
    redirect."""
    url = f"{TAB}?subject={scene.maths}" + ("" if page is None else f"&page={page}")
    response = scene.reader.get(url, follow_redirects=False)
    assert response.status_code == 200
    found = html.pagination(response.text, "Pages, top")
    assert found is not None
    assert [e.text for e in found[1] if e.current] == [str(shown)]
    newest = scene.newest_first()
    assert card_ids(response.text) == newest[(shown - 1) * 10 : shown * 10]


def test_changing_the_subject_opens_its_first_page(scene: Scene) -> None:
    """US2-12, FR-017: the subject form carries no page."""
    body = scene.reader.get(f"{TAB}?subject={scene.maths}&page=3").text
    (form,) = [f for f in html.forms(body, "main") if f.action == TAB]
    assert form.method == "get"
    assert [i.name for i in form.inputs] == ["subject"]


def test_the_address_keeps_the_subject_and_page(scene: Scene, client_as: ClientAs) -> None:
    """US2-13: a reload, or another browser, shows the same subject and page."""
    url = f"{TAB}?subject={scene.maths}&page=2"
    first = scene.reader.get(url).text
    again = client_as(READER).get(url).text
    assert card_ids(first) == card_ids(again) == scene.newest_first()[10:20]
    assert (str(scene.maths), "Mathematics", True) in subject_options(again)


def test_without_javascript(scene: Scene) -> None:
    """US2-14, FR-012, FR-023: the subject form has a nameless Show button inside `<noscript>`,
    and paging is plain links."""
    body = scene.reader.get(f"{TAB}?subject={scene.maths}").text
    (form,) = [f for f in html.forms(body, "main") if f.action == TAB]
    assert [(b.text, b.name) for b in form.buttons] == [("Show", None)]
    (noscript,) = html.parse(body).find_all("noscript")
    assert [b.text() for b in noscript.find_all("button")] == ["Show"]
    found = html.pagination(body, "Pages, top")
    assert found is not None
    assert [e.href for e in found[1] if e.text == "Next"] == [f"{TAB}?subject={scene.maths}&page=2"]


def test_the_actions_only_with_the_setting(scene: Scene) -> None:
    """US2-15, FR-008, FR-021: Edit and Delete carry the current page."""
    url = f"{TAB}?subject={scene.maths}&page=2"
    reader = scene.reader.get(url).text
    assert "Add question" not in reader
    assert all(card.actions == [] for card in cards(reader))
    manager = scene.manager.get(url).text
    assert (f"{TAB}/new?subject={scene.maths}&page=2", "Add question") in html.link_pairs(
        manager, "main"
    )
    for card in cards(manager):
        number = card.id.removeprefix("question-")
        assert card.actions == [
            ("Edit", f"{TAB}/{number}/edit?page=2"),
            ("Delete", f"{TAB}/{number}/delete?page=2"),
        ]


def test_opening_the_list_changes_nothing(scene: Scene) -> None:
    before = snapshot(scene.engine)
    for client in (scene.reader, scene.manager):
        client.get(TAB)
        client.get(f"{TAB}?subject={scene.maths}&page=2")
    assert snapshot(scene.engine) == before


# ---------------------------------------------------------------------------------------------
# User story 1: adding
# ---------------------------------------------------------------------------------------------


def add(
    client: TestClient,
    subject: int | str,
    text: str,
    answer: str,
    then: str = "list",
    page: str = "1",
) -> Any:
    data = {"subject": str(subject), "page": page, "text": text, "reference_answer": answer}
    if then is not None:
        data["then"] = then
    return client.post(TAB, data=data, follow_redirects=False)


def test_the_add_form(scene: Scene) -> None:
    """US1-1, FR-026: the subject is named, not offered; two empty fields; both saves."""
    body = scene.manager.get(f"{TAB}/new?subject={scene.physics}&page=1").text
    assert html.h1(body) == "Add question"
    assert "Subject: Physics" in html.text(body, "main")
    (form,) = [f for f in html.forms(body, "main") if f.method == "post"]
    assert form.action == TAB
    assert [(i.name, i.type, i.value) for i in form.inputs] == [
        ("subject", "hidden", str(scene.physics)),
        ("page", "hidden", "1"),
        ("text", "textarea", ""),
        ("reference_answer", "textarea", ""),
    ]
    assert [(b.text, b.name, b.value) for b in form.buttons] == [
        ("Save question", "then", "list"),
        ("Save and add one more question", "then", "another"),
    ]
    for name in ("text", "reference_answer"):
        attrs = html.control(body, name)
        assert "required" in attrs and attrs["maxlength"] == "2000"
    assert html.notices(body) == []


def test_save_question_returns_to_the_first_page(scene: Scene) -> None:
    """US1-2, FR-027: the new question is first."""
    response = add(scene.manager, scene.physics, "New?", "Yes.")
    assert response.status_code == 303
    assert response.headers["location"] == f"{TAB}?subject={scene.physics}"
    body = scene.manager.get(response.headers["location"]).text
    assert cards(body)[0].boxes == [("Question", "New?"), ("Reference answer", "Yes.")]


def test_save_and_add_one_more_question(scene: Scene) -> None:
    """US1-3, FR-028: an empty form with the notice, keeping the return page."""
    response = add(scene.manager, scene.maths, "More?", "Yes.", then="another", page="2")
    assert response.status_code == 303
    location = response.headers["location"]
    assert location == f"{TAB}/new?subject={scene.maths}&page=2&saved=1"
    body = scene.manager.get(location).text
    assert html.notices(body) == [("status", "The question was saved.")]
    assert textarea(body, "text") == textarea(body, "reference_answer") == ""
    assert ("Cancel", f"{TAB}?subject={scene.maths}&page=2") in [
        (t, h) for h, t in html.link_pairs(body, "main")
    ]
    assert count_questions(scene.engine) == 25 + 3 + 2 + 1


@pytest.mark.parametrize("then", ["list", "another"])
@pytest.mark.parametrize(
    ("text", "answer", "errors"),
    [
        ("", "Yes.", {"text": "Enter the question text."}),
        ("Why?", "   ", {"reference_answer": "Enter the reference answer."}),
        (
            " \n ",
            "",
            {"text": "Enter the question text.", "reference_answer": "Enter the reference answer."},
        ),
    ],
    ids=["no-text", "spaces-answer", "both"],
)
def test_an_empty_field_is_refused(
    scene: Scene, then: str, text: str, answer: str, errors: dict[str, str]
) -> None:
    """US1-4, FR-029: nothing stored; each error beside its field and in the summary, in field
    order; the values kept."""
    before = snapshot(scene.engine)
    response = add(scene.manager, scene.physics, text, answer, then=then)
    assert response.status_code == 400
    body = response.text
    for field, message in errors.items():
        assert html.field_error(body, field) == message
    summary = html.error_summary(body)
    assert summary is not None
    assert summary.items == [(f"#{f}", m) for f, m in errors.items()]
    assert textarea(body, "text") == text
    assert textarea(body, "reference_answer") == answer
    assert [n for n in html.notices(body) if n[0] == "status"] == []
    assert snapshot(scene.engine) == before


def test_the_length_limit(scene: Scene) -> None:
    """US1-5: 2,001 characters after trimming are refused, values kept; exactly 2,000 stored."""
    long = "ї" * 2001
    response = add(scene.manager, scene.physics, long, "Yes.")
    assert response.status_code == 400
    assert html.field_error(response.text, "text") == (
        "The question text can be at most 2,000 characters."
    )
    assert textarea(response.text, "text") == long
    response = add(scene.manager, scene.physics, "  " + "ї" * 2000 + "  ", "a" * 2000)
    assert response.status_code == 303
    body = scene.manager.get(response.headers["location"]).text
    assert cards(body)[0].boxes == [("Question", "ї" * 2000), ("Reference answer", "a" * 2000)]


def test_a_duplicate_is_accepted(scene: Scene) -> None:
    """US1-6."""
    for _ in range(2):
        assert add(scene.manager, scene.biology, "Same?", "Same.").status_code == 303
    body = scene.manager.get(f"{TAB}?subject={scene.biology}").text
    assert [card.boxes[0] for card in cards(body)] == [("Question", "Same?")] * 2


def test_values_are_trimmed_and_line_breaks_kept(scene: Scene) -> None:
    """US1-7: CRLF inner breaks are stored as LF."""
    add(scene.manager, scene.biology, "\r\n  Line one\r\nLine two  \r\n", "  A\rB ")
    (question,) = card_ids(scene.manager.get(f"{TAB}?subject={scene.biology}").text)
    row = stored(scene.engine, question)
    assert (row.text, row.reference_answer) == ("Line one\nLine two", "A\nB")


def test_the_return_page_is_a_number_only(scene: Scene) -> None:
    """US1-8, FR-035, spec Edge Cases: Cancel from page 3; a crafted page is never an
    address."""
    body = scene.manager.get(f"{TAB}/new?subject={scene.maths}&page=3").text
    assert (f"{TAB}?subject={scene.maths}&page=3", "Cancel") in html.link_pairs(body, "main")
    for page in ("https://evil.example", "abc", "//evil.example"):
        body = scene.manager.get(f"{TAB}/new?subject={scene.maths}&page={page}").text
        assert (f"{TAB}?subject={scene.maths}", "Cancel") in html.link_pairs(body, "main")
        response = add(scene.manager, scene.maths, "Q?", "A.", then="another", page=page)
        assert response.headers["location"] == f"{TAB}/new?subject={scene.maths}&page=1&saved=1"


@pytest.mark.parametrize("then", ["", "elsewhere", None], ids=["empty", "unknown", "missing"])
def test_an_unknown_then_saves_as_save_question(scene: Scene, then: str | None) -> None:
    response = add(scene.manager, scene.physics, "Q?", "A.", then=then)  # type: ignore[arg-type]
    assert response.headers["location"] == f"{TAB}?subject={scene.physics}"


def test_reloading_after_a_save_stores_nothing_more(scene: Scene) -> None:
    """SC-009: the 303 target is a GET."""
    response = add(scene.manager, scene.physics, "Once?", "Once.", then="another")
    before = snapshot(scene.engine)
    for _ in range(2):
        assert scene.manager.get(response.headers["location"]).status_code == 200
    assert snapshot(scene.engine) == before


def test_adding_end_to_end(scene: Scene) -> None:
    """The US1 narrative: choose a subject, add two questions with the two buttons, see them
    first on page 1, newest first."""
    body = scene.manager.get(f"{TAB}?subject={scene.biology}").text
    (add_href,) = [h for h, t in html.link_pairs(body, "main") if t == "Add question"]
    assert scene.manager.get(add_href).status_code == 200
    first = add(scene.manager, scene.biology, "First?", "1.", then="another")
    scene.manager.get(first.headers["location"])
    second = add(scene.manager, scene.biology, "Second?", "2.")
    body = scene.manager.get(second.headers["location"]).text
    assert [card.boxes[0][1] for card in cards(body)] == ["Second?", "First?"]


# ---------------------------------------------------------------------------------------------
# User story 3: editing
# ---------------------------------------------------------------------------------------------


def edit(client: TestClient, question_id: int, text: str, answer: str, **extra: str) -> Any:
    data = {"page": "2", "text": text, "reference_answer": answer, **extra}
    return client.post(f"{TAB}/{question_id}/edit", data=data, follow_redirects=False)


def test_the_edit_form(scene: Scene) -> None:
    """US3-1: the stored values, line breaks intact (a leading one too), the subject as text."""
    question = make_question(scene.engine, scene.maths, "\nStarts with a break\nand more", "A\n\nB")
    body = scene.manager.get(f"{TAB}/{question}/edit?page=2").text
    assert html.h1(body) == f"Edit question {question}"
    assert "Subject: Mathematics" in html.text(body, "main")
    assert textarea(body, "text") == "\nStarts with a break\nand more"
    assert textarea(body, "reference_answer") == "A\n\nB"
    (form,) = [f for f in html.forms(body, "main") if f.method == "post"]
    assert form.action == f"{TAB}/{question}/edit"
    assert [i.name for i in form.inputs] == ["page", "text", "reference_answer"]
    assert [(b.text, b.name) for b in form.buttons] == [("Save question", None)]
    assert (
        html.links(body, "main")[0].href
        == f"{TAB}?subject={scene.maths}&page=2#question-{question}"
    )


def test_saving_an_edit_returns_to_the_question(scene: Scene) -> None:
    """US3-2, FR-032: the number and subject kept; back to page 2 at the question."""
    question = scene.newest_first()[12]
    response = edit(scene.manager, question, "Changed?", "Changed.")
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"{TAB}?subject={scene.maths}&page=2#question-{question}"
    )
    row = stored(scene.engine, question)
    assert (row.id, row.subject_id, row.text, row.reference_answer) == (
        question,
        scene.maths,
        "Changed?",
        "Changed.",
    )
    body = scene.manager.get(response.headers["location"].split("#")[0]).text
    assert card_ids(body) == scene.newest_first()[10:20]


def test_cancelling_an_edit(scene: Scene) -> None:
    """US3-3: Cancel goes back to the same page at the question; nothing changes."""
    question = scene.newest_first()[12]
    before = snapshot(scene.engine)
    body = scene.manager.get(f"{TAB}/{question}/edit?page=2").text
    expected = f"{TAB}?subject={scene.maths}&page=2#question-{question}"
    assert (expected, "Cancel") in html.link_pairs(body, "main")
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(
    ("text", "answer", "field", "message"),
    [
        ("", "A.", "text", "Enter the question text."),
        (
            "Q?",
            "x" * 2001,
            "reference_answer",
            "The reference answer can be at most 2,000 characters.",
        ),
    ],
    ids=["emptied", "too-long"],
)
def test_an_invalid_edit_changes_nothing(
    scene: Scene, text: str, answer: str, field: str, message: str
) -> None:
    """US3-4."""
    question = scene.maths_ids[0]
    before = snapshot(scene.engine)
    response = edit(scene.manager, question, text, answer)
    assert response.status_code == 400
    assert html.field_error(response.text, field) == message
    assert (textarea(response.text, "text"), textarea(response.text, "reference_answer")) == (
        text,
        answer,
    )
    assert snapshot(scene.engine) == before


def test_a_crafted_subject_is_ignored(scene: Scene) -> None:
    """US3-5, FR-031."""
    question = scene.maths_ids[0]
    response = edit(scene.manager, question, "Q?", "A.", subject=str(scene.physics))
    assert response.status_code == 303
    assert stored(scene.engine, question).subject_id == scene.maths


def test_an_edit_does_not_move_the_question(scene: Scene) -> None:
    question = scene.maths_ids[3]
    edit(scene.manager, question, "Moved?", "No.")
    pages = [
        card_ids(scene.manager.get(f"{TAB}?subject={scene.maths}&page={p}").text) for p in (1, 2, 3)
    ]
    assert [q for page in pages for q in page] == scene.newest_first()


# ---------------------------------------------------------------------------------------------
# User story 4: deleting
# ---------------------------------------------------------------------------------------------


def test_the_delete_confirmation(scene: Scene) -> None:
    """US4-1, US4-2, FR-033: the number, the consequence, Delete and Cancel; nothing else."""
    question = scene.newest_first()[12]
    before = snapshot(scene.engine)
    body = scene.manager.get(f"{TAB}/{question}/delete?page=2").text
    assert html.h1(body) == f"Delete question {question}?"
    assert DELETE_CONSEQUENCE in html.text(body, "main")
    assert "Q12" not in body  # the question's text is not shown
    [form] = [f for f in html.forms(body, "main") if f.method == "post"]
    assert form.action == f"{TAB}/{question}/delete"
    assert [b.text for b in form.buttons] == ["Delete"]
    cancel = f"{TAB}?subject={scene.maths}&page=2#question-{question}"
    assert (cancel, "Cancel") in html.link_pairs(body, "main")
    assert snapshot(scene.engine) == before


def test_a_deleted_question_is_hidden_and_stored_unchanged(scene: Scene) -> None:
    """US4-3, SC-003."""
    question = scene.newest_first()[12]
    before = stored(scene.engine, question)
    response = scene.manager.post(f"{TAB}/{question}/delete", follow_redirects=False)
    assert response.status_code == 303
    after = stored(scene.engine, question)
    assert after.deleted_at is not None
    assert (after.text, after.reference_answer, after.subject_id, after.updated_at) == (
        before.text,
        before.reference_answer,
        before.subject_id,
        before.updated_at,
    )
    listed = [
        q
        for p in (1, 2, 3)
        for q in card_ids(scene.manager.get(f"{TAB}?subject={scene.maths}&page={p}").text)
    ]
    assert question not in listed and len(listed) == 24


@pytest.mark.parametrize(
    ("count", "index", "page", "landing_index"),
    [(25, 14, 2, 14), (25, 9, 1, 9), (25, 24, 3, 23), (21, 20, 2, 19)],
    ids=["middle", "last-on-page", "last-of-list", "only-on-last-page"],
)
def test_where_the_list_lands(
    scene: Scene, count: int, index: int, page: int, landing_index: int
) -> None:
    """US4-4 to US4-7, FR-034: by the address, and by the anchored card on that page."""
    subject = make_subject(scene.engine, "History")
    newest = bulk_questions(scene.engine, subject, count)[::-1]
    response = scene.manager.post(f"{TAB}/{newest[index]}/delete", follow_redirects=False)
    remaining = [q for q in newest if q != newest[index]]
    target = remaining[landing_index]
    page_part = "" if page == 1 else f"&page={page}"
    assert response.headers["location"] == f"{TAB}?subject={subject}{page_part}#question-{target}"
    body = scene.manager.get(response.headers["location"].split("#")[0]).text
    assert target in card_ids(body)


def test_deleting_the_last_question_lands_on_the_empty_subject(scene: Scene) -> None:
    question = make_question(scene.engine, scene.biology)
    response = scene.manager.post(f"{TAB}/{question}/delete", follow_redirects=False)
    assert response.headers["location"] == f"{TAB}?subject={scene.biology}"
    assert (
        empty_state(scene.manager.get(response.headers["location"]).text)[0] == "No questions yet"
    )  # type: ignore[index]


def test_a_deleted_question_is_not_found_anywhere(scene: Scene) -> None:
    """US4-8, SC-009: its pages and actions, and a second delete."""
    question = scene.maths_ids[0]
    response = scene.manager.post(f"{TAB}/{question}/delete", follow_redirects=False)
    before = snapshot(scene.engine)
    scene.manager.get(response.headers["location"])
    for method, path in (("GET", "edit"), ("GET", "delete"), ("POST", "edit"), ("POST", "delete")):
        url = f"{TAB}/{question}/{path}"
        reply = scene.manager.request(
            method, url, data={"text": "x", "reference_answer": "y"} if method == "POST" else None
        )
        not_found(reply, QUESTION_NOT_FOUND)
    assert snapshot(scene.engine) == before


# ---------------------------------------------------------------------------------------------
# User story 5: access, existence, fields, and changes in between
# ---------------------------------------------------------------------------------------------


def test_the_tab_has_seven_endpoints() -> None:
    """Guard the sweeps below."""
    assert QUESTION_ROUTES == [
        ("GET", TAB),
        ("GET", f"{TAB}/new"),
        ("GET", f"{TAB}/{{question_id:int}}/delete"),
        ("GET", f"{TAB}/{{question_id:int}}/edit"),
        ("POST", TAB),
        ("POST", f"{TAB}/{{question_id:int}}/delete"),
        ("POST", f"{TAB}/{{question_id:int}}/edit"),
    ]


def concrete(path: str, question_id: int, subject_id: int) -> str:
    url = re.sub(r"\{question_id:int\}", str(question_id), path)
    if url.endswith("/new"):
        url += f"?subject={subject_id}"
    return url


def form_for(subject_id: int) -> dict[str, str]:
    return {
        "subject": str(subject_id),
        "page": "1",
        "text": "Hacked?",
        "reference_answer": "Hacked.",
    }


@pytest.mark.parametrize(("method", "path"), QUESTION_ROUTES)
def test_other_roles_are_refused(
    scene: Scene, client: TestClient, client_as: ClientAs, method: str, path: str
) -> None:
    """US5-1: administrators and students get the 403 page naming their role; anonymous
    visitors are sent to sign in; nothing changes."""
    url = concrete(path, scene.maths_ids[0], scene.maths)
    data = form_for(scene.maths) if method == "POST" else None
    before = snapshot(scene.engine)
    for browser, label in (
        (client_as(ADMIN_EMAIL), "Administrator"),
        (client_as(STUDENT_EMAIL), "Student"),
        (client_as(ADMIN_STUDENT_EMAIL, Role.STUDENT), "Student"),
    ):
        response = browser.request(method, url, data=data, follow_redirects=False)
        assert response.status_code == 403, (label, method, url)
        assert f"Your current role, {label}, cannot open this page." in response.text
    anonymous = client.request(method, url, data=data, follow_redirects=False)
    assert anonymous.status_code == 303
    assert anonymous.headers["location"].startswith("/login")
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(("method", "path"), MANAGE_ROUTES)
@pytest.mark.parametrize("target", ["listed", "missing", "deleted", "deactivated-subject"])
def test_a_teacher_without_the_setting_is_refused_before_anything_is_looked_up(
    scene: Scene, method: str, path: str, target: str
) -> None:
    """US5-2, FR-037: 403 whether the id exists or not; nothing changes."""
    question, subject = {
        "listed": (scene.maths_ids[0], scene.maths),
        "missing": (MISSING, MISSING),
        "deleted": (scene.deleted, scene.geography),
        "deactivated-subject": (scene.chemistry_question, scene.chemistry),
    }[target]
    url = concrete(path, question, subject)
    data = form_for(subject) if method == "POST" else None
    before = snapshot(scene.engine)
    denied(scene.reader.request(method, url, data=data, follow_redirects=False))
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize(("method", "path"), QUESTION_ROUTES)
def test_a_teacher_with_the_setting_is_admitted(scene: Scene, method: str, path: str) -> None:
    """SC-002."""
    url = concrete(path, scene.maths_ids[0], scene.maths)
    data = form_for(scene.maths) if method == "POST" else None
    response = scene.manager.request(method, url, data=data, follow_redirects=False)
    assert response.status_code in (200, 303), (method, url, response.status_code)


@pytest.mark.parametrize("value", ["abc", "", str(MISSING), "9" * 40, "chemistry"])
def test_adding_to_an_unavailable_subject_is_not_found(scene: Scene, value: str) -> None:
    """US5-3."""
    subject = str(scene.chemistry) if value == "chemistry" else value
    before = snapshot(scene.engine)
    not_found(scene.manager.get(f"{TAB}/new?subject={subject}"), SUBJECT_NOT_FOUND)
    not_found(add(scene.manager, subject, "Q?", "A."), SUBJECT_NOT_FOUND)
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize("target", ["missing", "huge", "deleted", "deactivated-subject"])
def test_an_unavailable_question_is_not_found(scene: Scene, target: str) -> None:
    """US5-4, FR-038."""
    question = {
        "missing": MISSING,
        "huge": 10**30,
        "deleted": scene.deleted,
        "deactivated-subject": scene.chemistry_question,
    }[target]
    before = snapshot(scene.engine)
    for path in ("edit", "delete"):
        not_found(scene.manager.get(f"{TAB}/{question}/{path}"), QUESTION_NOT_FOUND)
    not_found(edit(scene.manager, question, "Q?", "A."), QUESTION_NOT_FOUND)
    not_found(scene.manager.post(f"{TAB}/{question}/delete"), QUESTION_NOT_FOUND)
    assert snapshot(scene.engine) == before


def test_a_path_id_that_is_not_a_number_matches_no_route(scene: Scene) -> None:
    for browser in (scene.manager, scene.reader):
        response = browser.get(f"{TAB}/abc/edit")
        assert response.status_code == 404
        assert "Question not found" not in response.text


@pytest.mark.parametrize(
    ("method", "url", "data"),
    [
        ("GET", f"{TAB}?subject=%00&page=%FF", None),
        ("GET", f"{TAB}/new?page=x&saved=yes", None),
        ("POST", TAB, {}),
        ("POST", TAB, {"subject": "x", "page": "y", "then": "z"}),
        ("POST", f"{TAB}/1/edit", {}),
        ("POST", f"{TAB}/1/delete", {"anything": "x"}),
    ],
)
def test_no_input_gets_a_json_422(
    scene: Scene, method: str, url: str, data: dict[str, str] | None
) -> None:
    for browser in (scene.manager, scene.reader):
        response = browser.request(method, url, data=data, follow_redirects=False)
        assert response.status_code != 422
        assert not response.headers.get("content-type", "").startswith("application/json")


def remove_setting(engine: Engine) -> None:
    with Session(engine) as session:
        user = get_user_by_email(session, MANAGER)
        assert user is not None and user.id is not None
        view = get_teacher(session, user.id)
        update_teacher(
            session,
            user.id,
            view.first_name,
            view.last_name,
            {link.institution_id: link.access_level for link in view.links},
            can_manage_competitions=False,
        )


def deactivate(engine: Engine, subject_id: int) -> None:
    with Session(engine) as session:
        set_subject_active(session, subject_id, False)


def delete_directly(scene: Scene, question_id: int) -> None:
    with Session(scene.engine) as session:
        delete_question(session, scene.manager_id, question_id)


@pytest.mark.parametrize("change", ["question-deleted", "subject-deactivated", "setting-removed"])
def test_a_change_between_the_edit_form_and_its_save(scene: Scene, change: str) -> None:
    """US5-5, US5-6: the save sees what changed; nothing changes."""
    question = scene.maths_ids[0]
    assert scene.manager.get(f"{TAB}/{question}/edit").status_code == 200
    {
        "question-deleted": lambda: delete_directly(scene, question),
        "subject-deactivated": lambda: deactivate(scene.engine, scene.maths),
        "setting-removed": lambda: remove_setting(scene.engine),
    }[change]()
    before = snapshot(scene.engine)
    response = edit(scene.manager, question, "Late?", "Late.")
    if change == "setting-removed":
        denied(response)
    else:
        not_found(response, QUESTION_NOT_FOUND)
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize("change", ["subject-deactivated", "setting-removed"])
def test_a_change_between_the_add_form_and_its_save(scene: Scene, change: str) -> None:
    assert scene.manager.get(f"{TAB}/new?subject={scene.maths}").status_code == 200
    {
        "subject-deactivated": lambda: deactivate(scene.engine, scene.maths),
        "setting-removed": lambda: remove_setting(scene.engine),
    }[change]()
    before = snapshot(scene.engine)
    response = add(scene.manager, scene.maths, "Late?", "Late.")
    if change == "setting-removed":
        denied(response)
    else:
        not_found(response, SUBJECT_NOT_FOUND)
    assert snapshot(scene.engine) == before


@pytest.mark.parametrize("change", ["question-deleted", "subject-deactivated", "setting-removed"])
def test_a_change_between_the_confirmation_and_the_delete(scene: Scene, change: str) -> None:
    question = scene.maths_ids[0]
    assert scene.manager.get(f"{TAB}/{question}/delete").status_code == 200
    {
        "question-deleted": lambda: delete_directly(scene, question),
        "subject-deactivated": lambda: deactivate(scene.engine, scene.maths),
        "setting-removed": lambda: remove_setting(scene.engine),
    }[change]()
    before = snapshot(scene.engine)
    response = scene.manager.post(f"{TAB}/{question}/delete", follow_redirects=False)
    if change == "setting-removed":
        denied(response)
    else:
        not_found(response, QUESTION_NOT_FOUND)
    assert snapshot(scene.engine) == before


def _fail_loudly(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("looked up before the setting was checked")


@pytest.mark.parametrize(("method", "path"), MANAGE_ROUTES)
def test_the_setting_is_checked_before_any_lookup(
    scene: Scene, monkeypatch: pytest.MonkeyPatch, method: str, path: str
) -> None:
    """T053, http-routes.md §Order of checks: no subject or question is read for a teacher
    without the setting (a lookup would raise and fail the request)."""
    for name in ("get_active_subject", "get_question"):
        monkeypatch.setattr(teacher_questions, name, _fail_loudly)
    url = concrete(path, scene.maths_ids[0], scene.maths)
    data = form_for(scene.maths) if method == "POST" else None
    denied(scene.reader.request(method, url, data=data, follow_redirects=False))


def test_question_ids_are_the_stored_order(scene: Scene) -> None:
    """The scene's ids are increasing, so "newest first" is "largest id first"."""
    with Session(scene.engine) as session:
        ids = session.scalars(
            select(Question.id).where(Question.subject_id == scene.maths).order_by(col(Question.id))
        ).all()
    assert list(ids) == scene.maths_ids
