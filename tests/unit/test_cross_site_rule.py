"""The cross-site rule for unsafe requests: Fetch Metadata first, then `Origin` against `Host`.

See specs/005-roles-authorization/contracts/auth-services.md#appcoresecuritypy (the
`is_cross_site` table) and research D7. Pure: no application, no database.
"""

import pytest
from starlette.datastructures import Headers

from app.core.security import is_cross_site

HOST = "app.test"

# (Sec-Fetch-Site, Origin, Host, refused?) for an unsafe method.
TABLE = [
    ("same-origin", None, HOST, False),
    ("none", None, HOST, False),
    ("same-site", None, HOST, True),
    ("cross-site", None, HOST, True),
    ("cross-site", "https://app.test", HOST, True),
    ("something-new", None, HOST, True),
    (None, "https://app.test", HOST, False),
    (None, "http://app.test:8000", "app.test:8000", False),
    (None, "https://evil.example", HOST, True),
    (None, "https://app.test:8000", HOST, True),
    (None, "null", HOST, True),
    (None, None, HOST, False),
]


def headers(fetch_site: str | None, origin: str | None, host: str) -> Headers:
    raw = {"Host": host}
    if fetch_site is not None:
        raw["Sec-Fetch-Site"] = fetch_site
    if origin is not None:
        raw["Origin"] = origin
    return Headers(raw)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "post"])
@pytest.mark.parametrize(("fetch_site", "origin", "host", "refused"), TABLE)
def test_unsafe_methods(
    method: str, fetch_site: str | None, origin: str | None, host: str, refused: bool
) -> None:
    assert is_cross_site(method, headers(fetch_site, origin, host)) is refused


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_safe_methods_are_never_cross_site(method: str) -> None:
    assert not is_cross_site(method, headers("cross-site", "https://evil.example", HOST))


def test_header_names_are_case_insensitive_in_a_plain_mapping() -> None:
    assert is_cross_site("POST", {"SEC-FETCH-SITE": "cross-site"})
    assert is_cross_site("POST", {"origin": "https://evil.example", "HOST": HOST})
    assert not is_cross_site("POST", {"Origin": "https://APP.test", "host": HOST})
