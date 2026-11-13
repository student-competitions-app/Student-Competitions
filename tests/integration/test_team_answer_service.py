"""A team's answers in a competition: the team answers page (which teams, their grouping, paging and
progress), the answer sheet, and the save (what it stores, the last save wins, the order of its
checks), under concurrency too.

See specs/012.3-team-answers/contracts/services.md and research R1–R7, R11, R17. Every case runs
on both engines; the two-session races run on PostgreSQL only (on SQLite the locks render
nothing, and writers are serialised anyway). The clock is fixed at 1 March 2027 09:00 UTC by
patching `app.services.competitions.utc_now`, which the service reads; no test waits.

- Taras: a real teacher with **Write** access to School No. 5 and Gymnasium No. 1 (Kyiv) and
  **Read** access to Lyceum No. 2 (Lviv), without **Can manage competitions**;
- Oksana: **Write** access to School No. 5 too; Iryna: **Read** access to Lyceum No. 2 only;
- "Spring round": an In progress competition of Chemistry (started 08:00) with 6 questions;
- "Comets" (School No. 5), "Lions" (Lyceum No. 2) and "Novas" (Kyiv Lyceum, which nobody is
  linked to) are in it.

Answers, finished and cancelled competitions and their entries are seeded directly
(`tests/conftest.py`), so the service is never checked through itself.
"""

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from app.core.config import AuthSettings
from app.models import (
    AccessLevel,
    CompetitionQuestion,
    CompetitionTeam,
    Institution,
    Role,
    TeamAnswer,
    User,
)
from app.services import team_answers
from app.services.competitions import (
    CompetitionNotFound,
    CompetitionStatus,
    cancel_competition,
    lock_competition,
)
from app.services.institutions import set_institution_active
from app.services.questions import delete_question, update_question
from app.services.regions import set_region_active
from app.services.subjects import set_subject_active
from app.services.teachers import update_teacher
from app.services.team_answers import (
    AnswersClosed,
    AnswersDenied,
    InvalidAnswers,
    QuestionNotFound,
    SaveResult,
    TeamNotFound,
)
from app.services.users import reconcile_users
from tests.conftest import (
    ADMIN_EMAIL,
    add_competition_question,
    add_competition_team,
    make_class,
    make_competition,
    make_institution,
    make_member,
    make_question,
    make_subject,
    make_teacher,
    make_team,
    save_team_answer,
    seed_roles_directly,
)
from tests.integration.test_competition_entries_service import postgresql_only, race
from tests.integration.test_team_service import enrolled

NOW = datetime(2027, 3, 1, 9, 0, tzinfo=UTC)
STARTED = datetime(2027, 3, 1, 8, 0, tzinfo=UTC)
LATER = datetime(2027, 3, 14, 8, 0, tzinfo=UTC)
MISSING = 999_999
TOO_LONG = "Answer to question {n} can be at most 2,000 characters."


@dataclass(frozen=True)
class Scene:
    engine: Engine
    settings: AuthSettings
    taras: int
    oksana: int
    iryna: int
    chemistry: int
    physics: int
    competition: int
    """"Spring round", In progress, 6 questions."""
    copies: list[int]
    """Its copies, in the order of adding: questions 1–6."""
    school: int
    gymnasium: int
    lyceum: int
    unlinked: int
    """"Kyiv Lyceum": nobody is linked to it."""
    comets: int
    """School No. 5, Write for Taras and Oksana."""
    lions: int
    """Lyceum No. 2, Read for Taras and Iryna."""
    novas: int
    """Kyiv Lyceum, linked to nobody."""


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[timedelta], datetime]:
    """A controllable `utc_now`, starting at 1 March 2027 09:00 UTC; call it to advance, and it
    returns the new time."""
    now = [NOW]
    monkeypatch.setattr("app.services.competitions.utc_now", lambda: now[0])

    def advance(by: timedelta = timedelta(0)) -> datetime:
        now[0] += by
        return now[0]

    return advance


