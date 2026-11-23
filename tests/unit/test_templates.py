"""The shared Jinja environment's own filters, and the components rendered on their own.

See specs/008-teacher-management-consent/research.md#d19 and, for `section_heading` and
`row_note`, specs/011.1-teacher-teams/contracts/components.md.
"""

from datetime import UTC, datetime

import pytest
from jinja2 import TemplateRuntimeError
from markupsafe import Markup

from app.core.i18n import Language, use_language
from app.core.templates import templates
from tests import html


def render(source: str, **context: object) -> str:
    return templates.env.from_string(source).render(**context)


def test_the_utc_filter_is_retired() -> None:
    """Milestone 12.5 FR-038: `local_time` and `local_date` show every stored time."""
    assert "utc" not in templates.env.filters


def test_local_date() -> None:
    moment = datetime(2026, 10, 14, 22, 30, tzinfo=UTC)
    source = '{% from "components/time.html" import local_date %}{{ local_date(t) }}'
    assert render(source, t=moment, time_zone=None) == (
        '<time datetime="2026-10-15">15 October 2026</time>'
    )


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
        '  <summary aria-label="Actions for “Spring &lt;round&gt;”">Actions</summary>\n'
        '  <ul class="actions-menu-panel">\n'
        '    <li><a href="/e?a=1&amp;b=2" class="actions-menu-link">Edit</a></li>'
        '<li><a href="/c" class="actions-menu-link actions-menu-link-destructive">'
        "Cancel competition</a></li>\n"
        "  </ul>\n"
        "</details>"
    )


def test_a_download_entry() -> None:
    """Milestone 12.8 contracts/components.md §2: the bare `download` attribute, the plain link
    class; without `download` the entry is unchanged."""
    out = render(MENU + '{{ menu_link("Download results", "/r?subject=3", download=True) }}')
    assert out == (
        '<li><a href="/r?subject=3" class="actions-menu-link" download>Download results</a></li>'
    )
    plain = render(MENU + '{{ menu_link("Edit", "/e") }}')
    assert plain == '<li><a href="/e" class="actions-menu-link">Edit</a></li>'


def test_a_download_is_never_destructive() -> None:
    with pytest.raises(TemplateRuntimeError, match="menu_link: a download is never destructive"):
        render(MENU + '{{ menu_link("Download", "/d", destructive=True, download=True) }}')


BUTTONS = '{% from "components/button.html" import link_button %}'
SELECTORS = '{% from "components/selectors.html" import chained_lists %}'
LEVEL = (
    '{"id": "s", "name": "subject", "label": "Subject", "placeholder": none, '
    '"options": [(1, "Physics")], "selected": 1, "disabled": false, "carry": []}'
)


def test_a_download_link_button() -> None:
    """Milestone 12.10 contracts/components.md §2: the bare `download` attribute after the role;
    without `download` the link is unchanged."""
    out = render(BUTTONS + '{{ link_button("Get", "/g", kind="secondary", download=True) }}')
    assert out == '<a href="/g" role="button" download class="secondary">Get</a>'
    plain = render(BUTTONS + '{{ link_button("Get", "/g", kind="secondary") }}')
    assert plain == '<a href="/g" role="button" class="secondary">Get</a>'


def test_a_download_link_button_is_never_destructive() -> None:
    with pytest.raises(TemplateRuntimeError, match="link_button: a download is never destructive"):
        render(BUTTONS + '{{ link_button("Get", "/g", kind="destructive", download=True) }}')


def test_chained_lists_without_an_aside_are_unchanged() -> None:
    out = render(SELECTORS + "{{ chained_lists([" + LEVEL + '], "/a") }}')
    assert "selectors-aside" not in out
    assert out.rstrip().endswith("</form>\n</div>")


def test_chained_lists_with_an_aside() -> None:
    """Milestone 12.10 contracts/components.md §1: the aside is the last cell of the grid, its
    markup kept as given."""
    source = SELECTORS + "{{ chained_lists([" + LEVEL + '], "/a", aside=aside) }}'
    out = render(source, aside=Markup('<a href="/d" download>D</a>'))
    root = html.parse(out)
    (grid,) = [e for e in root.iter() if "selectors-chained" in e.classes()]
    cells = [c for c in grid.children if isinstance(c, html.Element)]
    assert [c.tag for c in cells] == ["form", "div"]
    assert cells[-1].classes() == ["selectors-aside"]
    (link,) = cells[-1].find_all("a")
    assert link.attrs == {"href": "/d", "download": ""}


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
        ("published", '<span class="badge badge-accent">Published</span>'),
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


