"""The Questions tab of the teacher area: the question bank, one subject at a time.

See specs/011-question-bank/contracts/http-routes.md and research R5, R6, R8, R9, R11. Thin
handlers only: each reads its values as plain strings (so no input ever gets FastAPI's 422),
calls `app.services.questions`, maps its outcomes to a status and a page, and on success
redirects with a 303 (Post/Redirect/Get), so a reload never repeats a change. An invalid form is
shown again with every error and every value as typed.

**Every teacher reads the bank; only a teacher with Can manage competitions changes it.** The
list page shows **Add question**, **Edit** and **Delete** only with the setting. Every other
route is a *manage* route.

**Order of checks** (http-routes.md §Order of checks): the role (`@allow_roles`); then, on a
manage route, the setting, first thing in the handler, before any id is looked up or any value
used, so a teacher without it learns nothing about which subjects or questions exist (403 for an
unknown id too); then the ids ("Subject not found" / "Question not found", 404); then the fields
(400); then the service write, which checks the setting and the ids again under lock, so a
change made between the form and the save is seen.

**Return addresses** are built by `list_path` from server-side values only: a subject id that was
looked up, and a page number that went through `paging.parse_page`. Nothing here logs; the
service logs ids.
"""

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.auth import AccessDenied, allow_roles
from app.core.db import SessionDep
from app.models import Role, Subject, User
from app.routers.teacher import render_teacher
from app.schemas.question import question_field_errors
from app.schemas.teachers import MAX_ID
from app.services.paging import parse_page
from app.services.questions import (
    ManageRequired,
    QuestionNotFound,
    QuestionView,
    SubjectUnavailable,
    create_question,
    delete_question,
    get_active_subject,
    get_question,
    question_page,
    update_question,
)
from app.services.subjects import list_active_subjects
from app.services.teacher_access import can_manage_competitions

router = APIRouter(prefix="/teacher/questions")

TAB = "questions"
TAB_PATH = "/teacher/questions"

SUBJECT_NOT_FOUND = ("Subject not found", "This subject does not exist or is deactivated.")
QUESTION_NOT_FOUND = (
    "Question not found",
    "This question does not exist, was deleted, or its subject is deactivated.",
)
"""The not-found page's heading and text (research R6)."""

FIELD_ORDER = ["text", "reference_answer"]
"""The fields in page order, for the error summary."""


def list_path(subject_id: int, page: int = 1, anchor: int | None = None) -> str:
    """The list of `subject_id` at `page`, scrolled to `anchor`'s question when given."""
    path = f"{TAB_PATH}?subject={subject_id}"
    if page > 1:
        path += f"&page={page}"
    if anchor is not None:
        path += f"#question-{anchor}"
    return path


def _parse_subject(raw: str | None) -> int | None:
    """A subject id from the address or a form: an ASCII integer up to `MAX_ID`, else `None`."""
    if raw is None or not raw.isascii() or not raw.isdigit() or int(raw) > MAX_ID:
        return None
    return int(raw)


def _teacher(request: Request) -> int:
    user: User = request.state.user
    assert user.id is not None
    return user.id


def _can_manage(request: Request, session: SessionDep) -> bool:
    return can_manage_competitions(session, _teacher(request))


def _require_manage(request: Request, session: SessionDep) -> None:
    """The milestone 5 403 page for a teacher without the setting (FR-037)."""
    if not _can_manage(request, session):
        raise AccessDenied(Role.TEACHER)


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def _not_found(request: Request, page: tuple[str, str]) -> HTMLResponse:
    heading, text = page
    return render_teacher(
        request,
        "pages/teacher/question_not_found.html",
        TAB,
        {"heading": heading, "text": text},
        status_code=404,
    )


def _active_subject(session: SessionDep, raw: str | None) -> Subject | None:
    subject_id = _parse_subject(raw)
    if subject_id is None:
        return None
    try:
        return get_active_subject(session, subject_id)
    except SubjectUnavailable:
        return None


