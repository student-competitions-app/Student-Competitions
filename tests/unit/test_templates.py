"""The shared Jinja environment's own filters, and the components rendered on their own.

See specs/008-teacher-management-consent/research.md#d19 and, for `section_heading` and
`row_note`, specs/011.1-teacher-teams/contracts/components.md.
"""

from datetime import UTC, datetime

import pytest
from jinja2 import TemplateRuntimeError

from app.core.templates import templates


def render(source: str, **context: object) -> str:
    return templates.env.from_string(source).render(**context)


def test_the_utc_filter() -> None:
    moment = datetime(2026, 10, 22, 14, 5, 59, tzinfo=UTC)
    assert render("{{ t|utc }}", t=moment) == "2026-10-22 14:05 UTC"
    assert render('{{ t|utc("date") }}', t=moment) == "2026-10-22"
    assert render("{{ t|utc }}", t=None) == ""


# ---------------------------------------------------------------------------------------------
# Milestone 11.1 components (contracts/components.md §1–§2)
# ---------------------------------------------------------------------------------------------

SECTION_HEADING = '{% from "components/frame.html" import section_heading %}'
ROW_NOTE = '{% from "components/table.html" import row_note %}'


def test_section_heading_without_a_call_has_no_row() -> None:
    out = render(SECTION_HEADING + '{{ section_heading("Rockets", "team-heading") }}')
    assert out == '<div class="page-heading">\n  <h2 id="team-heading">Rockets</h2>\n</div>'


def test_section_heading_leaves_out_a_blank_row() -> None:
    """A call block of white space only, or of an `{% if %}` that renders nothing, gives no
    `row-actions` div, so a page can wrap its buttons in `{% if can_write %}`."""
    for block in (
        "   \n  ",
        "{% if false %}<a>Rename</a>{% endif %}",
        "\n{% if false %}x{% endif %}\n",
    ):
        source = SECTION_HEADING + '{% call section_heading("Rockets", "h") %}' + block
        out = render(source + "{% endcall %}")
        assert "row-actions" not in out, block
        assert out.endswith("</div>")


def test_section_heading_with_an_action_a_badge_and_a_row() -> None:
    source = (
        SECTION_HEADING
        + '{% call section_heading("KN-11 <b>", "h", ("Add", "/a?x=1&y=2"), deactivated=True) %}'
        + "  <a>Edit</a>\n{% endcall %}"
    )
    assert render(source) == (
        '<div class="page-heading">\n'
        '  <h2 id="h">KN-11 &lt;b&gt; <span class="badge badge-muted">Deactivated</span></h2>\n'
        '  <a href="/a?x=1&amp;y=2" role="button">Add</a>\n'
        "</div>\n"
        '<div class="row-actions"><a>Edit</a></div>'
    )


def test_row_note() -> None:
    assert render(ROW_NOTE + '{{ row_note("In <this> team") }}') == (
        '<span class="row-note">In &lt;this&gt; team</span>'
    )


def test_row_note_without_text_is_refused() -> None:
    with pytest.raises(TemplateRuntimeError, match="row_note: the text is required"):
        render(ROW_NOTE + '{{ row_note("") }}')