@pytest.fixture
def scene(
    engine: Engine, auth_settings: AuthSettings, clock: Callable[[timedelta], datetime]
) -> Scene:
    with Session(engine) as session:
        reconcile_users(session, [ADMIN_EMAIL])
    school = make_institution(engine, "School No. 5", "Kyiv")
    gymnasium = make_institution(engine, "Gymnasium No. 1", "Kyiv")
    lyceum = make_institution(engine, "Lyceum No. 2", "Lviv")
    unlinked = make_institution(engine, "Kyiv Lyceum", "Kyiv")
    taras = make_teacher(
        engine,
        auth_settings,
        email="taras@example.org",
        institutions={
            school: AccessLevel.WRITE,
            gymnasium: AccessLevel.WRITE,
            lyceum: AccessLevel.READ,
        },
        first="Taras",
        last="Shevchenko",
    )
    oksana = make_teacher(
        engine,
        auth_settings,
        email="oksana@example.org",
        institutions={school: AccessLevel.WRITE},
        first="Oksana",
        last="Petrenko",
    )
    iryna = make_teacher(
        engine,
        auth_settings,
        email="iryna@example.org",
        institutions={lyceum: AccessLevel.READ},
        first="Iryna",
        last="Bondar",
    )
    chemistry = make_subject(engine, "Chemistry")
    competition = make_competition(engine, chemistry, starts_at=STARTED)
    copies = [
        add_competition_question(
            engine, competition, make_question(engine, chemistry, f"Question {n}?", f"Ref {n}.")
        )
        for n in range(1, 7)
    ]
    comets = make_team(engine, school, "Comets")
    lions = make_team(engine, lyceum, "Lions")
    novas = make_team(engine, unlinked, "Novas")
    for team in (comets, lions, novas):
        add_competition_team(engine, competition, team)
    return Scene(
        engine=engine,
        settings=auth_settings,
        taras=taras,
        oksana=oksana,
        iryna=iryna,
        chemistry=chemistry,
        physics=make_subject(engine, "Physics"),
        competition=competition,
        copies=copies,
        school=school,
        gymnasium=gymnasium,
        lyceum=lyceum,
        unlinked=unlinked,
        comets=comets,
        lions=lions,
        novas=novas,
    )


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def answers_of(engine: Engine, competition_id: int, team_id: int) -> dict[int, str]:
    """The team's stored answers in the competition, by copy id."""
    with Session(engine) as session:
        rows = session.exec(
            select(TeamAnswer).where(
                TeamAnswer.competition_id == competition_id, TeamAnswer.team_id == team_id
            )
        )
        return {row.competition_question_id: row.text for row in rows}


def snapshot(engine: Engine) -> list[tuple[int, int, int, str]]:
    with Session(engine) as session:
        return sorted(
            (a.competition_id, a.team_id, a.competition_question_id, a.text)
            for a in session.exec(select(TeamAnswer))
        )


def save(
    s: Scene,
    answers: Mapping[int, str],
    *,
    teacher: int | None = None,
    team: int | None = None,
    competition: int | None = None,
    subject: int | None = None,
) -> SaveResult:
    """`save_answers` in a fresh session, as Taras for Comets in Spring round unless told; the
    session must stay usable after a refusal, so a read follows in the same session."""
    with Session(s.engine) as session:
        try:
            return team_answers.save_answers(
                session,
                s.taras if teacher is None else teacher,
                s.competition if competition is None else competition,
                s.chemistry if subject is None else subject,
                s.comets if team is None else team,
                answers,
            )
        finally:
            session.exec(select(TeamAnswer.team_id)).all()


def sheet(s: Scene, *, teacher: int | None = None, team: int | None = None) -> Any:
    with Session(s.engine) as session:
        return team_answers.answer_sheet(
            session,
            s.taras if teacher is None else teacher,
            s.competition,
            s.comets if team is None else team,
        )


def listing(
    s: Scene, teacher: int | None = None, p: int = 1, competition: int | None = None
) -> Any:
    with Session(s.engine) as session:
        return team_answers.answer_team_page(
            session,
            s.taras if teacher is None else teacher,
            s.competition if competition is None else competition,
            p,
        )


def rows(page: Any) -> dict[str, Any]:
    """The page's rows by team name."""
    return {row.name: row for group in page.groups for row in group.rows}


def groups(page: Any) -> list[tuple[str, int, list[str]]]:
    return [(g.region_name, g.total, [r.name for r in g.rows]) for g in page.groups]


def region_of(engine: Engine, institution_id: int) -> int:
    with Session(engine) as session:
        institution = session.get(Institution, institution_id)
        assert institution is not None
        return institution.region_id


def unlinked_teacher(engine: Engine, email: str) -> int:
    """A teacher with no institution link at all, seeded directly as the test cast is."""
    seed_roles_directly(engine, {email: [Role.TEACHER]})
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).one()
        assert user.id is not None
        return user.id


def manager(s: Scene) -> int:
    """A teacher with **Can manage competitions**, linked to an institution with no team."""
    office = make_institution(s.engine, "District Office", "Kyiv")
    return make_teacher(
        s.engine,
        s.settings,
        email="manager@example.org",
        institutions={office: AccessLevel.READ},
        can_manage=True,
    )


def set_link(s: Scene, teacher: int, links: Mapping[int, AccessLevel], first: str) -> None:
    """An administrator's edit of the teacher's links, through the milestone 8 service."""
    with Session(s.engine) as session:
        update_teacher(session, teacher, first, "Shevchenko", links, False)


TARAS_LINKS = {
    "school": AccessLevel.WRITE,
    "gymnasium": AccessLevel.WRITE,
    "lyceum": AccessLevel.READ,
}


def taras_links(s: Scene, **changes: AccessLevel | None) -> dict[int, AccessLevel]:
    """Taras's links with `changes` applied by name (`None` removes one)."""
    ids = {"school": s.school, "gymnasium": s.gymnasium, "lyceum": s.lyceum}
    merged: dict[str, AccessLevel | None] = {**TARAS_LINKS, **changes}
    return {ids[name]: level for name, level in merged.items() if level is not None}


# ---------------------------------------------------------------------------------------------
# User story 2: the team answers page
# ---------------------------------------------------------------------------------------------


