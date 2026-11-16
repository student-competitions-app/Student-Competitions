"""Ukrainian names through the services and on the pages (specs/012.5-ukrainian-localisation US6,
FR-052–FR-056).

A second name that differs from an existing one only by the spelling of its apostrophe is the same
name, and is refused with the existing duplicate message, in every scope a name is unique in. The
name is stored exactly as typed. Lists follow the Ukrainian alphabet in both languages.

Every case runs on both engines.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.models import AccessLevel
from app.services.classes import DuplicateClassName, create_class
from app.services.competitions import DuplicateCompetitionName, create_competition
from app.services.institutions import (
    DuplicateInstitutionName,
    create_institution,
    list_institutions,
)
from app.services.regions import DuplicateRegionName, create_region, list_regions
from app.services.students import list_students
from app.services.subjects import DuplicateSubjectName, create_subject, list_subjects
from app.services.teams import DuplicateTeamName, create_team, list_teams
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ClientAs,
    enrol_student,
    make_class,
    make_institution,
    make_subject,
    make_teacher,
)

TYPED = "Мар'яна"
"""As people type it on most keyboards: U+0027."""
OTHER_SPELLINGS = ["Мар’яна", "Марʼяна", "Мар‘яна", "Мар`яна"]
OLENA = "olena@example.org"
ORDER = ["Гончаренко", "Ґудзь", "Євтушенко", "Іваненко", "Їжакевич", "Ющенко", "Яковенко"]
SHUFFLED = ["Яковенко", "Ґудзь", "Іваненко", "Гончаренко", "Ющенко", "Євтушенко", "Їжакевич"]


@pytest.fixture
def teacher(client: TestClient) -> tuple[int, int]:
    """A teacher with Write access to one institution and the competitions setting; the ids of
    the teacher and the institution."""
    institution = make_institution(app.state.engine, "Ліцей", "Київ")
    teacher_id = make_teacher(
        app.state.engine,
        app.state.settings,
        email=OLENA,
        institutions={institution: AccessLevel.WRITE},
        can_manage=True,
    )
    return teacher_id, institution


@pytest.mark.parametrize("spelling", OTHER_SPELLINGS)
def test_subjects_and_regions(client: TestClient, spelling: str) -> None:
    with Session(app.state.engine) as session:
        subject = create_subject(session, TYPED)
        assert subject.name == TYPED
        with pytest.raises(DuplicateSubjectName) as refused:
            create_subject(session, spelling)
        assert str(refused.value.message) == f"A subject named “{TYPED}” already exists."
        region = create_region(session, TYPED)
        assert region.name == TYPED
        with pytest.raises(DuplicateRegionName):
            create_region(session, spelling)


@pytest.mark.parametrize("spelling", OTHER_SPELLINGS)
def test_institutions_within_a_region(client: TestClient, spelling: str) -> None:
    with Session(app.state.engine) as session:
        kyiv = create_region(session, "Київ")
        lviv = create_region(session, "Львів")
        assert kyiv.id is not None and lviv.id is not None
        create_institution(session, kyiv.id, TYPED)
        with pytest.raises(DuplicateInstitutionName):
            create_institution(session, kyiv.id, spelling)
        assert create_institution(session, lviv.id, spelling).name == spelling


@pytest.mark.parametrize("spelling", OTHER_SPELLINGS)
def test_classes_teams_and_competitions(teacher: tuple[int, int], spelling: str) -> None:
    teacher_id, institution = teacher
    subject = make_subject(app.state.engine, "Фізика")
    starts = datetime(2099, 3, 14, 8, 0, tzinfo=UTC)
    with Session(app.state.engine) as session:
        assert create_class(session, teacher_id, institution, TYPED, "2").name == TYPED
        with pytest.raises(DuplicateClassName):
            create_class(session, teacher_id, institution, spelling, "2")
    with Session(app.state.engine) as session:
        assert create_team(session, teacher_id, institution, TYPED).name == TYPED
        with pytest.raises(DuplicateTeamName):
            create_team(session, teacher_id, institution, spelling)
    with Session(app.state.engine) as session:
        assert create_competition(session, teacher_id, subject, TYPED, starts).name == TYPED
        with pytest.raises(DuplicateCompetitionName):
            create_competition(session, teacher_id, subject, spelling, starts)


def test_lists_follow_the_ukrainian_alphabet(teacher: tuple[int, int]) -> None:
    teacher_id, institution = teacher
    school_class = make_class(app.state.engine, institution, "КН-21", 2)
    with Session(app.state.engine) as session:
        for name in SHUFFLED:
            create_subject(session, name)
            create_region(session, name)
            create_team(session, teacher_id, institution, name)
        region = create_region(session, "Область")
        region_id = region.id
        assert region_id is not None
        for name in SHUFFLED:
            create_institution(session, region_id, name)
    for number, last in enumerate(SHUFFLED):
        enrol_student(
            app.state.engine,
            app.state.settings,
            email=f"s{number}@example.org",
            class_id=school_class,
            inviter_email=OLENA,
            last=last,
        )
    with Session(app.state.engine) as session:
        assert [s.name for s in list_subjects(session)] == ORDER
        assert [r.name for r in list_regions(session) if r.name in ORDER] == ORDER
        assert [i.name for i in list_institutions(session, region_id)] == ORDER
        assert [t.name for t in list_teams(session, institution)] == ORDER
        assert [s.last_name for s in list_students(session, school_class)] == ORDER


@pytest.mark.parametrize("language", ["uk", "en"])
def test_the_pages_list_in_the_same_order_in_either_language(
    client_as: ClientAs, language: str
) -> None:
    for name in SHUFFLED:
        make_institution(app.state.engine, name, "Область")
    admin = client_as(ADMIN_EMAIL)
    admin.cookies.set("sc_lang", language)
    with Session(app.state.engine) as session:
        (region,) = [r for r in list_regions(session) if r.name == "Область"]
    body = admin.get(f"/admin/institutions/regions/{region.id}").text
    names = [row[next(iter(row))] for row in html.table_rows(body)]
    assert names == ORDER
