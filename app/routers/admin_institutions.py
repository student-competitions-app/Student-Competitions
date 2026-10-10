"""The Educational institutions tab of the administrator area: regions on the left, and the
institutions of the selected region on the right, each with create, rename, deactivate/activate
and delete.

See specs/007-region-and-institutions-management/contracts/http-routes.md. Thin handlers only:
each parses the form, calls `app.services.regions` or `app.services.institutions`, maps their
exceptions to a status and a page, and on success redirects with a 303 (Post/Redirect/Get), so a
reload never repeats a change. Names are passed to the services exactly as submitted; an invalid
or duplicate one shows the form again with the message and the value as typed.

The selected region is part of the address (`/admin/institutions/regions/{region_id}`), and every
region and institution page lives under it, so the selection survives reloads, bookmarks and the
sign-in redirect, and every redirect knows its region (research D7, D8).

Every route is `@allow_roles(Role.ADMIN)`, and every page is rendered with the Educational
institutions tab current. Ids are declared `{region_id:int}` and `{institution_id:int}`, so a
non-integer id matches no route and gets the application's friendly 404 rather than a JSON
validation error.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import allow_roles
from app.core.db import SessionDep
from app.models import Institution, Region, Role
from app.routers.admin import render_admin
from app.schemas.names import InvalidName
from app.services.institutions import (
    DuplicateInstitutionName,
    InstitutionInUse,
    InstitutionNotFound,
    RegionInactive,
    create_institution,
    delete_institution,
    get_institution,
    list_institutions,
    rename_institution,
    set_institution_active,
)
from app.services.regions import (
    DuplicateRegionName,
    RegionNotEmpty,
    RegionNotFound,
    create_region,
    delete_region,
    get_region,
    list_regions,
    rename_region,
    set_region_active,
)

router = APIRouter(prefix="/admin/institutions")

TAB = "institutions"
TAB_PATH = "/admin/institutions"


def region_path(region_id: int) -> str:
    """The tab with this region selected."""
    return f"/admin/institutions/regions/{region_id}"


def _institution_path(region_id: int, institution_id: int) -> str:
    return f"{region_path(region_id)}/institutions/{institution_id}"


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def _not_found(request: Request, heading: str, message: str) -> HTMLResponse:
    return render_admin(
        request,
        "pages/admin/institutions_not_found.html",
        TAB,
        {"heading": heading, "message": message},
        status_code=404,
    )


def _region_not_found(request: Request) -> HTMLResponse:
    """The region was deleted, perhaps in another tab: a friendly page inside the area (FR-043)."""
    return _not_found(
        request, "Region not found", "This region does not exist. It may have been deleted."
    )


def _institution_not_found(request: Request) -> HTMLResponse:
    """The institution was deleted, or belongs to another region (FR-043)."""
    return _not_found(
        request,
        "Educational institution not found",
        "This educational institution does not exist in this region. It may have been deleted.",
    )


def _tab(
    request: Request, session: SessionDep, region: Region | None, status_code: int = 200
) -> HTMLResponse:
    """The two lists; with `region`, it is selected and its institutions are shown."""
    return render_admin(
        request,
        "pages/admin/institutions.html",
        TAB,
        {
            "regions": list_regions(session),
            "selected": region,
            "institutions": list_institutions(session, region.id) if region else [],
        },
        status_code=status_code,
    )


@router.get("", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def institutions_page(request: Request, session: SessionDep) -> HTMLResponse:
    return _tab(request, session, None)


# ---------------------------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------------------------


def _region_form(
    request: Request,
    heading: str,
    action: str,
    value: str,
    cancel: str,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """The create or rename form; with `error`, the refused value and why (FR-025)."""
    return render_admin(
        request,
        "pages/admin/region_form.html",
        TAB,
        {"heading": heading, "action": action, "value": value, "error": error, "cancel": cancel},
        status_code=status_code,
    )


@router.get("/regions/new", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def new_region_page(request: Request) -> HTMLResponse:
    return _region_form(request, "New region", "/admin/institutions/regions", "", TAB_PATH)


@router.post("/regions", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def create_region_action(
    request: Request, session: SessionDep, name: str = Form("")
) -> HTMLResponse:
    """On success the new region is selected (FR-022)."""
    try:
        region = create_region(session, name)
    except (InvalidName, DuplicateRegionName) as refused:
        return _region_form(
            request,
            "New region",
            "/admin/institutions/regions",
            name,
            TAB_PATH,
            refused.message,
            400,
        )
    return _redirect(region_path(region.id))


@router.get("/regions/{region_id:int}", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def region_page(request: Request, session: SessionDep, region_id: int) -> HTMLResponse:
    """Selecting a region is navigation: opening it changes nothing (FR-040)."""
    try:
        region = get_region(session, region_id)
    except RegionNotFound:
        return _region_not_found(request)
    return _tab(request, session, region)


@router.get("/regions/{region_id:int}/rename", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def rename_region_page(request: Request, session: SessionDep, region_id: int) -> HTMLResponse:
    try:
        region = get_region(session, region_id)
    except RegionNotFound:
        return _region_not_found(request)
    path = region_path(region_id)
    return _region_form(request, "Rename region", f"{path}/rename", region.name, path)


@router.post("/regions/{region_id:int}/rename", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def rename_region_action(
    request: Request, session: SessionDep, region_id: int, name: str = Form("")
) -> HTMLResponse:
    path = region_path(region_id)
    try:
        rename_region(session, region_id, name)
    except RegionNotFound:
        return _region_not_found(request)
    except (InvalidName, DuplicateRegionName) as refused:
        return _region_form(
            request, "Rename region", f"{path}/rename", name, path, refused.message, 400
        )
    return _redirect(path)


def _set_region_active(
    request: Request, session: SessionDep, region_id: int, active: bool
) -> HTMLResponse:
    """Already in that status: nothing changes, and it is not an error (FR-032). The region's
    institutions keep their own statuses (FR-033)."""
    try:
        set_region_active(session, region_id, active)
    except RegionNotFound:
        return _region_not_found(request)
    return _redirect(region_path(region_id))


@router.post("/regions/{region_id:int}/deactivate", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def deactivate_region_action(request: Request, session: SessionDep, region_id: int) -> HTMLResponse:
    return _set_region_active(request, session, region_id, False)


@router.post("/regions/{region_id:int}/activate", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def activate_region_action(request: Request, session: SessionDep, region_id: int) -> HTMLResponse:
    return _set_region_active(request, session, region_id, True)


def _region_delete_page(
    request: Request, region: Region, not_empty: bool, status_code: int = 200
) -> HTMLResponse:
    return render_admin(
        request,
        "pages/admin/region_delete.html",
        TAB,
        {"region": region, "not_empty": not_empty},
        status_code=status_code,
    )


@router.get("/regions/{region_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def delete_region_page(request: Request, session: SessionDep, region_id: int) -> HTMLResponse:
    """The confirmation step: opening it changes nothing (FR-035)."""
    try:
        region = get_region(session, region_id)
    except RegionNotFound:
        return _region_not_found(request)
    return _region_delete_page(request, region, not_empty=False)


@router.post("/regions/{region_id:int}/delete", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def delete_region_action(request: Request, session: SessionDep, region_id: int) -> HTMLResponse:
    """A region that holds institutions is refused with 409 (FR-036); on success no region is
    selected (FR-039)."""
    try:
        delete_region(session, region_id)
    except RegionNotFound:
        return _region_not_found(request)
    except RegionNotEmpty as refused:
        return _region_delete_page(request, refused.region, not_empty=True, status_code=409)
    return _redirect(TAB_PATH)


# ---------------------------------------------------------------------------------------------
# Institutions
# ---------------------------------------------------------------------------------------------


def _institution_form(
    request: Request,
    heading: str,
    action: str,
    value: str,
    region: Region,
    error: str | None = None,
    refused: bool = False,
    status_code: int = 200,
) -> HTMLResponse:
    """The create or rename form, naming the region and offering no way to change it (FR-030).
    With `refused`, the region is deactivated and there is no form at all (FR-024)."""
    return render_admin(
        request,
        "pages/admin/institution_form.html",
        TAB,
        {
            "heading": heading,
            "action": action,
            "value": value,
            "error": error,
            "cancel": region_path(region.id),
            "region": region,
            "refused": refused,
        },
        status_code=status_code,
    )


def _new_institution_heading(region: Region) -> str:
    return f"New educational institution in “{region.name}”"


def _region_inactive(request: Request, region: Region) -> HTMLResponse:
    """New institutions cannot be added to a deactivated region (FR-024, US3-7)."""
    return _institution_form(
        request, _new_institution_heading(region), "", "", region, refused=True, status_code=409
    )


@router.get("/regions/{region_id:int}/institutions/new", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def new_institution_page(request: Request, session: SessionDep, region_id: int) -> HTMLResponse:
    try:
        region = get_region(session, region_id)
    except RegionNotFound:
        return _region_not_found(request)
    if not region.is_active:
        return _region_inactive(request, region)
    return _institution_form(
        request,
        _new_institution_heading(region),
        f"{region_path(region_id)}/institutions",
        "",
        region,
    )


@router.post("/regions/{region_id:int}/institutions", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def create_institution_action(
    request: Request, session: SessionDep, region_id: int, name: str = Form("")
) -> HTMLResponse:
    """Refused for a missing or deactivated region before the name is looked at (FR-024)."""
    try:
        create_institution(session, region_id, name)
    except RegionNotFound:
        return _region_not_found(request)
    except RegionInactive as refused:
        return _region_inactive(request, refused.region)
    except (InvalidName, DuplicateInstitutionName) as refused:
        try:
            region = get_region(session, region_id)
        except RegionNotFound:
            return _region_not_found(request)
        return _institution_form(
            request,
            _new_institution_heading(region),
            f"{region_path(region_id)}/institutions",
            name,
            region,
            refused.message,
            status_code=400,
        )
    return _redirect(region_path(region_id))


@router.get(
    "/regions/{region_id:int}/institutions/{institution_id:int}/rename",
    response_class=HTMLResponse,
)
@allow_roles(Role.ADMIN)
def rename_institution_page(
    request: Request, session: SessionDep, region_id: int, institution_id: int
) -> HTMLResponse:
    try:
        institution = get_institution(session, region_id, institution_id)
    except RegionNotFound:
        return _region_not_found(request)
    except InstitutionNotFound:
        return _institution_not_found(request)
    return _institution_form(
        request,
        "Rename educational institution",
        f"{_institution_path(region_id, institution_id)}/rename",
        institution.name,
        get_region(session, region_id),
    )


@router.post(
    "/regions/{region_id:int}/institutions/{institution_id:int}/rename",
    response_class=HTMLResponse,
)
@allow_roles(Role.ADMIN)
def rename_institution_action(
    request: Request,
    session: SessionDep,
    region_id: int,
    institution_id: int,
    name: str = Form(""),
) -> HTMLResponse:
    """Only `name` is read: any other field, such as a region, is ignored (FR-030)."""
    try:
        rename_institution(session, region_id, institution_id, name)
    except RegionNotFound:
        return _region_not_found(request)
    except InstitutionNotFound:
        return _institution_not_found(request)
    except (InvalidName, DuplicateInstitutionName) as refused:
        try:
            region = get_region(session, region_id)
        except RegionNotFound:
            return _region_not_found(request)
        return _institution_form(
            request,
            "Rename educational institution",
            f"{_institution_path(region_id, institution_id)}/rename",
            name,
            region,
            refused.message,
            status_code=400,
        )
    return _redirect(region_path(region_id))


def _set_institution_active(
    request: Request, session: SessionDep, region_id: int, institution_id: int, active: bool
) -> HTMLResponse:
    """Whatever the region's status (FR-015). Already in that status: nothing changes (FR-032)."""
    try:
        set_institution_active(session, region_id, institution_id, active)
    except RegionNotFound:
        return _region_not_found(request)
    except InstitutionNotFound:
        return _institution_not_found(request)
    return _redirect(region_path(region_id))


