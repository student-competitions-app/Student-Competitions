"""The four role areas: placeholders that later milestones fill. Thin handlers only.

See specs/005-roles-authorization/contracts/http-routes.md and research D10. Each area is
declared once, here: its address, its title and the roles that may open it. The same declaration
decorates the handler and builds the home page's links, so what a person is shown and what they
may open cannot drift apart (FR-027). The tests check both against an independent copy of the
spec's access table.

`ADMIN_AREA` stays here, so the home page keeps its "Administrator area" link to `/admin`, but the
address itself is served by `app.routers.admin`: since milestone 6 it opens the administrator
area's tabs (specs/006-admin-area/research.md D6). `TEACHER_AREA` likewise: since milestone 9
`/teacher` is served by `app.routers.teacher` and opens the teacher area's tabs
(specs/009-classes-students-management/research.md D6).
"""

from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.auth import allow_roles
from app.core.config import APP_NAME
from app.core.templates import templates
from app.models import Role

router = APIRouter()


@dataclass(frozen=True)
class Area:
    """One area: its address, its title, the roles that may open it, and the one-line
    description its card shows on the home page (specs/010-design-system-ui-guidelines FR-035)."""

    path: str
    title: str
    roles: frozenset[Role]
    description: str


ADMIN_AREA = Area(
    "/admin",
    "Administrator area",
    frozenset({Role.ADMIN}),
    "Manage teachers, educational institutions and subjects.",
)
TEACHER_AREA = Area(
    "/teacher",
    "Teacher area",
    frozenset({Role.TEACHER}),
    "Manage your classes and students, and see the question bank.",
)
STUDENT_AREA = Area(
    "/student",
    "Student area",
    frozenset({Role.STUDENT}),
    "Take part in competitions and see your results.",
)
STAFF_AREA = Area(
    "/staff",
    "Staff area",
    frozenset({Role.ADMIN, Role.TEACHER}),
    "Pages shared by administrators and teachers.",
)
AREAS = (ADMIN_AREA, TEACHER_AREA, STUDENT_AREA, STAFF_AREA)


def areas_for(role: Role | None) -> list[Area]:
    """The areas `role` may open, in `AREAS` order; used by the home page."""
    return [area for area in AREAS if role in area.roles]


def _render(request: Request, area: Area) -> HTMLResponse:
    """A placeholder: the area's title and one sentence, nothing else (FR-030)."""
    return templates.TemplateResponse(
        request, "pages/area.html", {"app_name": APP_NAME, "area": area}
    )


@router.get(STUDENT_AREA.path, response_class=HTMLResponse)
@allow_roles(*STUDENT_AREA.roles)
def student_area(request: Request) -> HTMLResponse:
    return _render(request, STUDENT_AREA)


@router.get(STAFF_AREA.path, response_class=HTMLResponse)
@allow_roles(*STAFF_AREA.roles)
def staff_area(request: Request) -> HTMLResponse:
    return _render(request, STAFF_AREA)
