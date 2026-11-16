"""Server-rendered pages. Thin handlers only — application wiring lives in `app.main`.

The role areas have their own router (`app.routers.areas`); this one serves `/`, which every role
may open: it sends an administrator or a teacher to their own area and shows a student the home
page (specs/012.6-role-landing-area)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.auth import CurrentRole, allow_roles
from app.core.config import APP_DESCRIPTION, APP_NAME, APP_TAGLINE
from app.core.db import SessionDep
from app.core.templates import templates
from app.models import ALL_ROLES
from app.routers.areas import areas_for, landing_area
from app.services.database_status import read_database_status_or_none

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
@allow_roles(*ALL_ROLES)
def home(request: Request, session: SessionDep, current_role: CurrentRole) -> Response:
    """Land an administrator or a teacher in their own area, and show everyone else the home page
    (specs/012.6-role-landing-area FR-001, FR-003, research R1).

    The redirect follows the current role only and is answered before any database read; the area
    applies its own access check. The home page is the student's: the introduction, the link to
    the student area (FR-027), and the database status. The milestone 3 question list is gone
    (milestone 11 FR-043).

    Sync rather than async: the database calls block, so FastAPI runs this in its thread pool.

    A database error while reading degrades the page rather than failing it: the page still
    renders with a notice in place of the data, and the error is logged by type and message only,
    never with the database URL (FR-026, `read_database_status_or_none`). Any other exception is a
    bug and still reaches the default 500 handling.
    """
    area = landing_area(current_role)
    if area is not None:
        return RedirectResponse(area.path, status_code=303)
    db_status = read_database_status_or_none(session)
    context: dict[str, object] = {
        "app_name": APP_NAME,
        "app_tagline": APP_TAGLINE,
        "app_description": APP_DESCRIPTION,
        "areas": areas_for(current_role),
        "db_status": db_status,
        "data_available": db_status is not None,
    }
    return templates.TemplateResponse(request, "pages/home.html", context)
