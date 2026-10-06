"""The administrator area: a row of tabs, each with its own address. Thin handlers only.

See specs/006-admin-area/research.md D6–D7 and contracts/http-routes.md "Area shell". The tabs are
declared once, in `ADMIN_TABS`, and every administrator page renders them through `render_admin`
and `layouts/admin.html`, which marks the current tab. Tabs are ordinary links: no script.

`GET /admin` keeps milestone 5's address (the home page links to it) and sends the browser on to
the first tab. Teachers is a placeholder until milestone 8; the Educational institutions tab lives
in `app.routers.admin_institutions` and the Subjects tab in `app.routers.admin_subjects`.
"""

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import allow_roles
from app.core.config import APP_NAME
from app.core.templates import templates
from app.models import Role
from app.routers.areas import ADMIN_AREA

router = APIRouter()


@dataclass(frozen=True)
class AdminTab:
    key: str
    label: str
    path: str


ADMIN_TABS = (
    AdminTab("teachers", "Teachers", "/admin/teachers"),
    AdminTab("institutions", "Educational institutions", "/admin/institutions"),
    AdminTab("subjects", "Subjects", "/admin/subjects"),
)
"""The tabs, in the order shown. A milestone that adds a tab adds it here."""


def render_admin(
    request: Request,
    template: str,
    active_tab: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Render an administrator page with the tab row, `active_tab` marked current (FR-004)."""
    return templates.TemplateResponse(
        request,
        template,
        {
            "app_name": APP_NAME,
            "admin_tabs": ADMIN_TABS,
            "active_tab": active_tab,
            **(context or {}),
        },
        status_code=status_code,
    )


@router.get(ADMIN_AREA.path)
@allow_roles(*ADMIN_AREA.roles)
def admin_area() -> RedirectResponse:
    """The area's own address opens its first tab (FR-005)."""
    return RedirectResponse(ADMIN_TABS[0].path, status_code=303)


def _placeholder(request: Request, tab: str, heading: str, note: str) -> HTMLResponse:
    """A tab whose features arrive later: a heading and one sentence, no actions (FR-007)."""
    return render_admin(
        request, "pages/admin/placeholder.html", tab, {"heading": heading, "note": note}
    )


@router.get("/admin/teachers", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def admin_teachers(request: Request) -> HTMLResponse:
    return _placeholder(
        request, "teachers", "Teachers", "Teacher management will arrive in a later milestone."
    )