def _listed_question(session: SessionDep, question_id: int) -> tuple[QuestionView, Subject] | None:
    if question_id > MAX_ID:
        return None
    try:
        return get_question(session, question_id)
    except QuestionNotFound:
        return None


# ---------------------------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def questions_page(
    request: Request,
    session: SessionDep,
    subject: str | None = Query(None),
    page: str | None = Query(None),
) -> HTMLResponse:
    """The subject list, then the selected subject's questions, newest first, ten per page
    (FR-012–FR-024). The subject is the valid active one in the address, else the only active
    subject, else none; an invalid page reads as the first, one past the end as the last.
    Opening it changes nothing."""
    subjects = list_active_subjects(session)
    selected = _active_subject(session, subject)
    if selected is None and len(subjects) == 1:
        selected = subjects[0]
    listing = None
    if selected is not None:
        assert selected.id is not None
        listing = question_page(session, selected.id, parse_page(page))
    return render_teacher(
        request,
        "pages/teacher/questions.html",
        TAB,
        {
            "subjects": [(s.id, s.name) for s in subjects],
            "selected": selected,
            "listing": listing,
            "can_manage": _can_manage(request, session),
            "page_href": f"{TAB_PATH}?subject={selected.id}&page=" if selected else None,
        },
    )


# ---------------------------------------------------------------------------------------------
# Adding
# ---------------------------------------------------------------------------------------------


def _form(
    request: Request,
    subject: Subject,
    page: int,
    values: dict[str, str],
    *,
    question_id: int | None = None,
    errors: dict[str, str] | None = None,
    saved: bool = False,
    status_code: int = 200,
) -> HTMLResponse:
    """The add form, or with `question_id` the edit form. The subject is named, never offered
    for change (FR-026, FR-031)."""
    assert subject.id is not None
    return render_teacher(
        request,
        "pages/teacher/question_form.html",
        TAB,
        {
            "subject": subject,
            "page": page,
            "question_id": question_id,
            "values": values,
            "errors": errors or {},
            "field_order": FIELD_ORDER,
            "saved": saved,
            "back": list_path(subject.id, page, anchor=question_id),
        },
        status_code=status_code,
    )


