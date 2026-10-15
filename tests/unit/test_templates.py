"""The shared Jinja environment's own filters.

See specs/008-teacher-management-consent/research.md#d19.
"""

from datetime import UTC, datetime

from app.core.templates import templates


def render(source: str, **context: object) -> str:
    return templates.env.from_string(source).render(**context)


def test_the_utc_filter() -> None:
    moment = datetime(2026, 10, 22, 14, 5, 59, tzinfo=UTC)
    assert render("{{ t|utc }}", t=moment) == "2026-10-22 14:05 UTC"
    assert render('{{ t|utc("date") }}', t=moment) == "2026-10-22"
    assert render("{{ t|utc }}", t=None) == ""
