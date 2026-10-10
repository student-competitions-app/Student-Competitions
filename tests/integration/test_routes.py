"""The whole route table: private by default, every page declares its roles, and the only writes
are signing in and out and choosing a role.

Checked over every route rather than per route, so a route added later fails here whatever its
path if it is public by accident, declares no roles, admits the wrong roles, or accepts a write it
should not (milestone 4 FR-028, FR-047; milestone 5 FR-022, FR-024, FR-040, SC-002). See
specs/005-roles-authorization/contracts/http-routes.md#access-rule-applies-to-every-route.

`app.routes` holds each included router as a wrapper with no path or methods of its own, so
`iter_routes` descends into it and prefixes its routes, as FastAPI does when it matches a request.
"""

import re
from collections.abc import Iterator
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRouter, _IncludedRouter
from fastapi.testclient import TestClient
from starlette.routing import BaseRoute, Mount

from app.core.auth import PUBLIC_ROUTES, ROLE_CHOICE_ROUTES, allow_roles, declared_roles
from app.main import app
from app.models import Role
from tests.conftest import ADMIN_EMAIL, STUDENT_EMAIL, TEACHER_EMAIL, ClientAs

READ_ONLY_METHODS = {"GET", "HEAD"}

INSTITUTION = "/admin/institutions/regions/{region_id:int}/institutions/{institution_id:int}"


def iter_routes(
    routes: list[BaseRoute], prefix: str = ""
) -> Iterator[tuple[str, frozenset[str], BaseRoute]]:
    """Every endpoint as `(path, methods, route)`, included routers flattened, mounts skipped."""
    for route in routes:
        if isinstance(route, _IncludedRouter):
            yield from iter_routes(
                route.original_router.routes, prefix + route.include_context.prefix
            )
        elif isinstance(route, Mount):
            continue
        else:
            methods = getattr(route, "methods", None) or set()
            yield prefix + route.path, frozenset(methods), route  # type: ignore[attr-defined]


ALL_ROUTES = list(iter_routes(app.routes))


def endpoints() -> set[tuple[str, str]]:
    return {(method, path) for path, methods, _ in ALL_ROUTES for method in methods}


def test_the_route_table_is_not_empty() -> None:
    """Guard the sweeps below from passing vacuously."""
    assert ("GET", "/") in endpoints()


def test_the_write_routes_are_exact() -> None:
    """Signing in and out, choosing a role, and the administrator's subject, region and
    institution actions."""
    writes = {(method, path) for method, path in endpoints() if method not in READ_ONLY_METHODS}
    assert writes == {
        ("POST", "/login"),
        ("POST", "/login/code"),
        ("POST", "/logout"),
        ("POST", "/role"),
        ("POST", "/admin/subjects"),
        ("POST", "/admin/subjects/{subject_id:int}/rename"),
        ("POST", "/admin/subjects/{subject_id:int}/deactivate"),
        ("POST", "/admin/subjects/{subject_id:int}/activate"),
        ("POST", "/admin/subjects/{subject_id:int}/delete"),
        ("POST", "/admin/institutions/regions"),
        ("POST", "/admin/institutions/regions/{region_id:int}/rename"),
        ("POST", "/admin/institutions/regions/{region_id:int}/deactivate"),
        ("POST", "/admin/institutions/regions/{region_id:int}/activate"),
        ("POST", "/admin/institutions/regions/{region_id:int}/delete"),
        ("POST", "/admin/institutions/regions/{region_id:int}/institutions"),
        ("POST", f"{INSTITUTION}/rename"),
        ("POST", f"{INSTITUTION}/deactivate"),
        ("POST", f"{INSTITUTION}/activate"),
        ("POST", f"{INSTITUTION}/delete"),
    }


def test_the_role_choice_routes_are_exact_and_exist() -> None:
    assert ROLE_CHOICE_ROUTES == {("GET", "/role"), ("POST", "/role")}
    assert ROLE_CHOICE_ROUTES <= endpoints()


def test_the_allowlist_is_exact() -> None:
    assert PUBLIC_ROUTES == {
        ("GET", "/login"),
        ("POST", "/login"),
        ("POST", "/login/code"),
        ("POST", "/logout"),
        ("GET", "/healthz"),
    }


def test_every_allowlist_entry_exists() -> None:
    assert PUBLIC_ROUTES <= endpoints()


def _concrete(path: str) -> str:
    """A requestable URL for a route template: every `{parameter}` becomes `1`."""
    return re.sub(r"\{[^}]+\}", "1", path)


def test_every_route_outside_the_allowlist_redirects_anonymous_requests(
    client: TestClient,
) -> None:
    protected = sorted(
        (method, _concrete(path))
        for method, path in endpoints()
        if (("GET" if method == "HEAD" else method), path) not in PUBLIC_ROUTES
    )
    assert protected, "no protected route to check"
    for method, path in protected:
        response = client.request(method, path, follow_redirects=False)
        assert response.status_code == 303, f"{method} {path} answered {response.status_code}"
        if method in READ_ONLY_METHODS:
            expected = f"/login?next={quote(path, safe='')}"
        else:
            expected = "/login"
        assert response.headers["location"] == expected, f"{method} {path}"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