# ---------------------------------------------------------------------------------------------
# Milestone 12.9: the additional badge and the text card's badge (contracts/components.md §1–§2)
# ---------------------------------------------------------------------------------------------

ADDITIONAL = '{% from "components/badge.html" import additional_badge %}'
TEXT_CARD = '{% from "components/card.html" import text_card %}'


def test_the_additional_badge() -> None:
    assert render(ADDITIONAL + "{{ additional_badge() }}") == (
        '<span class="badge badge-info">Additional</span>'
    )


def test_the_additional_badge_in_ukrainian() -> None:
    """The context `question` gives the word that agrees with «питання»."""
    with use_language(Language.UK):
        out = render(ADDITIONAL + "{{ additional_badge() }}")
    assert out == '<span class="badge badge-info">Додаткове</span>'


def test_a_text_card_without_a_badge_is_unchanged() -> None:
    out = render(TEXT_CARD + '{% call text_card("Question 57", id="q") %}<p>Body</p>{% endcall %}')
    assert out == (
        '<article class="text-card" id="q">\n  <h3>Question 57</h3>\n  <p>Body</p>\n</article>'
    )


def test_a_text_card_holds_its_badge_inside_the_heading() -> None:
    out = render(
        ADDITIONAL
        + TEXT_CARD
        + "{% call text_card(heading, badge=additional_badge()) %}<p>Body</p>{% endcall %}",
        heading="Question <57>",
    )
    assert '<h3>Question &lt;57&gt; <span class="badge badge-info">Additional</span></h3>' in out


# ---------------------------------------------------------------------------------------------
# Milestone 12.7: the logo mark (contracts/components.md, FR-007–FR-011, FR-033)
# ---------------------------------------------------------------------------------------------

LOGO = '{% from "components/icons.html" import logo_mark %}'
LOGO_PATH = "/static/img/logo/logo-{}-{}.png"


@pytest.mark.parametrize("size", ["xl", ""])
def test_logo_mark_refuses_an_unknown_size(size: str) -> None:
    with pytest.raises(TemplateRuntimeError, match="logo_mark: size must be sm, md or lg"):
        render(LOGO + "{{ logo_mark(size, 'light') }}", size=size)


@pytest.mark.parametrize("size", ["sm", "lg"])
def test_logo_mark_refuses_a_size_on_the_top_bar(size: str) -> None:
    with pytest.raises(TemplateRuntimeError, match="logo_mark: the top bar's mark takes no size"):
        render(LOGO + "{{ logo_mark(size, top_bar=True) }}", size=size)


@pytest.mark.parametrize("call", ['logo_mark("md")', 'logo_mark("md", "sepia")'])
def test_logo_mark_needs_a_theme_off_the_top_bar(call: str) -> None:
    with pytest.raises(
        TemplateRuntimeError, match="logo_mark: theme must be light, dark or device"
    ):
        render(LOGO + "{{ " + call + " }}")


def densities(ink: str, px: int) -> str:
    return ", ".join(f"{LOGO_PATH.format(ink, n * px)} {n}x" for n in (1, 2, 3))


def assert_mark_image(element: html.Element, size: str, ink: str, px: int) -> None:
    assert element.tag == "img"
    assert element.classes() == ["logo-mark", f"logo-mark-{size}"]
    assert element.attrs["src"] == LOGO_PATH.format(ink, px)
    assert element.attrs["srcset"] == densities(ink, px)
    assert element.attrs["width"] == element.attrs["height"] == str(px)
    assert "alt" in element.attrs and element.attrs["alt"] == ""
    assert element.attrs["aria-hidden"] == "true"


@pytest.mark.parametrize(("size", "px"), [("sm", 24), ("md", 32), ("lg", 64)])
def test_logo_mark_in_each_theme(size: str, px: int) -> None:
    """Light gives the dark ink, Dark the light ink, and Device a `<picture>` whose dark-scheme
    source holds the light ink, around the dark-ink image: one file per mark, no script."""
    for theme, ink in (("light", "dark"), ("dark", "light")):
        page = html.parse(render(LOGO + "{{ logo_mark(size, theme) }}", size=size, theme=theme))
        (mark,) = [e for e in page.iter() if e is not page]
        assert_mark_image(mark, size, ink, px)

    page = html.parse(render(LOGO + "{{ logo_mark(size, 'device') }}", size=size))
    (picture,) = [e for e in page.children if isinstance(e, html.Element)]
    assert picture.tag == "picture"
    source, image = [e for e in picture.children if isinstance(e, html.Element)]
    assert source.tag == "source"
    assert source.attrs == {
        "media": "(prefers-color-scheme: dark)",
        "srcset": densities("light", px),
    }
    assert_mark_image(image, size, "dark", px)


