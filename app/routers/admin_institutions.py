"""The Educational institutions tab of the administrator area: list, create, rename,
deactivate/activate, delete.

See specs/007-institutions/contracts/http-routes.md. It mirrors the Subjects tab
(`app.routers.admin_subjects`). Thin handlers only: each parses the form, calls
`app.services.institutions`, maps its exceptions to a status and a page, and on success redirects
to the list with a 303 (Post/Redirect/Get), so a reload never repeats a change. Names are passed to
the service exactly as submitted; an invalid or duplicate one shows the form again with the
message and the value as typed.

Every route is `@allow_roles(Role.ADMIN)`, and every page is rendered with the Educational
institutions tab current. Ids are declared `{institution_id:int}`, so a non-integer id matches no
route and gets the application's friendly 404 rather than a JSON validation error.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import allow_roles
from app.core.db import SessionDep
from app.models import Institution, Role
from app.routers.admin import render_admin
from app.schemas.institution import InstitutionNameError
from app.services.institutions import (
    DuplicateInstitutionName,
    InstitutionInUse,
    InstitutionNotFound,
    create_institution,
    delete_institution,
    get_institution,
    list_institutions,
    rename_institution,
    set_institution_active,
)

router = APIRouter(prefix="/admin/institutions")

TAB = "institutions"
LIST_PATH = "/admin/institutions"
NEW_HEADING = "New educational institution"
RENAME_HEADING = "Rename educational institution"


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
    """The create or rename form; with `error`, the refused value and why (FR-013)."""
    return render_admin(
        request,
        "pages/admin/institution_form.html",
        TAB,
        {"heading": heading, "action": action, "value": value, "error": error},
        status_code=status_code,
    )


def _not_found(request: Request) -> HTMLResponse:
    """The institution was deleted, perhaps in another tab: a friendly page inside the area
    (FR-030)."""
    return render_admin(request, "pages/admin/institution_not_found.html", TAB, status_code=404)


def _rename_action(institution_id: int) -> str:
    return f"{LIST_PATH}/{institution_id}/rename"


@router.get("", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def institutions_page(request: Request, session: SessionDep) -> HTMLResponse:
    institutions = list_institutions(session)
    return render_admin(
        request, "pages/admin/institutions.html", TAB, {"institutions": institutions}
    )


@router.get("/new", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def new_institution_page(request: Request) -> HTMLResponse:
    return _form(request, NEW_HEADING, LIST_PATH, "")


@router.post("", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def create_institution_action(
    request: Request, session: SessionDep, name: str = Form("")
) -> HTMLResponse:
    try:
        create_institution(session, name)
    except (InstitutionNameError, DuplicateInstitutionName) as refused:
        return _form(request, NEW_HEADING, LIST_PATH, name, refused.message, 400)
    return _to_list()


@router.get("/{institution_id:int}/rename", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def rename_institution_page(
    request: Request, session: SessionDep, institution_id: int
) -> HTMLResponse:
    try:
        institution = get_institution(session, institution_id)
    except InstitutionNotFound:
        return _not_found(request)
    return _form(request, RENAME_HEADING, _rename_action(institution_id), institution.name)


@router.post("/{institution_id:int}/rename", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def rename_institution_action(
    request: Request, session: SessionDep, institution_id: int, name: str = Form("")
) -> HTMLResponse:
    try:
        rename_institution(session, institution_id, name)
    except InstitutionNotFound:
        return _not_found(request)
    except (InstitutionNameError, DuplicateInstitutionName) as refused:
        return _form(
            request, RENAME_HEADING, _rename_action(institution_id), name, refused.message, 400
        )
    return _to_list()


def _set_active(
    request: Request, session: SessionDep, institution_id: int, active: bool
) -> HTMLResponse:
    """Already in that status: nothing changes, and it is not an error (FR-021)."""
    try:
        set_institution_active(session, institution_id, active)
    except InstitutionNotFound:
        return _not_found(request)
    return _to_list()


@router.post("/{institution_id:int}/deactivate", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def deactivate_institution_action(
    request: Request, session: SessionDep, institution_id: int
) -> HTMLResponse:
    return _set_active(request, session, institution_id, False)


@router.post("/{institution_id:int}/activate", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def activate_institution_action(
    request: Request, session: SessionDep, institution_id: int
) -> HTMLResponse:
    return _set_active(request, session, institution_id, True)


def _delete_page(
    request: Request, institution: Institution, in_use: bool, status_code: int = 200
) -> HTMLResponse:
    return render_admin(
        request,
        "pages/admin/institution_delete.html",
        TAB,
        {"institution": institution, "in_use": in_use},
        status_code=status_code,
    )


@router.get("/{institution_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def delete_institution_page(
    request: Request, session: SessionDep, institution_id: int
) -> HTMLResponse:
    """The confirmation step: opening it changes nothing (FR-023)."""
    try:
        institution = get_institution(session, institution_id)
    except InstitutionNotFound:
        return _not_found(request)
    return _delete_page(request, institution, in_use=False)


@router.post("/{institution_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def delete_institution_action(
    request: Request, session: SessionDep, institution_id: int
) -> HTMLResponse:
    """An institution in use is refused with 409, offering deactivation instead (FR-024)."""
    try:
        delete_institution(session, institution_id)
    except InstitutionNotFound:
        return _not_found(request)
    except InstitutionInUse as refused:
        return _delete_page(request, refused.institution, in_use=True, status_code=409)
    return _to_list()
