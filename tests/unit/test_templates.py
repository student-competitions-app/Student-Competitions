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


# ---------------------------------------------------------------------------------------------
# Milestone 12.2: the region group (specs/012.2-competition-questions-teams contracts/
# components.md §1)
# ---------------------------------------------------------------------------------------------

GROUP = '{% from "components/group.html" import region_group %}'


def test_region_group_with_several_teams() -> None:
    source = (
        GROUP
        + '{% call region_group("Kyiv <north>", 14, "region-7-p2") %}<table></table>{% endcall %}'
    )
    assert render(source) == (
        '<section class="region-group" aria-labelledby="region-7-p2">\n'
        '  <h2 class="region-group-header" id="region-7-p2">Kyiv &lt;north&gt; · 14 teams</h2>\n'
        "  <table></table>\n"
        "</section>"
    )


def test_region_group_with_one_team() -> None:
    source = GROUP + '{% call region_group("Lviv", 1, "r") %}{% endcall %}'
    assert ">Lviv · 1 team</h2>" in render(source)


def test_region_group_needs_a_name() -> None:
    with pytest.raises(TemplateRuntimeError, match="region_group: the name is required"):
        render(GROUP + '{% call region_group("", 3, "r") %}{% endcall %}')


def test_region_group_needs_a_total_of_at_least_one() -> None:
    with pytest.raises(TemplateRuntimeError, match="region_group: the total must be at least 1"):
        render(GROUP + '{% call region_group("Kyiv", 0, "r") %}{% endcall %}')


# ---------------------------------------------------------------------------------------------
# Milestone 12.1 components (specs/012.1-teacher-competitions contracts/components.md §1–§6)
# ---------------------------------------------------------------------------------------------

MENU = '{% from "components/menu.html" import actions_menu, menu_link %}'
BADGE = '{% from "components/badge.html" import competition_status_badge %}'
TIME = '{% from "components/time.html" import local_time with context %}'
SELECT = '{% from "components/form.html" import select_field %}'
CONFIRMATION = '{% from "components/confirmation.html" import confirmation %}'
MOMENT = datetime(2027, 3, 14, 8, 0, tzinfo=UTC)


def test_actions_menu_with_entries() -> None:
    source = (
        MENU
        + '{% call actions_menu("Spring <round>") %}'
        + '{{ menu_link("Edit", "/e?a=1&b=2") }}'
        + '{{ menu_link("Cancel competition", "/c", destructive=True) }}'
        + "{% endcall %}"
    )
    assert render(source) == (
        '<details class="actions-menu" name="row-actions">\n'
        '  <summary>Actions<span class="visually-hidden"> for “Spring &lt;round&gt;”</span>'
        "</summary>\n"
        '  <ul class="actions-menu-panel">\n'
        '    <li><a href="/e?a=1&amp;b=2" class="actions-menu-link">Edit</a></li>'
        '<li><a href="/c" class="actions-menu-link actions-menu-link-destructive">'
        "Cancel competition</a></li>\n"
        "  </ul>\n"
        "</details>"
    )


def test_actions_menu_with_a_blank_call_block_emits_nothing() -> None:
    for block in ("", "   \n  ", "{% if false %}{{ menu_link('Edit', '/e') }}{% endif %}"):
        source = MENU + '{% call actions_menu("Spring round") %}' + block + "{% endcall %}"
        assert render(source) == "", block


def test_actions_menu_needs_an_item_name() -> None:
    with pytest.raises(TemplateRuntimeError, match="actions_menu: the item name is required"):
        render(MENU + '{% call actions_menu("") %}{{ menu_link("Edit", "/e") }}{% endcall %}')


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("upcoming", '<span class="badge badge-info">Upcoming</span>'),
        ("in_progress", '<span class="badge badge-success">In progress</span>'),
        ("finished", '<span class="badge badge-neutral">Finished</span>'),
        ("cancelled", '<span class="badge badge-muted">Cancelled</span>'),
    ],
)
def test_competition_status_badge(status: str, expected: str) -> None:
    assert render(BADGE + "{{ competition_status_badge(s) }}", s=status) == expected


def test_competition_status_badge_takes_the_enum() -> None:
    from app.services.competitions import CompetitionStatus

    out = render(BADGE + "{{ competition_status_badge(s) }}", s=CompetitionStatus.IN_PROGRESS)
    assert out == '<span class="badge badge-success">In progress</span>'


def test_competition_status_badge_refuses_an_unknown_status() -> None:
    with pytest.raises(TemplateRuntimeError, match="unknown status unknown"):
        render(BADGE + '{{ competition_status_badge("unknown") }}')


def test_local_time_in_the_requests_zone() -> None:
    from zoneinfo import ZoneInfo

    out = render(TIME + "{{ local_time(t) }}", t=MOMENT, time_zone=ZoneInfo("Europe/Kyiv"))
    assert out == '<time datetime="2027-03-14T08:00Z">14 March 2027, 10:00</time>'


def test_local_time_with_no_zone_is_utc() -> None:
    out = render(TIME + "{{ local_time(t) }}", t=MOMENT, time_zone=None)
    assert out == '<time datetime="2027-03-14T08:00Z">14 March 2027, 08:00 UTC</time>'


def test_local_time_needs_a_moment() -> None:
    with pytest.raises(TemplateRuntimeError, match="local_time: the moment is required"):
        render(TIME + "{{ local_time(none) }}", time_zone=None)


def test_select_field_without_groups_is_unchanged() -> None:
    out = render(SELECT + '{{ select_field("s", "Subject", [(1, "A"), (2, "B")], selected=2) }}')
    assert out == (
        '<label for="s">Subject</label>\n\n'
        '<select id="s" name="s">\n'
        '  <option value="1">A</option>\n'
        '  <option value="2" selected>B</option>\n'
        "</select>"
    )


def test_select_field_with_a_group_marks_a_selected_value_inside_it() -> None:
    source = (
        SELECT
        + '{{ select_field("s", "Subject", [(1, "A")], selected="7", placeholder="Choose",'
        + ' groups=[("Deactivated subjects", [(7, "Astronomy")])],'
        + ' extra_options=[("new", "+ New")]) }}'
    )
    assert render(source) == (
        '<label for="s">Subject</label>\n\n'
        '<select id="s" name="s">\n'
        '  <option value="">Choose</option>\n'
        '  <option value="1">A</option>\n'
        '  <optgroup label="Deactivated subjects">\n'
        '    <option value="7" selected>Astronomy</option>\n'
        "  </optgroup>\n"
        '  <option value="new">+ New</option>\n'
        "</select>"
    )


def test_confirmation_back_label() -> None:
    default = render(CONFIRMATION + '{{ confirmation("Q?", "C.", "/a", "Delete", "/back") }}')
    assert '<a href="/back">Cancel</a>' in default
    custom = render(
        CONFIRMATION
        + '{{ confirmation("Q?", "C.", "/a", "Cancel competition", "/back",'
        + ' back_label="Keep competition") }}'
    )
    assert '<a href="/back">Keep competition</a>' in custom
    assert ">Cancel</a>" not in custom
