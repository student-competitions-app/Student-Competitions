"""`GET /admin/components`: the component gallery, outside production only
(specs/010-design-system-ui-guidelines research D15, contracts/http-routes.md §2, FR-037–FR-038a).

The page shows every component of `templates/components/` and each of its variants, with sample
data declared here, so a developer can see the whole library in the current theme. It reads and
writes no data: the handler takes no session.

In production the address must be unknown to everyone, signed in or not, exactly like an address
that does not exist. A check in the handler or in `resolve_access` cannot do that: an anonymous
visitor would be sent to sign in, and a teacher refused, which reveals the address. Route
matching is the only step before both, so `DevelopmentOnlyRoute` refuses to match there. It reads
the running application's settings on every request, so a test can switch production on with
`app.state.settings = dataclasses.replace(settings, production=True)`; without settings it fails
closed.

Outside production it is an ordinary administrator page, with the tab row and no tab current; it
is not one of the tabs.
"""

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from starlette.routing import Match
from starlette.types import Scope

from app.core.auth import allow_roles
from app.models import AccessLevel, Role
from app.routers.admin import ADMIN_TABS, render_admin


class DevelopmentOnlyRoute(APIRoute):
    """A route that matches no request in production, nor when the settings are missing."""

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        settings = getattr(getattr(scope.get("app"), "state", None), "settings", None)
        if settings is None or settings.production:
            return Match.NONE, {}
        return super().matches(scope)


router = APIRouter(route_class=DevelopmentOnlyRoute)


@dataclass(frozen=True)
class SampleItem:
    id: int
    name: str
    is_active: bool = True


@dataclass(frozen=True)
class SampleUser:
    email: str


@dataclass(frozen=True)
class SampleTab:
    key: str
    label: str
    path: str


SUBJECTS = (
    SampleItem(1, "Physics"),
    SampleItem(2, "Mathematics"),
    SampleItem(
        3,
        "History of science and technology in the twentieth century, an interdisciplinary elective",
        is_active=False,
    ),
)
REGIONS = (SampleItem(1, "Kyiv"), SampleItem(2, "Lviv"), SampleItem(3, "Odesa", is_active=False))
INSTITUTIONS = (
    SampleItem(1, "Kyiv Polytechnic Institute"),
    SampleItem(2, "Kyiv Lyceum No. 142", is_active=False),
)
CLASSES = ((1, "KN-21 · year 2"), (2, "KN-22 · year 2"))
ACCESS_LEVELS = (AccessLevel.READ, AccessLevel.WRITE)
DETAILS = (
    ("Email", "olena.kovalenko@school.example"),
    ("First name", "Olena"),
    ("Last name", "Kovalenko"),
    ("Roles", "Teacher, Student"),
    ("Year of study", None),
)
FIELD_ERRORS = {
    "gallery-name": "Enter a name.",
    "gallery-year": "The year of study must be a whole number from 1 to 12.",
}
FORM_ERROR = "Too many attempts. Please try again later."
ONE_ROLE_USER = SampleUser("olena.kovalenko@school.example")
TWO_ROLE_USER = SampleUser("taras.shevchenko@school.example")
SAMPLE_TABS = (
    SampleTab("first", "First tab", "/admin/components#frame"),
    SampleTab("second", "Second tab", "/admin/components#frame"),
)
TOKENS = (
    "page",
    "surface",
    "text",
    "muted",
    "border",
    "top-bar",
    "primary",
    "on-primary",
    "primary-tint",
    "accent",
    "success",
    "success-tint",
    "danger",
    "danger-tint",
    "primary-hover",
    "focus-ring",
    "danger-hover",
    "on-danger",
    "on-success",
    "on-accent",
    "on-top-bar",
    "on-top-bar-muted",
    "neutral-tint",
)
"""Every colour token, in the order of data-model §2.1–§2.2; one swatch each."""


def _samples() -> dict[str, Any]:
    return {
        "subjects": SUBJECTS,
        "regions": REGIONS,
        "institutions": INSTITUTIONS,
        "classes": CLASSES,
        "access_levels": ACCESS_LEVELS,
        "details": DETAILS,
        "field_errors": FIELD_ERRORS,
        "form_error": FORM_ERROR,
        "one_role_user": ONE_ROLE_USER,
        "two_role_user": TWO_ROLE_USER,
        "two_roles": (Role.TEACHER, Role.STUDENT),
        "teacher_role": Role.TEACHER,
        "sample_tabs": SAMPLE_TABS,
        "admin_sample_tabs": ADMIN_TABS,
        "tokens": TOKENS,
    }


@router.get("/admin/components", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def component_gallery(request: Request) -> HTMLResponse:
    return render_admin(request, "pages/admin/components.html", None, _samples())