def test_only_the_teams_of_the_teachers_institutions_are_listed(scene: Scene) -> None:
    """US2-2, FR-005, FR-010: Comets (Write) and Lions (Read) are listed, Novas (unlinked) not."""
    page = listing(scene)
    assert groups(page) == [("Kyiv", 1, ["Comets"]), ("Lviv", 1, ["Lions"])]
    found = rows(page)
    assert found["Comets"].can_write and not found["Lions"].can_write
    assert (found["Comets"].institution_name, found["Lions"].institution_name) == (
        "School No. 5",
        "Lyceum No. 2",
    )
    assert page.linked
    assert groups(listing(scene, scene.iryna)) == [("Lviv", 1, ["Lions"])]
    assert not rows(listing(scene, scene.iryna))["Lions"].can_write


def test_twelve_listed_teams_in_two_regions_over_two_pages(engine: Engine, scene: Scene) -> None:
    """US2 story, FR-006, FR-007: of 30 teams in five regions, the 12 of Taras's institutions are
    listed, 9 in Kyiv and 3 in Lviv; Lviv continues on page 2 with its header and total again.
    Regions and teams by name ignoring case, ties by id."""
    for name in ("alpha", "Bravo", "charlie", "Delta"):
        add_competition_team(engine, scene.competition, make_team(engine, scene.school, name))
    for name in ("echo", "Foxtrot", "golf", "Hotel"):
        add_competition_team(engine, scene.competition, make_team(engine, scene.gymnasium, name))
    for name in ("Leo", "lynx"):
        add_competition_team(engine, scene.competition, make_team(engine, scene.lyceum, name))
    others = [
        make_institution(engine, f"Other {region}", region)
        for region in ("Odesa", "Dnipro", "Kharkiv")
    ]
    for index in range(17):
        institution = (others + [scene.unlinked])[index % 4]
        add_competition_team(
            engine, scene.competition, make_team(engine, institution, f"Other team {index}")
        )
    with Session(engine) as session:
        total = len(session.exec(select(CompetitionTeam)).all())
    assert total == 30
    first, second = listing(scene, p=1), listing(scene, p=2)
    assert first.paging.total == 12 and first.paging.number == 1
    assert groups(first) == [
        (
            "Kyiv",
            9,
            ["alpha", "Bravo", "charlie", "Comets", "Delta", "echo", "Foxtrot", "golf", "Hotel"],
        ),
        ("Lviv", 3, ["Leo"]),
    ]
    assert groups(second) == [("Lviv", 3, ["Lions", "lynx"])]
    with Session(engine) as session:
        assert team_answers.team_page_of(session, scene.taras, scene.competition, scene.lions) == 2
        assert team_answers.team_page_of(session, scene.taras, scene.competition, scene.comets) == 1
        assert team_answers.team_page_of(session, scene.taras, scene.competition, scene.novas) == 1
        assert team_answers.team_page_of(session, scene.taras, scene.competition, MISSING) == 1


def test_deleted_and_deactivated_teams_are_neither_listed_nor_counted(
    engine: Engine, scene: Scene
) -> None:
    """US2-2, FR-005, FR-007: a deleted team, a team of a deactivated institution and one of a
    deactivated region are not listed and not in the totals."""
    deleted = make_team(engine, scene.school, "Deleted", deleted=True)
    add_competition_team(engine, scene.competition, deleted)
    closed = make_institution(engine, "Closed School", "Kyiv")
    add_competition_team(engine, scene.competition, make_team(engine, closed, "Closed"))
    with Session(engine) as session:
        update_teacher(
            session,
            scene.taras,
            "Taras",
            "Shevchenko",
            {**taras_links(scene), closed: AccessLevel.WRITE},
            False,
        )
        set_institution_active(session, region_of(engine, closed), closed, False)
    assert groups(listing(scene)) == [("Kyiv", 1, ["Comets"]), ("Lviv", 1, ["Lions"])]
    with Session(engine) as session:
        set_region_active(session, region_of(engine, scene.lyceum), False)
    assert groups(listing(scene)) == [("Kyiv", 1, ["Comets"])]


def test_active_members_and_progress(engine: Engine, scene: Scene) -> None:
    """US2-5, US2-6, FR-008, FR-009: the team's own active members; "0 of 6", "3 of 6", and after
    an emptying "2 of 6"; a competition with no copies reads "0 of 0"."""
    school_class = make_class(engine, scene.school)
    make_member(engine, scene.comets, enrolled(engine, "s1@example.org", school_class))
    make_member(engine, scene.comets, enrolled(engine, "s2@example.org", school_class))
    found = rows(listing(scene))
    assert (found["Comets"].active_members, found["Comets"].answered) == (2, 0)
    assert (found["Comets"].questions, found["Lions"].questions) == (6, 6)
    for copy in scene.copies[:3]:
        save_team_answer(engine, scene.competition, scene.comets, copy, "NaCl")
    assert rows(listing(scene))["Comets"].answered == 3
    save(scene, {scene.copies[0]: ""})
    assert rows(listing(scene))["Comets"].answered == 2
    assert rows(listing(scene))["Lions"].answered == 0
    winter = make_competition(engine, scene.chemistry, "Winter round", starts_at=STARTED)
    add_competition_team(engine, winter, scene.comets)
    (row,) = rows(listing(scene, competition=winter)).values()
    assert (row.answered, row.questions) == (0, 0)