def test_the_api_docs_are_not_served(client: TestClient, path: str) -> None:
    """The built-in docs routes are plain Starlette routes that an application-wide dependency
    does not cover, so they are switched off rather than left public."""
    assert client.get(path, follow_redirects=False).status_code == 404


def test_the_static_files_are_the_only_mount() -> None:
    mounts = [route.path for route in app.routes if isinstance(route, Mount)]
    assert mounts == ["/static"]


# ---------------------------------------------------------------------------------------------
# Every page declares its roles; denied by default (milestone 5, user story 5)
# ---------------------------------------------------------------------------------------------

SINGLE_ROLE = {Role.ADMIN: ADMIN_EMAIL, Role.TEACHER: TEACHER_EMAIL, Role.STUDENT: STUDENT_EMAIL}

PROBE_PATH = "/__undeclared_probe"


def undeclared_routes(application: FastAPI) -> list[str]:
    """`"<METHOD> <path>"` for every route that is neither public, nor the role choice, nor
    declared with a non-empty `@allow_roles`."""
    offenders = []
    for path, methods, route in iter_routes(application.routes):
        for method in sorted(methods):
            key = ("GET" if method == "HEAD" else method, path)
            if key in PUBLIC_ROUTES or key in ROLE_CHOICE_ROUTES:
                continue
            if not declared_roles(getattr(route, "endpoint", None)):
                offenders.append(f"{method} {path}")
    return offenders


def test_every_route_is_public_role_choice_or_declared() -> None:
    """US5-1, US5-3, SC-002: the build fails naming each route that declares nobody."""
    offenders = undeclared_routes(app)
    assert offenders == [], "routes without @allow_roles(...): " + ", ".join(offenders)


@pytest.fixture
def undeclared_probe() -> Iterator[str]:
    """A route that forgot its declaration, added to the running application for one test. Added
    with `app.add_api_route`, it gets the application-wide access dependency like any route."""
    app.add_api_route(PROBE_PATH, lambda: {"secret": "probe"}, methods=["GET"])
    added = app.router.routes[-1]
    try:
        yield PROBE_PATH
    finally:
        app.router.routes.remove(added)


def test_the_sweep_names_an_undeclared_route(undeclared_probe: str) -> None:
    """US5-3."""
    assert undeclared_routes(app) == [f"GET {undeclared_probe}"]


@pytest.mark.parametrize("role", list(SINGLE_ROLE))
def test_an_undeclared_route_is_denied_to_everyone(
    client_as: ClientAs, undeclared_probe: str, role: Role
) -> None:
    """US5-4, FR-024: deny by default at runtime too."""
    response = client_as(SINGLE_ROLE[role]).get(undeclared_probe)
    assert response.status_code == 403
    assert "probe" not in response.text.replace(undeclared_probe, "")


def declared_get_routes() -> list[tuple[str, frozenset[Role]]]:
    found = []
    for path, methods, route in ALL_ROUTES:
        roles = declared_roles(getattr(route, "endpoint", None))
        if "GET" in methods and roles:
            found.append((path, roles))
    return found


def test_there_are_declared_pages_to_sweep() -> None:
    assert len(declared_get_routes()) >= 5


@pytest.mark.parametrize(("path", "allowed"), declared_get_routes())
def test_every_declared_page_admits_exactly_its_roles(
    client_as: ClientAs, path: str, allowed: frozenset[Role]
) -> None:
    """US5-2: allowed and denied, for every role, on every declared page.

    An allowed role is "not denied" rather than "200" (specs/006-admin-area/research.md D9):
    `/admin` answers with a 303 to its first tab, and `/admin/subjects/1/rename` with a 404 when
    there is no subject 1. Both prove access was granted; each page's own status is pinned by its
    own tests."""
    for role, email in SINGLE_ROLE.items():
        status = client_as(email).get(_concrete(path), follow_redirects=False).status_code
        if role in allowed:
            assert status != 403, f"{role.value} GET {path}: {status}"
        else:
            assert status == 403, f"{role.value} GET {path}: {status}"


def test_a_declaration_needs_at_least_one_role() -> None:
    with pytest.raises(ValueError):
        allow_roles()


def test_a_declaration_takes_only_roles() -> None:
    with pytest.raises(TypeError):
        allow_roles("admin")  # type: ignore[arg-type]


def test_the_declaration_is_found_above_or_below_the_route_decorator() -> None:
    router = APIRouter()

    @allow_roles(Role.TEACHER)
    @router.get("/above")
    def above() -> None: ...

    @router.get("/below")
    @allow_roles(Role.STUDENT)
    def below() -> None: ...

    found = {route.path: declared_roles(route.endpoint) for route in router.routes}  # type: ignore[attr-defined]
    assert found == {"/above": {Role.TEACHER}, "/below": {Role.STUDENT}}
