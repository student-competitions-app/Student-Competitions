"""The Subjects tab of the administrator area: list, create, rename, deactivate/activate, delete,
and a subject's questions as a CSV file, exported and imported (milestone 12.11).

See specs/006-admin-area/contracts/http-routes.md "Subjects" and
specs/012.11-question-bank-csv/contracts/http-routes.md. Thin handlers only: each parses the
form, calls `app.services.subjects`, maps its exceptions to a status and a page, and on success
redirects to the list with a 303 (Post/Redirect/Get), so a reload never repeats a change. Names
are passed to the service exactly as submitted; an invalid or duplicate one shows the form again
with the message and the value as typed.

Every route is `@allow_roles(Role.ADMIN)`, and every page is rendered with the Subjects tab
current. Ids are declared `{subject_id:int}`, so a non-integer id matches no route and gets the
application's friendly 404 rather than a JSON validation error.

**Milestone 12.11**: a row's actions sit in its actions menu, whose entries are links, so
**Deactivate** and **Activate** open a confirmation page first; their `POST` routes are unchanged.
The import's file is read by the `UploadedCsv` dependency, after the role check, never by a
`File(...)` parameter (research R7). The checks run in this order: the cross-site check and the
role (`resolve_access`), then the subject ("Subject not found", 404), then the file.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.auth import allow_roles
from app.core.db import SessionDep
from app.core.i18n import _
from app.models import Role, Subject
from app.routers.admin import render_admin
from app.routers.downloads import csv_download
from app.routers.uploads import UploadedCsv
from app.schemas.subject import SubjectNameError
from app.services.question_bank_files import (
    export_file_name,
    export_rows,
    question_counts,
    replace_questions,
    today_in_kyiv,
)
from app.services.question_csv import QuestionFileCheck, check_question_file, write_question_csv
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
    """The create or rename form; with `error`, the refused value and why (FR-019), in the shared
    form shape: `values` and `errors` keyed by the field (milestone 10 data-model §4.2)."""
    return render_admin(
        request,
        "pages/admin/subject_form.html",
        TAB,
        {
            "heading": heading,
            "action": action,
            "values": {"name": value},
            "errors": {"name": error} if error else {},
        },
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
    counts = question_counts(session)
    return render_admin(
        request, "pages/admin/subjects.html", TAB, {"subjects": subjects, "counts": counts}
    )


@router.get("/new", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def new_subject_page(request: Request) -> HTMLResponse:
    return _form(request, _("New subject"), LIST_PATH, "")


@router.post("", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def create_subject_action(
    request: Request, session: SessionDep, name: str = Form("")
) -> HTMLResponse:
    try:
        create_subject(session, name)
    except (SubjectNameError, DuplicateSubjectName) as refused:
        return _form(request, _("New subject"), LIST_PATH, name, refused.message, 400)
    return _to_list()


@router.get("/{subject_id:int}/rename", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def rename_subject_page(request: Request, session: SessionDep, subject_id: int) -> HTMLResponse:
    try:
        subject = get_subject(session, subject_id)
    except SubjectNotFound:
        return _not_found(request)
    return _form(request, _("Rename subject"), _rename_action(subject_id), subject.name)


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
            request, _("Rename subject"), _rename_action(subject_id), name, refused.message, 400
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


def _status_page(request: Request, session: SessionDep, subject_id: int, page: str) -> HTMLResponse:
    """A confirmation page before deactivating or activating (milestone 12.11): opening it changes
    nothing, and it is shown whatever the subject's status, since confirming a status the subject
    already has changes nothing either (FR-026)."""
    try:
        subject = get_subject(session, subject_id)
    except SubjectNotFound:
        return _not_found(request)
    return render_admin(request, f"pages/admin/{page}", TAB, {"subject": subject})


@router.get("/{subject_id:int}/deactivate", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def deactivate_subject_page(request: Request, session: SessionDep, subject_id: int) -> HTMLResponse:
    return _status_page(request, session, subject_id, "subject_deactivate.html")


@router.get("/{subject_id:int}/activate", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def activate_subject_page(request: Request, session: SessionDep, subject_id: int) -> HTMLResponse:
    return _status_page(request, session, subject_id, "subject_activate.html")


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


# ---------------------------------------------------------------------------------------------
# A subject's questions as a CSV file (milestone 12.11)
# ---------------------------------------------------------------------------------------------


@router.get("/{subject_id:int}/questions/export")
@allow_roles(Role.ADMIN)
def export_questions(request: Request, session: SessionDep, subject_id: int) -> Response:
    """The subject's question bank as a CSV file, offered as a link marked as a download: every
    listed question, additional ones included, oldest first (FR-013–FR-016). Read at every request,
    never stored, never logged; an active and a deactivated subject alike."""
    try:
        subject = get_subject(session, subject_id)
    except SubjectNotFound:
        return _not_found(request)
    content = write_question_csv(export_rows(session, subject_id))
    return csv_download(content, export_file_name(subject.name, today_in_kyiv()))


def _import_page(
    request: Request,
    session: SessionDep,
    subject: Subject,
    check: QuestionFileCheck | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """The import page: a destructive confirmation with the file field, and, after a refused file,
    every error found (at most 20) with the field empty again (FR-030–FR-033)."""
    assert subject.id is not None
    file_error = check.file_error if check is not None else None
    return render_admin(
        request,
        "pages/admin/subject_import.html",
        TAB,
        {
            "subject": subject,
            "count": question_counts(session).get(subject.id, 0),
            "errors": {"file": file_error} if file_error is not None else {},
            "row_errors": check.row_errors if check is not None else (),
            "more": check.more if check is not None else 0,
        },
        status_code=status_code,
    )


@router.get("/{subject_id:int}/questions/import", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def import_questions_page(request: Request, session: SessionDep, subject_id: int) -> HTMLResponse:
    """Opening it changes nothing."""
    try:
        subject = get_subject(session, subject_id)
    except SubjectNotFound:
        return _not_found(request)
    return _import_page(request, session, subject)


@router.post("/{subject_id:int}/questions/import", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def import_questions_action(
    request: Request, session: SessionDep, subject_id: int, upload: UploadedCsv
) -> HTMLResponse:
    """The whole file is checked first: a refused file shows the page again with every error, 400,
    and nothing changes. A valid one replaces the subject's questions and returns to the list,
    where the Questions column shows the new number (FR-034, FR-041)."""
    try:
        subject = get_subject(session, subject_id)
    except SubjectNotFound:
        return _not_found(request)
    check = check_question_file(upload.data, too_large=upload.too_large)
    if not check.ok:
        return _import_page(request, session, subject, check, 400)
    try:
        replace_questions(session, subject_id, check.rows)
    except SubjectNotFound:
        return _not_found(request)
    return _to_list()