def test_answers_of_another_competition_are_not_counted(engine: Engine, scene: Scene) -> None:
    other = make_competition(engine, scene.chemistry, "Other round", starts_at=STARTED)
    copy = add_competition_question(engine, other, make_question(engine, scene.chemistry))
    add_competition_team(engine, other, scene.comets)
    save_team_answer(engine, other, scene.comets, copy, "Elsewhere")
    assert rows(listing(scene))["Comets"].answered == 0


def test_a_teacher_linked_to_nothing_available(engine: Engine, scene: Scene) -> None:
    """US9-1, FR-012: no link at all, and only a link to a deactivated institution."""
    nobody = unlinked_teacher(engine, "nobody@example.org")
    page = listing(scene, nobody)
    assert (page.linked, page.groups) == (False, [])
    closed = make_institution(engine, "Closed School", "Kyiv")
    nadiia = make_teacher(
        engine, scene.settings, email="nadiia@example.org", institutions={closed: AccessLevel.WRITE}
    )
    with Session(engine) as session:
        set_institution_active(session, region_of(engine, closed), closed, False)
    assert not listing(scene, nadiia).linked


def test_a_teacher_whose_institutions_have_no_team_in_it(engine: Engine, scene: Scene) -> None:
    """US9-2: linked to an available institution, none of whose teams is in the competition."""
    other = make_institution(engine, "School No. 9", "Odesa")
    make_team(engine, other, "Outsiders")
    bohdan = make_teacher(
        engine, scene.settings, email="bohdan@example.org", institutions={other: AccessLevel.WRITE}
    )
    page = listing(scene, bohdan)
    assert (page.linked, page.groups) == (True, [])


def test_links_are_read_on_every_call(scene: Scene) -> None:
    """FR-013, US8-7: lowering a link to Read takes Write away at once; removing it hides the
    institution's teams at once."""
    set_link(scene, scene.taras, taras_links(scene, school=AccessLevel.READ), "Taras")
    assert not rows(listing(scene))["Comets"].can_write
    set_link(scene, scene.taras, taras_links(scene, school=None), "Taras")
    assert "Comets" not in rows(listing(scene))


def test_count_answered_needs_no_query_for_no_ids(engine: Engine, scene: Scene) -> None:
    with Session(engine) as session:
        assert team_answers.count_answered(session, scene.competition, []) == {}


# ---------------------------------------------------------------------------------------------
# User story 1: the sheet and the save
# ---------------------------------------------------------------------------------------------


def test_the_sheet_lists_every_copy_in_order(engine: Engine, scene: Scene) -> None:
    """US1-2, US1-4, FR-015: the copies in the order of adding, numbered 1–6, with the copy's
    text after the bank question is edited, and a question deleted from the bank like any other;
    never a reference answer."""
    with Session(engine) as session:
        first = session.get(CompetitionQuestion, scene.copies[0])
        second = session.get(CompetitionQuestion, scene.copies[1])
        assert first is not None and second is not None
        bank_manager = manager(scene)
        update_question(session, bank_manager, first.question_id, "Edited?", "Edited.")
        delete_question(session, bank_manager, second.question_id)
    found = sheet(scene)
    assert (found.team_id, found.team_name, found.institution_name) == (
        scene.comets,
        "Comets",
        "School No. 5",
    )
    assert [(q.competition_question_id, q.number, q.text, q.answer) for q in found.questions] == [
        (copy, n, f"Question {n}?", "") for n, copy in enumerate(scene.copies, start=1)
    ]
    assert not any(hasattr(q, "reference_answer") for q in found.questions)
    assert all("Ref" not in q.text for q in found.questions)


def test_saving_changing_and_emptying(engine: Engine, scene: Scene) -> None:
    """US1-5, US1-6, FR-017, FR-024: three answers at once; then one changed, one emptied and a
    new one, all by one save; the sheet shows them."""
    first, second, third, fourth = scene.copies[:4]
    result = save(scene, {first: "Sodium", second: "Water", third: "Salt"})
    assert result == SaveResult(answered=3, changed=3)
    assert answers_of(engine, scene.competition, scene.comets) == {
        first: "Sodium",
        second: "Water",
        third: "Salt",
    }
    result = save(scene, {first: "Sodium chloride", second: "", third: "Salt", fourth: "Ice"})
    assert result == SaveResult(answered=3, changed=3)
    assert answers_of(engine, scene.competition, scene.comets) == {
        first: "Sodium chloride",
        third: "Salt",
        fourth: "Ice",
    }
    shown = {q.competition_question_id: q.answer for q in sheet(scene).questions}
    assert shown[first] == "Sodium chloride" and shown[second] == ""


def test_answers_are_trimmed_with_inner_line_breaks_kept(engine: Engine, scene: Scene) -> None:
    """US1-7, US1-8, FR-018: trimmed, line endings as `\\n`; spaces and line breaks only are not
    answered and store no row."""
    first, second = scene.copies[:2]
    result = save(scene, {first: "  Sodium\r\nchloride \r\n", second: " \r\n \n "})
    assert result == SaveResult(answered=1, changed=1)
    assert answers_of(engine, scene.competition, scene.comets) == {first: "Sodium\nchloride"}


