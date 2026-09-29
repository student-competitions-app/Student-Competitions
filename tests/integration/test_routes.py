"""The whole route table: private by default, and the only writes are signing in and out.

Checked over every route rather than per route, so a route added later fails here whatever its
path if it is public by accident or accepts a write it should not (FR-028, FR-047, SC-003). See
specs/004-email-otp-auth/contracts/http-routes.md#access-rule-applies-to-every-route.

`app.routes` holds each included router as a wrapper with no path or methods of its own, so
`iter_routes` descends into it and prefixes its routes, as FastAPI does when it matches a request.
"""

import re
from collections.abc import Iterator
from urllib.parse import quote

import pytest
from fastapi.routing import _IncludedRouter
from fastapi.testclient import TestClient
from starlette.routing import BaseRoute, Mount

from app.core.auth import PUBLIC_ROUTES
from app.main import app

READ_ONLY_METHODS = {"GET", "HEAD"}


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


def test_the_write_routes_are_exactly_login_and_logout() -> None:
    writes = {(method, path) for method, path in endpoints() if method not in READ_ONLY_METHODS}
    assert writes == {("POST", "/login"), ("POST", "/login/code"), ("POST", "/logout")}


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
