"""The languages of the emails (specs/012.5-ukrainian-localisation US4, FR-019, FR-039,
FR-041–FR-043; research R10).

- The sign-in code and the deletion link are written in the language of the request that sends
  them: the browser's choice, else the deployment's default.
- An invitation is written in Ukrainian then English, whoever sends it and whatever language they
  use, since the invited person has not chosen one yet.
- Every time in an email is Kyiv time, labelled in its language.

Every case runs on both engines.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import AccessLevel
from app.services.email import LANGUAGE_SEPARATOR, EmailMessage
from tests.conftest import (
    ADMIN_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
    invite_and_accept,
    make_class,
    make_institution,
    make_teacher,
)
from tests.integration.test_teacher_invitation import invite_form

UKRAINIAN_NAME = "Студентські змагання"
ENGLISH_NAME = "Student Competitions"
OLENA = "olena@example.org"
TARAS = "taras@example.org"
CODE = re.compile(r"\b(\d{6})\b")


def parts(message: EmailMessage) -> tuple[str, str, str, str]:
    """The Ukrainian and English subjects and texts of a bilingual email."""
    uk_subject, en_subject = message.subject.split(" / ")
    uk_text, en_text = message.text.split(LANGUAGE_SEPARATOR)
    return uk_subject, en_subject, uk_text, en_text


# ---------------------------------------------------------------------------------------------
# The sign-in code and the deletion link: the request's language (FR-041)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("cookie", "ukrainian"), [("uk", True), ("en", False), (None, True)])
def test_the_sign_in_code_is_in_the_request_s_language(
    ukrainian_default: None,
    client: TestClient,
    outbox: list[EmailMessage],
    cookie: str | None,
    ukrainian: bool,
) -> None:
    if cookie is not None:
        client.cookies.set("sc_lang", cookie)
    client.post("/login", data={"email": TEACHER_EMAIL, "next": "/"})
    [message] = outbox
    code = CODE.search(message.text)
    assert code is not None
    assert code.group(1) not in message.subject
    assert not any(character.isdigit() for character in message.subject)
    if ukrainian:
        assert UKRAINIAN_NAME in message.subject and UKRAINIAN_NAME in message.text
        assert "Your" not in message.text
    else:
        assert message.subject == f"Your {ENGLISH_NAME} sign-in code"
        assert f"Your {ENGLISH_NAME} sign-in code is: {code.group(1)}" in message.text


@pytest.mark.parametrize(("cookie", "ukrainian"), [("uk", True), ("en", False)])
def test_the_deletion_link_is_in_the_request_s_language_with_kyiv_time(
    client: TestClient, outbox: list[EmailMessage], cookie: str, ukrainian: bool
) -> None:
    school = make_institution(app.state.engine, "Kyiv Lyceum")
    invite_and_accept(
        app.state.engine, app.state.settings, email=OLENA, institutions={school: AccessLevel.READ}
    )
    client.cookies.set("sc_lang", cookie)
    client.post("/data-deletion", data={"email": OLENA})
    [message] = outbox
    assert "/data-deletion/confirm/" in message.text
    if ukrainian:
        assert UKRAINIAN_NAME in message.subject
        assert "(за київським часом)" in message.text
        assert "Kyiv time" not in message.text
    else:
        assert message.subject == f"Delete your {ENGLISH_NAME} data"
        assert "(Kyiv time)" in message.text
    assert "UTC" not in message.text


# ---------------------------------------------------------------------------------------------
# Invitations: Ukrainian then English, whatever the sender's language (FR-042)
# ---------------------------------------------------------------------------------------------


def invite_teacher(admin: TestClient, institutions: dict[str, int]) -> None:
    response = admin.post(
        "/admin/teachers/invite", data=invite_form(institutions), follow_redirects=False
    )
    assert response.status_code == 303


def test_a_teacher_invitation_is_the_same_bilingual_email_in_either_language(
    client_as: ClientAs, outbox: list[EmailMessage]
) -> None:
    institutions = {
        "kyiv": make_institution(app.state.engine, "Київський ліцей", "Київ"),
        "lviv": make_institution(app.state.engine, "Lviv School", "Lviv"),
    }
    admin = client_as(ADMIN_EMAIL)
    sent = []
    for language in ("uk", "en"):
        admin.cookies.set("sc_lang", language)
        outbox.clear()
        invite_teacher(admin, institutions)
        [message] = outbox
        sent.append(message)
    uk_subject, en_subject, uk_text, en_text = parts(sent[0])
    (_, _, uk_again, en_again) = parts(sent[1])
    assert sent[0].subject == sent[1].subject
    strip_link = re.compile(r"/invitations/\S+")
    assert strip_link.sub("", uk_text) == strip_link.sub("", uk_again)
    assert strip_link.sub("", en_text) == strip_link.sub("", en_again)

    assert UKRAINIAN_NAME in uk_subject and ENGLISH_NAME not in uk_subject
    assert en_subject == f"You are invited to {ENGLISH_NAME} as a teacher"
    assert f"({ADMIN_EMAIL}) запрошує вас" in uk_text
    assert "Педагог" in uk_text
    assert f"({ADMIN_EMAIL}) invites you to {ENGLISH_NAME} as a teacher." in en_text
    assert "Role: Teacher" in en_text
    for name in ("Київський ліцей (Київ)", "Lviv School (Lviv)"):
        assert name in uk_text and name in en_text
    assert "Редагування" in uk_text and "Write" in en_text
    assert "(за київським часом)" in uk_text
    assert "(Kyiv time)" in en_text
    for text in (uk_text, en_text):
        assert len(re.findall(r"/invitations/[A-Za-z0-9_-]+", text)) == 1
    assert UKRAINIAN_NAME in uk_text and ENGLISH_NAME not in uk_text
    assert ENGLISH_NAME in en_text and UKRAINIAN_NAME not in en_text


def test_a_student_invitation_is_bilingual_too(
    client_as: ClientAs, outbox: list[EmailMessage]
) -> None:
    engine = app.state.engine
    institution = make_institution(engine, "Kyiv Polytechnic Institute", "Kyiv")
    make_teacher(
        engine, app.state.settings, email=OLENA, institutions={institution: AccessLevel.WRITE}
    )
    school_class = make_class(engine, institution, "КН-21", 2)
    teacher = client_as(OLENA)
    for language in ("en", "uk"):
        teacher.cookies.set("sc_lang", language)
        outbox.clear()
        response = teacher.post(
            f"/teacher/students/classes/{school_class}/invite",
            data={"email": TARAS, "first_name": "Тарас", "last_name": "Шевченко"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        [message] = outbox
        uk_subject, en_subject, uk_text, en_text = parts(message)
        assert en_subject == f"You are invited to {ENGLISH_NAME} as a student"
        assert "студента" in uk_subject
        assert "Студент" in uk_text and "Role: Student" in en_text
        assert "КН-21 · 2 курс" in uk_text
        assert "КН-21 · year 2" in en_text
        assert "Kyiv Polytechnic Institute (Kyiv)" in uk_text
        assert "Kyiv Polytechnic Institute (Kyiv)" in en_text
        assert "запрошує вас" in uk_text