def test_an_unchanged_save_writes_nothing(engine: Engine, scene: Scene) -> None:
    """Spec Edge Cases: saving with nothing changed is accepted; nothing is written."""
    first, second = scene.copies[:2]
    save(scene, {first: "Sodium"})
    assert save(scene, {first: " Sodium ", second: ""}) == SaveResult(answered=1, changed=0)
    assert answers_of(engine, scene.competition, scene.comets) == {first: "Sodium"}


def test_a_question_left_out_keeps_its_answer(engine: Engine, scene: Scene) -> None:
    """Spec Assumptions: a save that does not name a question leaves its answer as it is."""
    first, second = scene.copies[:2]
    save(scene, {first: "Sodium", second: "Water"})
    assert save(scene, {first: "Salt"}) == SaveResult(answered=2, changed=1)
    assert answers_of(engine, scene.competition, scene.comets) == {first: "Salt", second: "Water"}
    assert save(scene, {}) == SaveResult(answered=2, changed=0)


# ---------------------------------------------------------------------------------------------
# User story 6: answers that are too long
# ---------------------------------------------------------------------------------------------


def test_a_too_long_answer_saves_nothing(engine: Engine, scene: Scene) -> None:
    """US6-1, FR-019: 2,001 characters after trimming among changes to questions 1 and 5: nothing
    is saved, the earlier answers included."""
    q1, _, _, q4, q5, _ = scene.copies
    save_team_answer(engine, scene.competition, scene.comets, q1, "Old")
    before = snapshot(engine)
    with pytest.raises(InvalidAnswers) as refused:
        save(scene, {q1: "New", q4: " " + "x" * 2001 + " ", q5: "Five"})
    assert refused.value.errors == {q4: TOO_LONG.format(n=4)}
    assert snapshot(engine) == before


def test_several_too_long_answers_are_all_reported_in_question_order(scene: Scene) -> None:
    """US6-3: each error keyed by its copy, in the order of the questions."""
    q1, q2, q3 = scene.copies[:3]
    with pytest.raises(InvalidAnswers) as refused:
        save(scene, {q3: "y" * 2001, q1: "x" * 2001, q2: "fine"})
    assert list(refused.value.errors.items()) == [
        (q1, TOO_LONG.format(n=1)),
        (q3, TOO_LONG.format(n=3)),
    ]


def test_exactly_2000_characters_after_trimming_are_saved(engine: Engine, scene: Scene) -> None:
    """US6-4, spec Edge Cases: 2,001 before trimming, 2,000 after."""
    q1 = scene.copies[0]
    assert save(scene, {q1: "x" * 2000 + "\n"}).answered == 1
    assert answers_of(engine, scene.competition, scene.comets) == {q1: "x" * 2000}


def test_a_null_character_is_refused(engine: Engine, scene: Scene) -> None:
    with pytest.raises(InvalidAnswers) as refused:
        save(scene, {scene.copies[2]: "a\x00b"})
    assert refused.value.errors == {
        scene.copies[2]: "Answer to question 3 cannot contain a null character."
    }
    assert snapshot(engine) == []


def test_the_length_is_checked_only_after_the_access(scene: Scene) -> None:
    """FR-025: a Read-access teacher with a too-long answer is denied, not told the length."""
    with pytest.raises(AnswersDenied):
        save(scene, {scene.copies[0]: "x" * 2001}, team=scene.lions)


# ---------------------------------------------------------------------------------------------
# User story 7: only while In progress
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "seed"),
    [
        (CompetitionStatus.UPCOMING, {"starts_at": LATER}),
        (CompetitionStatus.CANCELLED, {"starts_at": STARTED, "cancelled": True}),
        (CompetitionStatus.FINISHED, {"starts_at": STARTED, "stopped": True}),
    ],
)
def test_a_competition_that_is_not_in_progress_refuses_the_save(
    engine: Engine, scene: Scene, status: CompetitionStatus, seed: dict[str, Any]
) -> None:
    """US7-1, US7-2, FR-026, SC-003: nothing changes, the seeded answers included."""
    closed = make_competition(engine, scene.chemistry, "Closed round", **seed)
    copy = add_competition_question(engine, closed, make_question(engine, scene.chemistry))
    add_competition_team(engine, closed, scene.comets)
    save_team_answer(engine, closed, scene.comets, copy, "Kept")
    before = snapshot(engine)
    with pytest.raises(AnswersClosed) as refused:
        save(scene, {copy: "Changed"}, competition=closed)
    assert refused.value.status is status
    assert snapshot(engine) == before


def test_the_start_minute_itself_is_in_progress(
    engine: Engine, scene: Scene, clock: Callable[[timedelta], datetime]
) -> None:
    """US7-5: once the start passes, the same save is accepted."""
    autumn = make_competition(
        engine, scene.chemistry, "Autumn round", starts_at=NOW + timedelta(hours=1)
    )
    copy = add_competition_question(engine, autumn, make_question(engine, scene.chemistry))
    add_competition_team(engine, autumn, scene.comets)
    with pytest.raises(AnswersClosed):
        save(scene, {copy: "Early"}, competition=autumn)
    clock(timedelta(hours=1))
    assert save(scene, {copy: "On time"}, competition=autumn).answered == 1


