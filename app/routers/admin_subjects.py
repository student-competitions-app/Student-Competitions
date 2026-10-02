"""The Subjects tab of the administrator area: list, create, rename, deactivate/activate, delete.

See specs/006-admin-area/contracts/http-routes.md "Subjects". Thin handlers only: each parses the
form, calls `app.services.subjects`, maps its exceptions to a status and a page, and on success
redirects to the list with a 303 (Post/Redirect/Get), so a reload never repeats a change. Names
are passed to the service exactly as submitted; an invalid or duplicate one shows the form again
with the message and the value as typed.

Every route is `@allow_roles(Role.ADMIN)`, and every page is rendered with the Subjects tab
current. Ids are declared `{subject_id:int}`, so a non-integer id matches no route and gets the
application's friendly 404 rather than a JSON validation error.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import allow_roles
from app.core.db import SessionDep
from app.models import Role, Subject
from app.routers.admin import render_admin
from app.schemas.subject import SubjectNameError
from app.services.subjects import (
    DuplicateSubjectName,
    SubjectInUse,
    SubjectNotFound,
    create_subject,
    delete_subject,
    get_subject,
    list_subjects,
    rename_subject,
    set_subject_active,
)

router = APIRouter(prefix="/admin/subjects")

TAB = "subjects"
LIST_PATH = "/admin/subjects"


def _to_list() -> RedirectResponse:
    return RedirectResponse(LIST_PATH, status_code=303)


def _form(
    request: Request,
    heading: str,
    action: str,
    value: str,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """The create or rename form; with `error`, the refused value and why (FR-019)."""
    return render_admin(
        request,
        "pages/admin/subject_form.html",
        TAB,
        {"heading": heading, "action": action, "value": value, "error": error},
        status_code=status_code,
    )


def _not_found(request: Request) -> HTMLResponse:
    """The subject was deleted, perhaps in another tab: a friendly page inside the area (FR-035)."""
    return render_admin(request, "pages/admin/subject_not_found.html", TAB, status_code=404)


def _rename_action(subject_id: int) -> str:
    return f"{LIST_PATH}/{subject_id}/rename"


@router.get("", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def subjects_page(request: Request, session: SessionDep) -> HTMLResponse:
    subjects = list_subjects(session)
    return render_admin(request, "pages/admin/subjects.html", TAB, {"subjects": subjects})


@router.get("/new", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def new_subject_page(request: Request) -> HTMLResponse:
    return _form(request, "New subject", LIST_PATH, "")


@router.post("", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def create_subject_action(
    request: Request, session: SessionDep, name: str = Form("")
) -> HTMLResponse:
    try:
        create_subject(session, name)
    except (SubjectNameError, DuplicateSubjectName) as refused:
        return _form(request, "New subject", LIST_PATH, name, refused.message, 400)
    return _to_list()


@router.get("/{subject_id:int}/rename", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def rename_subject_page(request: Request, session: SessionDep, subject_id: int) -> HTMLResponse:
    try:
        subject = get_subject(session, subject_id)
    except SubjectNotFound:
        return _not_found(request)
    return _form(request, "Rename subject", _rename_action(subject_id), subject.name)


@router.post("/{subject_id:int}/rename", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def rename_subject_action(
    request: Request, session: SessionDep, subject_id: int, name: str = Form("")
) -> HTMLResponse:
    try:
        rename_subject(session, subject_id, name)
    except SubjectNotFound:
        return _not_found(request)
    except (SubjectNameError, DuplicateSubjectName) as refused:
        return _form(
            request, "Rename subject", _rename_action(subject_id), name, refused.message, 400
        )
    return _to_list()


def _set_active(
    request: Request, session: SessionDep, subject_id: int, active: bool
) -> HTMLResponse:
    """Already in that status: nothing changes, and it is not an error (FR-026)."""
    try:
        set_subject_active(session, subject_id, active)
    except SubjectNotFound:
        return _not_found(request)
    return _to_list()


@router.post("/{subject_id:int}/deactivate", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def deactivate_subject_action(
    request: Request, session: SessionDep, subject_id: int
) -> HTMLResponse:
    return _set_active(request, session, subject_id, False)


@router.post("/{subject_id:int}/activate", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def activate_subject_action(request: Request, session: SessionDep, subject_id: int) -> HTMLResponse:
    return _set_active(request, session, subject_id, True)


def _delete_page(
    request: Request, subject: Subject, in_use: bool, status_code: int = 200
) -> HTMLResponse:
    return render_admin(
        request,
        "pages/admin/subject_delete.html",
        TAB,
        {"subject": subject, "in_use": in_use},
        status_code=status_code,
    )


@router.get("/{subject_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def delete_subject_page(request: Request, session: SessionDep, subject_id: int) -> HTMLResponse:
    """The confirmation step: opening it changes nothing (FR-028)."""
    try:
        subject = get_subject(session, subject_id)
    except SubjectNotFound:
        return _not_found(request)
    return _delete_page(request, subject, in_use=False)


@router.post("/{subject_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def delete_subject_action(request: Request, session: SessionDep, subject_id: int) -> HTMLResponse:
    """A subject in use is refused with 409, offering deactivation instead (FR-029)."""
    try:
        delete_subject(session, subject_id)
    except SubjectNotFound:
        return _not_found(request)
    except SubjectInUse as refused:
        return _delete_page(request, refused.subject, in_use=True, status_code=409)
    return _to_list()
