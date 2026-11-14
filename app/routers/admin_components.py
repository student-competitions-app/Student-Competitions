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
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from starlette.routing import Match
from starlette.types import Scope

from app.core.auth import allow_roles
from app.models import AccessLevel, Role
from app.routers.admin import ADMIN_TABS, render_admin
from app.services.paging import Paging


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
TEXTAREA_ERROR = "Enter the question text."
MULTILINE_TEXT = (
    "Name the three states of matter.\n"
    "For each, give one example from everyday life.\n\n"
    "Explain which state has the most energy."
)
LONG_WORD = "Longwordwithoutbreak" * 15
LONG_WORD_TEXT = f"A word longer than a phone screen:\n{LONG_WORD}\nThe end."
"""Two sample texts for the text card and the textarea: several lines, and a 300-character
unbroken word on its own line."""
LONG_SECTION_TITLE = (
    "This robotics and programming olympiad team of the Kyiv Polytechnic Institute, which meets"
    " every Thursday after classes in the main buildings and prepares students for the regional"
    " and national rounds"
)
"""A 200-character section title, the longest a team or class name may be, to show the wrap."""
CLASS_STUDENTS = (
    ("Shevchenko Taras", "add"),
    ("Ukrainka Lesia", "in-team"),
    ("Franko Ivan", "none"),
)
"""The rows of "Students of KN-21 · year 2": `(name, what the actions cell holds)`, for the row
note: an Add button, the note, or nothing (a full team), which on a phone has no actions part."""
PAGINGS = (Paging.build(1, 5), Paging.build(4, 200), Paging.build(20, 200))
"""Page navigation: page 1 of 1 (5 items), page 4 of 20 and page 20 of 20 (200 items)."""
SAMPLE_MOMENT = datetime(2027, 3, 14, 8, 0, tzinfo=UTC)
"""A start: 14 March 2027, 08:00 UTC, which is 10:00 in Kyiv."""
KYIV = ZoneInfo("Europe/Kyiv")
LONG_COMPETITION_NAME = (
    "Regional robotics and programming olympiad for the lyceums of Kyiv, the spring round, with"
    " the practical tasks, the written theory part and the team presentations of the projects"
    " done this past winter"
)
"""A 200-character competition name, the longest allowed, to show the wrap in a menu row."""
COMPETITION_STATUSES = ("upcoming", "in_progress", "finished", "cancelled")
SUBJECT_GROUPS = (("Deactivated subjects", [(7, "Astronomy")]),)
"""A subject list's option group, as the Competitions tab offers deactivated subjects."""
DATE_TIME_VALUES = {
    "gallery-start-empty_date": "",
    "gallery-start-empty_time": "",
    "gallery-start-filled_date": "2027-03-14",
    "gallery-start-filled_time": "10:00",
    "gallery-start-errors_date": "2027-02-30",
    "gallery-start-errors_time": "03:30",
}
DATE_TIME_ERRORS = {
    "gallery-start-errors_date": "Enter a real start date.",
    "gallery-start-errors_time": (
        "There is no 03:30 on 28 March 2027 in Europe/Kyiv because the clocks go forward."
        " Enter another time."
    ),
}
"""The date and time pair: empty, filled in a zone, and with a date error and the gap error."""
LONG_REGION_NAME = (
    "Autonomous Republic of the long names, the region that tests how a heading of two hundred"
    " characters wraps inside its box on a phone screen and on a wide desktop screen, with no"
    " sideways scroll at all"
)
"""A 200-character region name, the longest allowed, to show the region group's header wrap."""
REGION_GROUPS = (
    (
        "Kyiv",
        14,
        (
            ("Comets", "Kyiv Polytechnic Institute", 4, "remove"),
            ("Novas", "Kyiv Lyceum No. 142", 0, "remove"),
            ("Rockets", "School No. 5", 7, "deleted"),
        ),
    ),
    ("Lviv", 1, (("Lions", "Lviv Lyceum No. 3", 5, "already"),)),
    (LONG_REGION_NAME, 3, (("Stars", "School No. 12", 2, "remove"),)),
)
"""Region groups: `(name, total, rows)`, each row `(team, institution, active members, what the
actions cell holds)`: Remove, the "(deleted)" note, or "Already in this competition"."""
ANSWER_SHEET_ERROR = "Answer to question 3 can be at most 2,000 characters."
ANSWER_SHEET_ITEMS = (
    {
        "number": 1,
        "field_id": "gallery-answer-1",
        "text": "What is table salt made of? Give its name and its formula.",
        "value": "Sodium chloride\nNaCl",
        "error": None,
    },
    {
        "number": 2,
        "field_id": "gallery-answer-2",
        "text": "Name the three states of matter.",
        "value": "",
        "error": None,
    },
    {
        "number": 3,
        "field_id": "gallery-answer-3",
        "text": "Describe how water boils, step by step.",
        "value": "Water boils when " + "the bubbles rise and burst at the surface, " * 48,
        "error": ANSWER_SHEET_ERROR,
    },
)
"""The answer sheet: question 1 answered on two lines, question 2 empty (the placeholder), and
question 3 with a value over 2,000 characters and its error."""
ANSWER_SHEET_ERRORS = {"gallery-answer-3": ANSWER_SHEET_ERROR}
ANSWER_SHEET_ORDER = ("gallery-answer-1", "gallery-answer-2", "gallery-answer-3")
GRADE_ERROR = "Enter a whole number from 0 to 10."
GRADING_SHEET_ITEMS = (
    {
        "number": 1,
        "text": "What is table salt made of? Give its name and its formula.",
        "reference_answer": "Sodium chloride, NaCl.",
        "answer": "Sodium chloride\nNaCl",
        "field_id": "gallery-grade-1",
        "value": "7",
        "error": None,
    },
    {
        "number": 2,
        "text": "Name the three states of matter.",
        "reference_answer": "Solid, liquid and gas.",
        "answer": None,
        "field_id": "gallery-grade-2",
        "value": "",
        "error": None,
    },
    {
        "number": 3,
        "text": "Describe how water boils, step by step.",
        "reference_answer": (
            "Heat raises the temperature to 100 °C; bubbles of vapour form, rise and burst."
        ),
        "answer": "It gets hot and bubbles.",
        "field_id": "gallery-grade-3",
        "value": "11",
        "error": GRADE_ERROR,
    },
)
"""The grading sheet: question 1 answered on two lines and graded 7, question 2 not answered (no
field), and question 3 answered with the value "11" and its error."""
GRADING_SHEET_ERRORS = {"gallery-grade-3": GRADE_ERROR}
GRADING_SHEET_ORDER = ("gallery-grade-1", "gallery-grade-3")
READ_ONLY_ITEMS = tuple(
    {"number": item["number"], "text": item["text"], "answer": item["answer"], "grade": grade}
    for item, grade in zip(GRADING_SHEET_ITEMS, (7, None, None), strict=True)
)
"""The read-only answers of the same questions: question 1 graded 7, question 2 not answered,
question 3 answered and not graded yet."""
FILTER_LINKS = (
    ("All teams", "#filter-links", True),
    ("Ungraded only", "#filter-links", False),
)
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
        "textarea_error": TEXTAREA_ERROR,
        "multiline_text": MULTILINE_TEXT,
        "long_word_text": LONG_WORD_TEXT,
        "long_section_title": LONG_SECTION_TITLE,
        "class_students": CLASS_STUDENTS,
        "pagings": PAGINGS,
        "sample_moment": SAMPLE_MOMENT,
        "kyiv": KYIV,
        "long_competition_name": LONG_COMPETITION_NAME,
        "competition_statuses": COMPETITION_STATUSES,
        "subject_groups": SUBJECT_GROUPS,
        "date_time_values": DATE_TIME_VALUES,
        "date_time_errors": DATE_TIME_ERRORS,
        "region_groups": REGION_GROUPS,
        "answer_sheet_items": ANSWER_SHEET_ITEMS,
        "answer_sheet_errors": ANSWER_SHEET_ERRORS,
        "answer_sheet_order": ANSWER_SHEET_ORDER,
        "grading_sheet_items": GRADING_SHEET_ITEMS,
        "grading_sheet_errors": GRADING_SHEET_ERRORS,
        "grading_sheet_order": GRADING_SHEET_ORDER,
        "read_only_items": READ_ONLY_ITEMS,
        "filter_links": FILTER_LINKS,
    }


@router.get("/admin/components", response_class=HTMLResponse)
@allow_roles(Role.ADMIN)
def component_gallery(request: Request) -> HTMLResponse:
    return render_admin(request, "pages/admin/components.html", None, _samples())