def test_the_competition_and_the_subject_come_before_the_status(
    engine: Engine, scene: Scene
) -> None:
    """FR-025 step 2: an unknown competition, another subject's and a hidden one are not found."""
    copy = scene.copies[0]
    with pytest.raises(CompetitionNotFound):
        save(scene, {copy: "x"}, competition=MISSING)
    with pytest.raises(CompetitionNotFound):
        save(scene, {copy: "x"}, subject=scene.physics)
    with Session(engine) as session:
        set_subject_active(session, scene.chemistry, False)
    with pytest.raises(CompetitionNotFound):
        save(scene, {copy: "x"})
    assert snapshot(engine) == []


def test_the_status_comes_before_the_team_and_the_access(engine: Engine, scene: Scene) -> None:
    """US8-8: a cancelled competition with an unknown team, or a team of an unlinked institution,
    is the refusal."""
    with Session(engine) as session:
        cancel_competition(session, manager(scene), scene.competition, scene.chemistry, None)
    for team in (MISSING, scene.novas):
        with pytest.raises(AnswersClosed):
            save(scene, {scene.copies[0]: "x"}, team=team)


def test_a_save_racing_a_cancellation(engine: Engine, database_url: str, scene: Scene) -> None:
    """FR-026, SC-003: either the save commits first and the cancellation keeps its answers, or
    the cancellation commits first and the save is refused with nothing stored."""
    postgresql_only(database_url)
    canceller = manager(scene)
    for attempt in range(3):
        competition = make_competition(
            engine, scene.chemistry, f"Race {attempt}", starts_at=STARTED
        )
        race_copy = add_competition_question(
            engine, competition, make_question(engine, scene.chemistry)
        )
        add_competition_team(engine, competition, scene.comets)
        outcomes = race(
            engine,
            lambda session, c=competition, q=race_copy: team_answers.save_answers(
                session, scene.taras, c, scene.chemistry, scene.comets, {q: "Raced"}
            ),
            lambda session, c=competition: cancel_competition(
                session, canceller, c, scene.chemistry, None
            ),
        )
        assert outcomes[1] == "ok"
        assert outcomes[0] in ("ok", "AnswersClosed")
        stored = answers_of(engine, competition, scene.comets)
        assert stored == ({race_copy: "Raced"} if outcomes[0] == "ok" else {})


def test_saves_of_two_teams_of_one_competition_do_not_wait(
    engine: Engine, database_url: str, scene: Scene
) -> None:
    """Research R3: a save holding Comets's link does not hold up a save of another team."""
    postgresql_only(database_url)
    gymnasium_team = make_team(engine, scene.gymnasium, "Stars")
    add_competition_team(engine, scene.competition, gymnasium_team)
    with Session(engine) as holding:
        lock_competition(holding, scene.competition, scene.chemistry, share=True)
        team_answers._lock_team(holding, scene.competition, scene.comets)
        with Session(engine) as other:
            other.execute(text("SET LOCAL lock_timeout = '300ms'"))
            team_answers.save_answers(
                other,
                scene.taras,
                scene.competition,
                scene.chemistry,
                gymnasium_team,
                {scene.copies[0]: "Not held up"},
            )
        with Session(engine) as same:
            same.execute(text("SET LOCAL lock_timeout = '300ms'"))
            with pytest.raises(OperationalError, match="lock timeout"):
                team_answers.save_answers(
                    same,
                    scene.taras,
                    scene.competition,
                    scene.chemistry,
                    scene.comets,
                    {scene.copies[0]: "Queued"},
                )
        holding.rollback()
    assert answers_of(engine, scene.competition, gymnasium_team) == {scene.copies[0]: "Not held up"}
    assert answers_of(engine, scene.competition, scene.comets) == {}


# ---------------------------------------------------------------------------------------------
# User story 8: the team, the questions and the access
# ---------------------------------------------------------------------------------------------


def test_unknown_deleted_and_foreign_teams_are_not_found(engine: Engine, scene: Scene) -> None:
    """US8-3, FR-025 step 4: on the sheet and the save, before the access; nothing is stored."""
    deleted = make_team(engine, scene.lyceum, "Gone", deleted=True)
    add_competition_team(engine, scene.competition, deleted)
    outside = make_team(engine, scene.school, "Outside")
    closed = make_institution(engine, "Closed School", "Kyiv")
    closed_team = make_team(engine, closed, "Closed")
    add_competition_team(engine, scene.competition, closed_team)
    set_link(scene, scene.taras, {**taras_links(scene), closed: AccessLevel.WRITE}, "Taras")
    with Session(engine) as session:
        set_institution_active(session, region_of(engine, closed), closed, False)
    for team in (MISSING, deleted, outside, closed_team):
        with pytest.raises(TeamNotFound):
            sheet(scene, team=team)
        with pytest.raises(TeamNotFound):
            save(scene, {scene.copies[0]: "x"}, team=team)
    assert snapshot(engine) == []


def test_a_team_of_a_deactivated_region_is_not_found(engine: Engine, scene: Scene) -> None:
    with Session(engine) as session:
        set_region_active(session, region_of(engine, scene.school), False)
    with pytest.raises(TeamNotFound):
        sheet(scene)
    with pytest.raises(TeamNotFound):
        save(scene, {scene.copies[0]: "x"})


