"""Where `/` sends each role, and where the profile and error pages link back to.

See specs/012.6-role-landing-area/data-model.md §2–§3. The redirect and the back links read the same
declarations, so these invariants keep them from drifting apart.
"""

import pytest

from app.core.i18n import Language, use_language
from app.models import Role
from app.routers.areas import LANDINGS, Area, back_link_for, landing_area


@pytest.mark.parametrize(("role", "area"), LANDINGS.items())
def test_every_landing_is_open_to_its_role_and_has_a_back_label(role: Role, area: Area) -> None:
    assert role in area.roles
    assert area.back_label is not None


@pytest.mark.parametrize("role", [None, Role.STUDENT])
def test_no_landing_means_the_home_page(role: Role | None) -> None:
    assert landing_area(role) is None


def test_staff_land_in_their_own_area() -> None:
    admin, teacher = landing_area(Role.ADMIN), landing_area(Role.TEACHER)
    assert admin is not None and admin.path == "/admin"
    assert teacher is not None and teacher.path == "/teacher"


@pytest.mark.parametrize(
    ("role", "path", "label"),
    [
        (Role.ADMIN, "/admin", "Back to the administrator area"),
        (Role.TEACHER, "/teacher", "Back to the teacher area"),
        (Role.STUDENT, "/", "Back to the home page"),
        (None, "/", "Back to the home page"),
    ],
)
def test_the_back_link_follows_the_role(role: Role | None, path: str, label: str) -> None:
    with use_language(Language.EN):
        back = back_link_for(role)
        assert (back.path, str(back.label)) == (path, label)