@router.post(
    "/regions/{region_id:int}/institutions/{institution_id:int}/deactivate",
    response_class=HTMLResponse,
)
@allow_roles(Role.ADMIN)
def deactivate_institution_action(
    request: Request, session: SessionDep, region_id: int, institution_id: int
) -> HTMLResponse:
    return _set_institution_active(request, session, region_id, institution_id, False)


@router.post(
    "/regions/{region_id:int}/institutions/{institution_id:int}/activate",
    response_class=HTMLResponse,
)
@allow_roles(Role.ADMIN)
def activate_institution_action(
    request: Request, session: SessionDep, region_id: int, institution_id: int
) -> HTMLResponse:
    return _set_institution_active(request, session, region_id, institution_id, True)


def _institution_delete_page(
    request: Request,
    institution: Institution,
    region: Region,
    in_use: bool,
    status_code: int = 200,
) -> HTMLResponse:
    return render_admin(
        request,
        "pages/admin/institution_delete.html",
        TAB,
        {"institution": institution, "region": region, "in_use": in_use},
        status_code=status_code,
    )


@router.get(
    "/regions/{region_id:int}/institutions/{institution_id:int}/delete",
    response_class=HTMLResponse,
)
@allow_roles(Role.ADMIN)
def delete_institution_page(
    request: Request, session: SessionDep, region_id: int, institution_id: int
) -> HTMLResponse:
    """The confirmation step, naming the institution and its region: opening it changes nothing
    (FR-035)."""
    try:
        institution = get_institution(session, region_id, institution_id)
    except RegionNotFound:
        return _region_not_found(request)
    except InstitutionNotFound:
        return _institution_not_found(request)
    return _institution_delete_page(
        request, institution, get_region(session, region_id), in_use=False
    )


@router.post(
    "/regions/{region_id:int}/institutions/{institution_id:int}/delete",
    response_class=HTMLResponse,
)
@allow_roles(Role.ADMIN)
def delete_institution_action(
    request: Request, session: SessionDep, region_id: int, institution_id: int
) -> HTMLResponse:
    """An institution in use is refused with 409, offering deactivation instead (FR-037)."""
    try:
        delete_institution(session, region_id, institution_id)
    except RegionNotFound:
        return _region_not_found(request)
    except InstitutionNotFound:
        return _institution_not_found(request)
    except InstitutionInUse as refused:
        return _institution_delete_page(
            request,
            refused.institution,
            get_region(session, region_id),
            in_use=True,
            status_code=409,
        )
    return _redirect(region_path(region_id))