def test_logo_mark_on_the_top_bar() -> None:
    """Light ink in every theme, 44 px (the touch target) at every width, at 1x, 2x and 3x."""
    page = html.parse(render(LOGO + "{{ logo_mark(top_bar=True) }}"))
    (mark,) = [e for e in page.iter() if e is not page]
    assert mark.tag == "img"
    assert mark.classes() == ["logo-mark", "logo-mark-top-bar"]
    assert mark.attrs["src"] == LOGO_PATH.format("light", 44)
    assert mark.attrs["srcset"] == densities("light", 44)
    assert "sizes" not in mark.attrs
    assert mark.attrs["width"] == mark.attrs["height"] == "44"
    assert mark.attrs["alt"] == "" and mark.attrs["aria-hidden"] == "true"


def test_local_time_in_the_requests_zone() -> None:
    from zoneinfo import ZoneInfo

    out = render(TIME + "{{ local_time(t) }}", t=MOMENT, time_zone=ZoneInfo("Europe/Kyiv"))
    assert out == '<time datetime="2027-03-14T08:00Z">14 March 2027, 10:00</time>'


def test_local_time_with_no_zone_is_kyiv_time() -> None:
    out = render(TIME + "{{ local_time(t) }}", t=MOMENT, time_zone=None)
    assert out == '<time datetime="2027-03-14T08:00Z">14 March 2027, 10:00 (Kyiv time)</time>'


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


def test_confirmation_without_a_kind_is_unchanged() -> None:
    """Milestone 12.4 contracts/components.md §1: the default is byte-for-byte the 12.1 markup."""
    out = render(
        CONFIRMATION + '{{ confirmation("Q?", "C.", "/a", "Delete", "/back", {"page": "2"}) }}'
    )
    assert out == (
        '<section class="confirmation">\n  <h1>Q?</h1>\n  <p>C.</p>\n'
        '  <div class="form-actions">\n'
        '    <form method="post" action="/a" class="inline-form">'
        '<input type="hidden" name="page" value="2">'
        '<button type="submit" class="destructive">Delete</button>\n</form>\n'
        '    <a href="/back">Cancel</a>\n  </div>\n</section>'
    )


def test_a_primary_confirmation() -> None:
    out = render(
        CONFIRMATION
        + '{{ confirmation("Q?", "C.", "/a", "Finish competition", "/back",'
        + ' back_label="Keep in progress", kind="primary") }}'
    )
    assert '<button type="submit">Finish competition</button>' in out
    assert "destructive" not in out
    assert '<a href="/back">Keep in progress</a>' in out


def test_confirmation_refuses_another_kind() -> None:
    with pytest.raises(TemplateRuntimeError, match="confirmation: kind must be destructive or"):
        render(CONFIRMATION + '{{ confirmation("Q?", "C.", "/a", "Go", "/b", kind="secondary") }}')


def test_a_blocked_confirmation() -> None:
    """Milestone 12.8 contracts/components.md §3: the reason as a notice in place of the button,
    the work left before the link back, no form."""
    out = render(
        CONFIRMATION
        + '{{ confirmation("Q?", "C.", "/a", "Publish results", "/back",'
        + ' back_label="Keep unpublished", kind="primary", blocked="Grade every team first.",'
        + ' alternative=("Grade the remaining teams", "/grades?show=ungraded")) }}'
    )
    assert "<form" not in out and "<button" not in out
    assert "Grade every team first." in out
    assert out.index("Grade every team first.") < out.index('<div class="form-actions">')
    assert (
        '<a href="/grades?show=ungraded">Grade the remaining teams</a>\n'
        '    <a href="/back">Keep unpublished</a>'
    ) in out


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            '{{ confirmation("Q?", "C.", "/a", "Delete", "/b", blocked="Not yet.") }}',
            "confirmation: only a primary confirmation can be blocked",
        ),
        (
            '{{ confirmation("Q?", "C.", "/a", "Go", "/b", kind="primary",'
            ' alternative=("Do", "/d")) }}',
            "confirmation: an alternative needs a blocked confirmation",
        ),
    ],
)
def test_a_blocked_confirmation_is_refused_where_it_cannot_be(call: str, message: str) -> None:
    with pytest.raises(TemplateRuntimeError, match=message):
        render(CONFIRMATION + call)


