"""The bilingual consent texts (specs/012.5-ukrainian-localisation US5, FR-044–FR-047; research
R11, contracts/components.md §7).

Whatever the page's language, the invitation page and the profile show the Ukrainian part first,
under «Українською» and marked `lang="uk"`, then the English part, under "English" and marked
`lang="en"`; the rest of the page follows the chosen language. Accepting in either language records
the same text, version 1.

Every database case runs on both engines.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models import AccessLevel, ConsentRecord, ConsentText
from app.services.consent import ConsentParts, consent_parts
from tests import html
from tests.conftest import (
    TEACHER_EMAIL,
    ClientAs,
    invite,
    invite_student,
    make_class,
    make_institution,
    make_teacher,
)

OLENA = "olena@example.org"
TARAS = "taras@example.org"
WRITER = "writer@example.org"


def consent_sections(body: str) -> list[tuple[str, str, str]]:
    """`(lang, heading, first paragraph)` of each part of the consent text, in page order."""
    found = []
    for section in html.parse(body).iter():
        if "consent-parts" not in section.classes():
            continue
        for part in section.find_all("div"):
            (heading,) = part.find_all("h3")
            paragraphs = part.find_all("p")
            found.append((part.attrs["lang"], heading.text(), paragraphs[0].text()))
    return found


def assert_bilingual(body: str) -> None:
    sections = consent_sections(body)
    assert [(lang, heading) for lang, heading, _ in sections] == [
        ("uk", "Українською"),
        ("en", "English"),
    ]
    assert sections[0][2].startswith("Натискаючи «Я погоджуюся»")
    assert sections[1][2].startswith('By pressing "I agree"')


def teacher_invitation() -> str:
    school = make_institution(app.state.engine, "Kyiv Lyceum")
    token = invite(
        app.state.engine, app.state.settings, email=OLENA, institutions={school: AccessLevel.READ}
    )
    return f"/invitations/{token}"


def student_invitation() -> str:
    engine = app.state.engine
    school = make_institution(engine, "Kyiv Polytechnic Institute")
    make_teacher(
        engine, app.state.settings, email="t@example.org", institutions={school: AccessLevel.WRITE}
    )
    school_class = make_class(engine, school, "KN-21", 2)
    token = invite_student(
        engine,
        app.state.settings,
        email=TARAS,
        class_id=school_class,
        inviter_email="t@example.org",
    )
    return f"/invitations/{token}"


@pytest.mark.parametrize("language", ["uk", "en"])
@pytest.mark.parametrize("make_link", [teacher_invitation, student_invitation])
def test_the_invitation_page_shows_both_parts_in_order(
    client: TestClient, language: str, make_link: object
) -> None:
    assert callable(make_link)
    link = make_link()
    client.cookies.set("sc_lang", language)
    body = client.get(link).text
    assert html.html_attrs(body)["lang"] == language
    assert_bilingual(body)
    agree = "Я погоджуюся" if language == "uk" else "I agree"
    assert agree in [b.text for f in html.forms(body, "main") for b in f.buttons]


@pytest.mark.parametrize("language", ["uk", "en"])
def test_accepting_in_either_language_records_version_1(
    client: TestClient, client_as: ClientAs, language: str
) -> None:
    link = teacher_invitation()
    client.cookies.set("sc_lang", language)
    page = client.get(link).text
    (form,) = [f for f in html.forms(page, "main") if f.action in ("", link)]
    text_id = next(i.value for i in form.inputs if i.name == "consent_text_id")
    response = client.post(link, data={"consent_text_id": text_id}, follow_redirects=False)
    assert response.status_code == 303
    with Session(app.state.engine) as session:
        text = session.exec(
            select(ConsentText).where(ConsentText.role == "teacher", ConsentText.version == 1)
        ).one()
        records = session.exec(select(ConsentRecord)).all()
    assert [r.consent_text_id for r in records] == [text.id]
    assert text.version == 1
    browser = client_as(OLENA)
    for profile_language in ("uk", "en"):
        browser.cookies.set("sc_lang", profile_language)
        body = browser.get("/profile").text
        assert html.html_attrs(body)["lang"] == profile_language
        assert_bilingual(body)


def test_consent_parts() -> None:
    text = "Українською\n\nПерший.\n\nДругий.\n\nEnglish\n\nFirst.\n\nSecond."
    assert consent_parts(text) == ConsentParts(("Перший.", "Другий."), ("First.", "Second."))


def test_a_text_with_no_english_paragraph_has_no_parts() -> None:
    assert consent_parts("By pressing.\n\nEnglish is spoken here.") is None


def test_the_cast_teacher_has_no_consent_to_show(client_as: ClientAs) -> None:
    """A profile with no record shows no consent section at all."""
    body = client_as(TEACHER_EMAIL).get("/profile").text
    assert consent_sections(body) == []