@router.get("/new", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def new_question_page(
    request: Request,
    session: SessionDep,
    subject: str | None = Query(None),
    page: str | None = Query(None),
    saved: str | None = Query(None),
) -> HTMLResponse:
    """The empty add form; with `saved=1`, after **Save and add one more question**, it says the
    question was saved (FR-028)."""
    _require_manage(request, session)
    selected = _active_subject(session, subject)
    if selected is None:
        return _not_found(request, SUBJECT_NOT_FOUND)
    values = {"text": "", "reference_answer": ""}
    return _form(request, selected, parse_page(page), values, saved=saved == "1")


@router.post("", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def create_question_action(
    request: Request,
    session: SessionDep,
    subject: str = Form(""),
    page: str = Form(""),
    text: str = Form(""),
    reference_answer: str = Form(""),
    then: str = Form(""),
) -> Response:
    """**Save question** (`then=list`, or anything but `another`) returns to the top of the first
    page, where the new question is first (FR-027); **Save and add one more question**
    (`then=another`) opens an empty form again, keeping the return page (FR-028)."""
    _require_manage(request, session)
    selected = _active_subject(session, subject)
    if selected is None:
        return _not_found(request, SUBJECT_NOT_FOUND)
    assert selected.id is not None
    return_page = parse_page(page)
    errors, clean_text, clean_answer = question_field_errors(text, reference_answer)
    if errors:
        values = {"text": text, "reference_answer": reference_answer}
        return _form(request, selected, return_page, values, errors=errors, status_code=400)
    try:
        create_question(session, _teacher(request), selected.id, clean_text, clean_answer)
    except ManageRequired:
        raise AccessDenied(Role.TEACHER) from None
    except SubjectUnavailable:
        return _not_found(request, SUBJECT_NOT_FOUND)
    if then == "another":
        return _redirect(f"{TAB_PATH}/new?subject={selected.id}&page={return_page}&saved=1")
    return _redirect(list_path(selected.id))


# ---------------------------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------------------------


@router.get("/{question_id:int}/edit", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def edit_question_page(
    request: Request, session: SessionDep, question_id: int, page: str | None = Query(None)
) -> HTMLResponse:
    """The edit form, filled with the stored values."""
    _require_manage(request, session)
    found = _listed_question(session, question_id)
    if found is None:
        return _not_found(request, QUESTION_NOT_FOUND)
    question, subject = found
    values = {"text": question.text, "reference_answer": question.reference_answer}
    return _form(request, subject, parse_page(page), values, question_id=question.id)


@router.post("/{question_id:int}/edit", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def update_question_action(
    request: Request,
    session: SessionDep,
    question_id: int,
    page: str = Form(""),
    text: str = Form(""),
    reference_answer: str = Form(""),
) -> Response:
    """Saves both fields and returns to the page the teacher came from, at the question
    (FR-032). Only `page`, `text` and `reference_answer` are read: a `subject` field, or any
    other, is ignored, so a question never changes subject (FR-031)."""
    _require_manage(request, session)
    found = _listed_question(session, question_id)
    if found is None:
        return _not_found(request, QUESTION_NOT_FOUND)
    _, subject = found
    assert subject.id is not None
    return_page = parse_page(page)
    errors, clean_text, clean_answer = question_field_errors(text, reference_answer)
    if errors:
        values = {"text": text, "reference_answer": reference_answer}
        return _form(
            request,
            subject,
            return_page,
            values,
            question_id=question_id,
            errors=errors,
            status_code=400,
        )
    try:
        update_question(session, _teacher(request), question_id, clean_text, clean_answer)
    except ManageRequired:
        raise AccessDenied(Role.TEACHER) from None
    except QuestionNotFound:
        return _not_found(request, QUESTION_NOT_FOUND)
    return _redirect(list_path(subject.id, return_page, anchor=question_id))


# ---------------------------------------------------------------------------------------------
# Deleting
# ---------------------------------------------------------------------------------------------


@router.get("/{question_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def delete_question_page(
    request: Request, session: SessionDep, question_id: int, page: str | None = Query(None)
) -> HTMLResponse:
    """The confirmation: it names the question by its number and shows nothing else (FR-033)."""
    _require_manage(request, session)
    found = _listed_question(session, question_id)
    if found is None:
        return _not_found(request, QUESTION_NOT_FOUND)
    question, subject = found
    assert subject.id is not None
    return render_teacher(
        request,
        "pages/teacher/question_delete.html",
        TAB,
        {
            "question_id": question.id,
            "cancel": list_path(subject.id, parse_page(page), anchor=question.id),
        },
    )


@router.post("/{question_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def delete_question_action(request: Request, session: SessionDep, question_id: int) -> Response:
    """Deletes the question softly and lands where it was: on the question that took its place,
    else the one before it, else the subject's empty list (FR-034, research R8). No form field is
    read: the landing comes from the question's position, not from the page sent."""
    _require_manage(request, session)
    found = _listed_question(session, question_id)
    if found is None:
        return _not_found(request, QUESTION_NOT_FOUND)
    question, _ = found
    try:
        landing = delete_question(session, _teacher(request), question_id)
    except ManageRequired:
        raise AccessDenied(Role.TEACHER) from None
    except QuestionNotFound:
        return _not_found(request, QUESTION_NOT_FOUND)
    if landing.question_id is None:
        return _redirect(list_path(question.subject_id))
    return _redirect(list_path(question.subject_id, landing.page, anchor=landing.question_id))