# ---------------------------------------------------------------------------------------------
# Milestone 12.3: the placeholder and the answer sheet (specs/012.3-team-answers contracts/
# components.md §1–§2)
# ---------------------------------------------------------------------------------------------

FORM = '{% from "components/form.html" import field, textarea_field %}'
SHEET = '{% from "components/answer_sheet.html" import answer_sheet %}'


def test_field_and_textarea_without_a_placeholder_are_unchanged() -> None:
    """The markup of milestones 10 and 11, byte for byte: every existing call is unchanged."""
    out = render(
        FORM + '{{ field("n", "Name", value="a", hint="H", error="E", attrs={"maxlength": "9"}) }}'
    )
    assert out == (
        '<label for="n">Name</label>\n'
        '<small id="n-hint" class="field-hint">H</small>'
        '<small id="n-error" class="field-error">E</small>\n'
        '<input type="text" id="n" name="n" value="a" aria-describedby="n-hint n-error"'
        ' aria-invalid="true" maxlength="9">'
    )
    out = render(
        FORM + '{{ textarea_field("t", "Text", value=v, hint="H", attrs={"maxlength": "2000"}) }}',
        v="\nx",
    )
    assert out == (
        '<label for="t">Text</label>\n'
        '<small id="t-hint" class="field-hint">H</small>\n'
        '<textarea id="t" name="t" rows="6" aria-describedby="t-hint" maxlength="2000">'
        "\n\nx</textarea>"
    )


def test_the_placeholder_keeps_the_label_and_the_hint() -> None:
    out = render(
        FORM + '{{ textarea_field("t", "Answer to question 2", hint="Up to 2,000 characters.",'
        ' placeholder="Not <answered>") }}'
    )
    assert out == (
        '<label for="t">Answer to question 2</label>\n'
        '<small id="t-hint" class="field-hint">Up to 2,000 characters.</small>\n'
        '<textarea id="t" name="t" rows="6" aria-describedby="t-hint"'
        ' placeholder="Not &lt;answered&gt;"></textarea>'
    )
    out = render(FORM + '{{ field("n", "Name", placeholder="Empty", attrs={"required": True}) }}')
    assert out.count('placeholder="Empty"') == 1
    assert out.startswith('<label for="n">Name</label>')
    assert out.endswith(' placeholder="Empty" required>')


def sheet_item(number: int, value: str = "", error: str | None = None) -> dict[str, object]:
    return {
        "number": number,
        "field_id": f"answer-{40 + number}",
        "text": f"Question <{number}>",
        "value": value,
        "error": error,
    }


def test_the_answer_sheet() -> None:
    out = render(
        SHEET + '{{ answer_sheet(items, "/teacher/competitions/17/answers/31", hidden) }}',
        items=[sheet_item(1, "Sodium"), sheet_item(2, error="Too long.")],
        hidden={"subject": "3", "back": "2"},
    )
    assert out.startswith('<form method="post" action="/teacher/competitions/17/answers/31">')
    assert '<input type="hidden" name="subject" value="3">' in out
    assert '<input type="hidden" name="back" value="2">' in out
    assert out.count("<li>") == 2
    assert "<h3>Question 1</h3>" in out and "<h3>Question 2</h3>" in out
    assert "Question &lt;1&gt;" in out
    assert '<label for="answer-41">Answer to question 1</label>' in out
    assert (
        '<textarea id="answer-41" name="answer-41" rows="6" aria-describedby="answer-41-hint"'
        ' placeholder="Not answered" maxlength="2000">Sodium</textarea>'
    ) in out
    assert 'aria-describedby="answer-42-hint answer-42-error" aria-invalid="true"' in out
    assert '<small id="answer-42-error" class="field-error">Too long.</small>' in out
    assert out.index("</ol>") < out.index("Save answers</button>")
    assert out.count("<button") == 1
    assert ">Cancel<" not in out


def test_the_answer_sheet_keeps_a_leading_line_break() -> None:
    out = render(SHEET + '{{ answer_sheet(items, "/a", {}) }}', items=[sheet_item(1, "\nNaCl")])
    assert 'maxlength="2000">\n\nNaCl</textarea>' in out


