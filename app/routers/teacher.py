"""The teacher area: a row of tabs, each with its own address. Thin handlers only.

See specs/009-classes-students-management/research.md D6 and contracts/http-routes.md §1. Modelled
on `app.routers.admin`: the tabs are declared once, in `TEACHER_TABS`, and every teacher page
renders them through `render_teacher` and `layouts/teacher.html`, which marks the current tab.
Tabs are ordinary links: no script (FR-047).

`GET /teacher` keeps milestone 5's address (the home page links to it through
`areas.TEACHER_AREA`) and sends the browser on to the first tab. The Students tab lives in
`app.routers.teacher_students`; Competitions is a placeholder until milestones 11 and 14.
"""

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import allow_roles
from app.core.config import APP_NAME
from app.core.templates import templates
from app.models import Role
from app.routers.areas import TEACHER_AREA

router = APIRouter()


@dataclass(frozen=True)
class TeacherTab:
    key: str
    label: str
    path: str


TEACHER_TABS = (
    TeacherTab("students", "Students", "/teacher/students"),
    TeacherTab("competitions", "Competitions", "/teacher/competitions"),
)
"""The tabs, in the order shown. A milestone that adds a tab adds it here."""


def render_teacher(
    request: Request,
    template: str,
    active_tab: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Render a teacher page with the tab row, `active_tab` marked current (FR-047)."""
    return templates.TemplateResponse(
        request,
        template,
        {
            "app_name": APP_NAME,
            "teacher_tabs": TEACHER_TABS,
            "active_tab": active_tab,
            **(context or {}),
        },
        status_code=status_code,
    )


@router.get(TEACHER_AREA.path)
@allow_roles(*TEACHER_AREA.roles)
def teacher_area() -> RedirectResponse:
    """The area's own address opens its first tab (FR-047)."""
    return RedirectResponse(TEACHER_TABS[0].path, status_code=303)


@router.get("/teacher/competitions", response_class=HTMLResponse)
@allow_roles(Role.TEACHER)
def competitions_page(request: Request) -> HTMLResponse:
    """A placeholder: a heading and one sentence, no actions (FR-059)."""
    return render_teacher(
        request,
        "pages/teacher/placeholder.html",
        "competitions",
        {
            "heading": "Competitions",
            "note": "Competitions will arrive in a later milestone.",
        },
    )
