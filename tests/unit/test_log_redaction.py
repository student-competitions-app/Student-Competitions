"""The access-log redactor: sealed tokens and sealed query values never reach the access log.

See specs/008-teacher-management-consent/research.md#d14. `TestClient` does not run uvicorn, so
the filter is fed records shaped exactly like uvicorn's access records.
"""

import logging

import pytest

from app.core.log_redaction import AccessLogRedactor

ACCESS_FORMAT = '%s - "%s %s HTTP/%s" %d'
TOKEN = "AbC-123_xyz"


def _access_record(path: str) -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        ACCESS_FORMAT,
        ("1.2.3.4:5", "GET", path, "1.1", 200),
        None,
    )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (f"/invitations/{TOKEN}", "/invitations/***"),
        (f"/invitations/{TOKEN}?x=1", "/invitations/***?x=1"),
        (f"/data-deletion/confirm/{TOKEN}", "/data-deletion/confirm/***"),
        (f"/admin/teachers?sent={TOKEN}", "/admin/teachers?sent=***"),
        (f"/login?prefill={TOKEN}&next=/x", "/login?prefill=***&next=/x"),
        (f"/login?next=/x&prefill={TOKEN}", "/login?next=/x&prefill=***"),
        ("/admin/teachers", "/admin/teachers"),
        ("/login?next=/x", "/login?next=/x"),
        ("/data-deletion", "/data-deletion"),
        ("/login?presented=1", "/login?presented=1"),
    ],
)
def test_access_paths_are_redacted(path: str, expected: str) -> None:
    record = _access_record(path)
    assert AccessLogRedactor().filter(record) is True
    assert record.getMessage() == f'1.2.3.4:5 - "GET {expected} HTTP/1.1" 200'
    if expected != path:
        assert TOKEN not in record.getMessage()


@pytest.mark.parametrize(
    "args",
    [None, ("a", "b", f"/invitations/{TOKEN}"), {"path": f"/invitations/{TOKEN}"}],
    ids=["none", "three-tuple", "mapping"],
)
def test_other_records_pass_unchanged(args: object) -> None:
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "message", None, None)
    record.args = args  # type: ignore[assignment]
    assert AccessLogRedactor().filter(record) is True
    assert record.args is args