def test_the_answer_sheet_needs_a_question() -> None:
    with pytest.raises(TemplateRuntimeError, match="answer_sheet: at least one question"):
        render(SHEET + '{{ answer_sheet([], "/a", {}) }}')


# ---------------------------------------------------------------------------------------------
# Milestone 12.4: the grading sheet and the filter links (specs/012.4-finish-and-grade contracts/
# components.md §2–§3)
# ---------------------------------------------------------------------------------------------

GRADING = '{% from "components/grading_sheet.html" import grading_sheet, answers_read_only %}'
FILTER = '{% from "components/filter.html" import filter_links %}'


def grading_item(number: int, answer: str | None) -> dict[str, object]:
    return {
        "number": number,
        "text": f"Question text {number}",
        "reference_answer": f"Reference {number}",
        "answer": answer,
        "field_id": f"grade-{number}",
        "value": "",
        "error": None,
        "grade": None,
    }


def test_the_grading_sheet_with_an_answer_has_a_form() -> None:
    out = render(
        GRADING + '{{ grading_sheet(items, "/g", {"back": "2"}) }}',
        items=[grading_item(1, "Yes"), grading_item(2, None)],
    )
    assert out.startswith('<form method="post" action="/g">')
    assert '<input type="hidden" name="back" value="2">' in out
    assert out.count('<input type="text"') == 1
    assert '<button type="submit">Save grades</button>' in out
    assert "Not answered" in out


def test_the_grading_sheet_with_no_answer_has_no_form_and_no_button() -> None:
    out = render(
        GRADING + '{{ grading_sheet(items, "/g", {"back": "2"}) }}',
        items=[grading_item(1, None), grading_item(2, None)],
    )
    assert "<form" not in out
    assert "<button" not in out
    assert "<input" not in out
    assert out.count("Reference answer") == 2
    assert out.count("Not answered") == 2


def test_the_read_only_grading_sheet() -> None:
    """Milestone 12.8 contracts/components.md §4: the note first, the reference answers kept, each
    grade as text, no form, field or button."""
    graded = {**grading_item(1, "Yes"), "grade": 7}
    out = render(
        GRADING + '{{ grading_sheet(items, "/g", {"back": "2"}, read_only=True, note="Frozen.") }}',
        items=[graded, grading_item(2, None), grading_item(3, "No")],
    )
    assert out.index("Frozen.") < out.index('<ol class="answer-sheet">')
    for absent in ("<form", "<input", "<button", "<label"):
        assert absent not in out
    assert out.count("Reference answer") == 3
    assert "Grade: 7 of 10" in out
    assert "Not graded yet" in out
    assert "Not answered" in out


def test_the_editable_grading_sheet_is_unchanged_by_the_read_only_flag() -> None:
    items = [grading_item(1, "Yes"), grading_item(2, None)]
    default = render(GRADING + '{{ grading_sheet(items, "/g", {"back": "2"}) }}', items=items)
    explicit = render(
        GRADING + '{{ grading_sheet(items, "/g", {"back": "2"}, read_only=False) }}', items=items
    )
    assert default == explicit
    assert "Grade:" not in default and "Not graded yet" not in default


def test_a_note_needs_the_read_only_grading_sheet() -> None:
    with pytest.raises(TemplateRuntimeError, match="grading_sheet: a note needs the read-only"):
        render(
            GRADING + '{{ grading_sheet(items, "/g", {}, note="Frozen.") }}',
            items=[grading_item(1, "Yes")],
        )


def test_the_grading_sheets_need_a_question() -> None:
    with pytest.raises(TemplateRuntimeError, match="grading_sheet: at least one question"):
        render(GRADING + '{{ grading_sheet([], "/g", {}) }}')
    with pytest.raises(TemplateRuntimeError, match="answers_read_only: at least one question"):
        render(GRADING + "{{ answers_read_only([]) }}")


@pytest.mark.parametrize(
    "links",
    [
        [],
        [("All teams", "/a", False), ("Ungraded only", "/u", False)],
        [("All teams", "/a", True), ("Ungraded only", "/u", True)],
    ],
)
def test_filter_links_need_exactly_one_current_link(links: list[tuple[str, str, bool]]) -> None:
    with pytest.raises(TemplateRuntimeError, match="filter_links: exactly one link"):
        render(FILTER + '{{ filter_links(links, "Show") }}', links=links)