def test_questions_of_another_competition_are_not_found(engine: Engine, scene: Scene) -> None:
    """US8-4, FR-025 step 4: another competition's copy, an unknown id; nothing is stored."""
    other = make_competition(engine, scene.chemistry, "Other round", starts_at=STARTED)
    foreign = add_competition_question(engine, other, make_question(engine, scene.chemistry))
    for question in (foreign, MISSING):
        with pytest.raises(QuestionNotFound):
            save(scene, {scene.copies[0]: "Fine", question: "x"})
    assert snapshot(engine) == []


def test_the_questions_come_before_the_access(scene: Scene) -> None:
    with pytest.raises(QuestionNotFound):
        save(scene, {MISSING: "x"}, team=scene.lions)


def test_no_write_access_is_denied(engine: Engine, scene: Scene) -> None:
    """US3-4, US8-5, FR-025 step 5: a Read link and no link, on the sheet and the save; the
    answers saved before stay."""
    save_team_answer(engine, scene.competition, scene.lions, scene.copies[0], "Kept")
    save_team_answer(engine, scene.competition, scene.novas, scene.copies[0], "Kept")
    before = snapshot(engine)
    for teacher, team in (
        (scene.taras, scene.lions),
        (scene.iryna, scene.lions),
        (scene.taras, scene.novas),
    ):
        with pytest.raises(AnswersDenied):
            sheet(scene, teacher=teacher, team=team)
        with pytest.raises(AnswersDenied):
            save(scene, {scene.copies[0]: "Changed"}, teacher=teacher, team=team)
    assert snapshot(engine) == before


def test_a_link_lowered_or_removed_while_the_sheet_is_open(engine: Engine, scene: Scene) -> None:
    """US8-6, FR-027: the sheet opened, then the link lowered or removed: the save is denied and
    the answers saved before stay."""
    save(scene, {scene.copies[0]: "Before"})
    for change in (AccessLevel.READ, None):
        sheet(scene)
        set_link(scene, scene.taras, taras_links(scene, school=change), "Taras")
        with pytest.raises(AnswersDenied):
            save(scene, {scene.copies[0]: "After"})
        assert answers_of(engine, scene.competition, scene.comets) == {scene.copies[0]: "Before"}
        set_link(scene, scene.taras, taras_links(scene), "Taras")


@pytest.mark.parametrize("level", ["institution", "region"])
def test_deactivation_keeps_the_answers_and_reactivation_shows_them_again(
    engine: Engine, scene: Scene, level: str
) -> None:
    """FR-029, spec Edge Cases (G1): while the team's institution or region is deactivated, the
    rows stay exactly as they were, and the sheet and a save (changed, emptied and new answers)
    are not found; after reactivation the team is listed with the same progress and texts."""
    q1, q2, q3, q4 = scene.copies[:4]
    for copy, answer in ((q1, "One"), (q2, "Two"), (q3, "Three")):
        save_team_answer(engine, scene.competition, scene.comets, copy, answer)
    finished = make_competition(
        engine, scene.chemistry, "Summer round", starts_at=STARTED, stopped=True
    )
    finished_copy = add_competition_question(
        engine, finished, make_question(engine, scene.chemistry)
    )
    add_competition_team(engine, finished, scene.comets)
    save_team_answer(engine, finished, scene.comets, finished_copy, "Finished")
    before = snapshot(engine)
    region = region_of(engine, scene.school)

    def set_active(active: bool) -> None:
        with Session(engine) as session:
            if level == "institution":
                set_institution_active(session, region, scene.school, active)
            else:
                set_region_active(session, region, active)

    set_active(False)
    assert snapshot(engine) == before
    with pytest.raises(TeamNotFound):
        sheet(scene)
    with pytest.raises(TeamNotFound):
        save(scene, {q1: "Changed", q2: "", q4: "New"})
    assert snapshot(engine) == before
    assert "Comets" not in rows(listing(scene))
    set_active(True)
    assert snapshot(engine) == before
    assert rows(listing(scene))["Comets"].answered == 3
    assert [q.answer for q in sheet(scene).questions] == ["One", "Two", "Three", "", "", ""]


def test_a_save_racing_a_lowered_link(engine: Engine, database_url: str, scene: Scene) -> None:
    """FR-027 under concurrency: the save commits first, or it is denied with nothing stored."""
    postgresql_only(database_url)
    for level in (AccessLevel.READ, None):
        set_link(scene, scene.taras, taras_links(scene), "Taras")
        before = snapshot(engine)
        outcomes = race(
            engine,
            lambda session, change=level: team_answers.save_answers(
                session,
                scene.taras,
                scene.competition,
                scene.chemistry,
                scene.comets,
                {scene.copies[0]: f"Raced {change}"},
            ),
            lambda session, change=level: update_teacher(
                session,
                scene.taras,
                "Taras",
                "Shevchenko",
                taras_links(scene, school=change),
                False,
            ),
        )
        assert outcomes[1] == "ok"
        assert outcomes[0] in ("ok", "AnswersDenied")
        if outcomes[0] == "AnswersDenied":
            assert snapshot(engine) == before


