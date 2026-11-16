"""The three role areas, where `/` sends each role, and the links back to them. Thin handlers only.

See specs/005-roles-authorization/contracts/http-routes.md and research D10. Each area is
declared once, here: its address, its title, the roles that may open it, and the label of the link
back to it. The same declaration decorates the handler, builds the student's home page card, sends
a role to its area from `/` (`landing_area`) and names the link back to it (`back_link_for`), so
what a person is shown, where they land and what they may open cannot drift apart (FR-027;
specs/012.6-role-landing-area research R2). The tests check them against an independent copy of
the spec's access table.

`/student` is the one placeholder served here. `ADMIN_AREA` and `TEACHER_AREA` are declared here
too, as the landings of an administrator and a teacher, but their addresses are served by
`app.routers.admin` and `app.routers.teacher`, which open each area's tabs
(specs/006-admin-area/research.md D6, specs/009-classes-students-management/research.md D6).
"""

from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.auth import allow_roles
from app.core.config import APP_NAME
from app.core.i18n import Text, _
from app.core.templates import templates
from app.models import Role

router = APIRouter()


@dataclass(frozen=True)
class Area:
    """One area: its address, its title, the roles that may open it, the one-line description its
    card shows on the home page (specs/010-design-system-ui-guidelines FR-035) if it has a card,
    and the "Back to …" label of an area that is a landing (milestone 12.6 FR-014, FR-015)."""

    path: str
    title: Text
    roles: frozenset[Role]
    description: Text | None = None
    back_label: Text | None = None


ADMIN_AREA = Area(
    "/admin",
    _("Administrator area"),
    frozenset({Role.ADMIN}),
    back_label=_("Back to the administrator area"),
)
TEACHER_AREA = Area(
    "/teacher",
    _("Teacher area"),
    frozenset({Role.TEACHER}),
    back_label=_("Back to the teacher area"),
)
STUDENT_AREA = Area(
    "/student",
    _("Student area"),
    frozenset({Role.STUDENT}),
    _("Take part in competitions and see your results."),
)
AREAS = (ADMIN_AREA, TEACHER_AREA, STUDENT_AREA)

LANDINGS: dict[Role, Area] = {Role.ADMIN: ADMIN_AREA, Role.TEACHER: TEACHER_AREA}
"""Where `/` sends a role: its own area. A role not listed sees the home page (milestone 12.6)."""


@dataclass(frozen=True)
class BackLink:
    """The "Back to …" link of the profile and error pages: where it leads and its text."""

    path: str
    label: Text


HOME_BACK_LINK = BackLink("/", _("Back to the home page"))
"""The back link for every role without a landing, and when the role is not known."""


def landing_area(role: Role | None) -> Area | None:
    """The area `/` sends `role` to, or `None` when `/` shows the home page (FR-001, FR-005)."""
    return LANDINGS.get(role) if role is not None else None


def back_link_for(role: Role | None) -> BackLink:
    """The back link for `role`: its landing area, or the home page (FR-014 to FR-016)."""
    area = landing_area(role)
    if area is None or area.back_label is None:
        return HOME_BACK_LINK
    return BackLink(area.path, area.back_label)


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