def test_a_save_racing_the_deactivation_of_the_institution(
    engine: Engine, database_url: str, scene: Scene
) -> None:
    """FR-029 under concurrency: the save commits first and the deactivation keeps its rows, or
    the deactivation commits first and the save stores nothing."""
    postgresql_only(database_url)
    save_team_answer(engine, scene.competition, scene.comets, scene.copies[1], "Before")
    before = snapshot(engine)
    region = region_of(engine, scene.school)
    outcomes = race(
        engine,
        lambda session: team_answers.save_answers(
            session,
            scene.taras,
            scene.competition,
            scene.chemistry,
            scene.comets,
            {scene.copies[0]: "Raced"},
        ),
        lambda session: set_institution_active(session, region, scene.school, False),
    )
    assert outcomes[1] == "ok"
    assert outcomes[0] in ("ok", "TeamNotFound", "AnswersDenied")
    stored = answers_of(engine, scene.competition, scene.comets)
    if outcomes[0] == "ok":
        assert stored == {scene.copies[0]: "Raced", scene.copies[1]: "Before"}
    else:
        assert snapshot(engine) == before


def test_the_session_is_usable_after_every_refusal(engine: Engine, scene: Scene) -> None:
    with Session(engine) as session:
        for team, answers, error in (
            (MISSING, {}, TeamNotFound),
            (scene.comets, {MISSING: "x"}, QuestionNotFound),
            (scene.lions, {}, AnswersDenied),
            (scene.comets, {scene.copies[0]: "x" * 2001}, InvalidAnswers),
        ):
            with pytest.raises(error):
                team_answers.save_answers(
                    session, scene.taras, scene.competition, scene.chemistry, team, answers
                )
            assert session.exec(select(TeamAnswer)).all() == []


# ---------------------------------------------------------------------------------------------
# User story 10: the last save wins
# ---------------------------------------------------------------------------------------------


def test_the_later_save_replaces_every_answer_of_the_earlier(engine: Engine, scene: Scene) -> None:
    """US10-1, FR-024: Oksana answers question 2 (with question 1 as stored); Taras's later save,
    from a page that did not show her answer, empties questions 1 and 2 and answers question 3."""
    q1, q2, q3 = scene.copies[:3]
    save_team_answer(engine, scene.competition, scene.comets, q1, "Old")
    taras_page = {q.competition_question_id: q.answer for q in sheet(scene).questions}
    save(scene, {q1: "Old", q2: "Oksana's", q3: ""}, teacher=scene.oksana)
    assert taras_page[q2] == ""
    save(scene, {q1: "", q2: taras_page[q2], q3: "Taras's"})
    assert answers_of(engine, scene.competition, scene.comets) == {q3: "Taras's"}


def test_two_saves_at_the_same_moment_never_mix(
    engine: Engine, database_url: str, scene: Scene
) -> None:
    """US10-2, FR-024, SC-006: two full sheets of the same team saved at once: the stored answers
    are exactly one of the two, never a mix."""
    postgresql_only(database_url)
    first = {copy: f"First {n}" for n, copy in enumerate(scene.copies)}
    second = {copy: ("" if n % 2 else f"Second {n}") for n, copy in enumerate(scene.copies)}
    expected = [{k: v for k, v in sheet_.items() if v} for sheet_ in (first, second)]
    for _ in range(4):
        outcomes = race(
            engine,
            lambda session: team_answers.save_answers(
                session, scene.taras, scene.competition, scene.chemistry, scene.comets, first
            ),
            lambda session: team_answers.save_answers(
                session, scene.oksana, scene.competition, scene.chemistry, scene.comets, second
            ),
        )
        assert outcomes == ["ok", "ok"]
        assert answers_of(engine, scene.competition, scene.comets) in expected


# ---------------------------------------------------------------------------------------------
# Logging (FR-031)
# ---------------------------------------------------------------------------------------------


def test_a_save_logs_ids_and_counts_only(
    engine: Engine, scene: Scene, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    q1, q2 = scene.copies[:2]
    save(scene, {q1: "Sodium chloride", q2: "Secret answer"})
    save(scene, {q1: "Sodium chloride", q2: "Secret answer"})
    saved = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Team answers")]
    assert saved == [
        f"Team answers saved: competition={scene.competition} team={scene.comets}"
        " answered=2 changed=2",
        f"Team answers saved: competition={scene.competition} team={scene.comets}"
        " answered=2 changed=0",
    ]
    caplog.clear()
    for answers, team in (
        ({MISSING: "x"}, scene.comets),
        ({q1: "x"}, scene.lions),
        ({q1: "y" * 2001}, scene.comets),
    ):
        with pytest.raises((QuestionNotFound, AnswersDenied, InvalidAnswers)):
            save(scene, answers, team=team)
    assert [r for r in caplog.records if r.getMessage().startswith("Team answers")] == []
    for record in caplog.records:
        message = record.getMessage()
        for secret in (
            "Spring round",
            "Comets",
            "School No. 5",
            "Question 1?",
            "Sodium",
            "Secret answer",
            "taras@example.org",
            "Taras",
        ):
            assert secret not in message, (secret, message)
