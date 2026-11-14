"""The component gallery, `GET /admin/components` (specs/010-design-system-ui-guidelines US7,
FR-037–FR-038a, SC-009; contracts/http-routes.md §2, contracts/components.md §12), with the
loading feedback of milestone 10.1 (specs/010.1-loading-feedback-pinned-frame FR-017,
contracts/components.md §5).

Outside production an administrator sees every component and variant; other roles are refused
as on any administrator page, and anonymous visitors are sent to sign in. In production the
address is unknown to everyone: the same 404 as an address that does not exist. Every test runs
once per database engine.
"""

import dataclasses
import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.main import app
from app.models import Role
from tests import html
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_STUDENT_EMAIL,
    STUDENT_EMAIL,
    TEACHER_EMAIL,
    ClientAs,
)

GALLERY = "/admin/components"

SECTIONS = {
    "identity": ["Student Competitions", "--sc-page", "--sc-accent", "Heading 1", "Small text"],
    "frame": ["Account menu", "Switch to", "Light", "Dark", "Device", "Back to the frame"],
    "section-heading": ["KN-21 · year 2", "Add student", "Deactivated", "Activate", "Rockets"],
    "loading": ["Loading bar", "Busy button", "Send invitation"],
    "buttons": ["Primary button", "Secondary link", "Destructive form", "Destructive outline"],
    "cards": [
        "Card with a link",
        "Card without a link",
        "Card with a body",
        "Text cards",
        "Question 57",
        "Reference answer",
        "Longwordwithoutbreak" * 15,
    ],
    "table": [
        "Physics",
        "Deactivated",
        "Rename",
        "Activate",
        "Students of KN-21 · year 2",
        "In this team",
        "A short value on one line",
        "3 of 6",
        "No subjects yet",
    ],
    "region-group": [
        "Kyiv · 14 teams",
        "Lviv · 1 team",
        "Educational institution",
        "Active members",
        "(deleted)",
        "Already in this competition",
    ],
    "actions-menu": [
        "Actions",
        "for “Spring final”",
        "Edit",
        "Questions",
        "Teams",
        "Answers",
        "Grades",
        "Finish competition",
        "Cancel competition",
        "Autumn round",
    ],
    "time": ["14 March 2027, 10:00", "14 March 2027, 08:00 UTC"],
    "badges": [
        "Active",
        "Deactivated",
        "Read",
        "Write",
        "Upcoming",
        "In progress",
        "Finished",
        "Cancelled",
    ],
    "empty-states": ["No subjects yet", "Select a region"],
    "notices": ["Invitation sent to", "no longer valid", "temporarily unavailable"],
    "forms": [
        "There is a problem",
        "Enter a name.",
        "Can manage competitions",
        "Save",
        "Cancel",
        "Up to 2,000 characters.",
        "Reference answer",
        "Enter the question text.",
        "Save question",
        "Save and add one more question",
        "Start date",
        "Start time",
        "Time zone: Europe/Kyiv",
        "Enter a real start date.",
        "There is no 03:30 on 28 March 2027 in Europe/Kyiv because the clocks go forward.",
        "Answer to question 2",
    ],
    "answer-sheet": [
        "Answer sheet",
        "There is a problem",
        "Question 1",
        "Sodium chloride",
        "Answer to question 3",
        "Answer to question 3 can be at most 2,000 characters.",
        "Save answers",
    ],
    "grading-sheet": [
        "Grading sheet",
        "There is a problem",
        "Question 1",
        "Reference answer",
        "Answer to question 1",
        "Grade for question 1",
        "A whole number from 0 to 10.",
        "Not answered",
        "Enter a whole number from 0 to 10.",
        "Save grades",
        "Grade: 7 of 10",
        "Not graded yet",
    ],
    "confirmations": [
        "Delete “Physics”?",
        "is in use and cannot be deleted",
        "Deactivate",
        "Keep competition",
        "Finish competition",
        "Keep in progress",
    ],
    "details": ["Email", "Olena", "Teacher, Student"],
    "selectors": [
        "Regions",
        "Kyiv",
        "Educational institutions in “Kyiv”",
        "+ Add class",
        "Show",
        "Astronomy",
    ],
    "filter-links": ["Filter links", "All teams", "Ungraded only"],
    "pagination": [
        "Questions 1–5 of 5",
        "Questions 31–40 of 200",
        "Questions 191–200 of 200",
        "Previous",
        "Next",
    ],
}
"""components.md §12, in order: each section's id and texts of its variants."""


@pytest.fixture
def production(client: TestClient) -> Iterator[None]:
    settings = app.state.settings
    app.state.settings = dataclasses.replace(settings, production=True)
    try:
        yield
    finally:
        app.state.settings = settings


def sections(body: str) -> list[html.Element]:
    (main,) = html.parse(body).find_all("main")
    return [s for s in main.find_all("section") if s.attrs.get("id") in SECTIONS]


def test_an_administrator_sees_every_section_and_variant(admin_client: TestClient) -> None:
    response = admin_client.get(GALLERY)
    assert response.status_code == 200
    found = sections(response.text)
    assert [s.attrs["id"] for s in found] == list(SECTIONS)
    for section in found:
        text = section.text()
        for variant in SECTIONS[section.attrs["id"]]:
            assert variant in text, (section.attrs["id"], variant)


def test_the_loading_section_shows_both_components_in_their_loading_state(
    admin_client: TestClient,
) -> None:
    """The bar shown (not hidden) under a sample frame, and a busy button of each kind: never
    disabled, and outside any form, so pressing one does nothing."""
    (section,) = [s for s in sections(admin_client.get(GALLERY).text) if s.attrs["id"] == "loading"]
    bars = [e for e in section.find_all("div") if "loading-bar" in e.classes()]
    assert len(bars) == 1
    (bar,) = bars
    assert "hidden" not in bar.attrs
    assert bar.attrs.get("aria-hidden") == "true"
    assert bar.parent is not None and "frame" in bar.parent.classes()
    busy = [b for b in section.find_all("button") if b.attrs.get("aria-busy") == "true"]
    assert [b.text() for b in busy] == ["Send invitation", "Dark", "Delete"]
    assert not any("disabled" in b.attrs for b in busy)

    def in_form(element: html.Element) -> bool:
        parent = element.parent
        while parent is not None and parent.tag != "form":
            parent = parent.parent
        return parent is not None

    assert not any(in_form(b) for b in busy)


def gallery_section(body: str, section_id: str) -> html.Element:
    (found,) = [s for s in sections(body) if s.attrs["id"] == section_id]
    return found


def test_the_section_heading_variants(admin_client: TestClient) -> None:
    """Milestone 11.1 contracts/components.md §1: four headings, each an `h2` in a page heading,
    one with the badge, one with no action and no row, and one with a 200-character title."""
    section = gallery_section(admin_client.get(GALLERY).text, "section-heading")
    variants = [
        s for s in section.find_all("section") if s.attrs.get("aria-labelledby", "").startswith("g")
    ]
    assert len(variants) == 4
    for variant in variants:
        (heading,) = variant.find_all("h2")
        assert heading.attrs["id"] == variant.attrs["aria-labelledby"]
        assert heading.parent is not None and "page-heading" in heading.parent.classes()

    def in_div(variant: html.Element, div_class: str, tags: tuple[str, ...]) -> list[list[str]]:
        found = [d for d in variant.find_all("div") if div_class in d.classes()]
        return [[e.text() for e in d.iter() if e.tag in tags] for d in found]

    def badges(variant: html.Element) -> list[str]:
        (heading,) = variant.find_all("h2")
        return [e.text() for e in heading.iter() if "badge" in e.classes()]

    actions, deactivated, read, long = variants
    assert in_div(actions, "page-heading", ("a",)) == [["Add student"]]
    assert in_div(actions, "row-actions", ("a", "button")) == [["Edit", "Delete"]]
    assert badges(actions) == []
    assert in_div(deactivated, "page-heading", ("a",)) == [[]]
    assert in_div(deactivated, "row-actions", ("a", "button")) == [["Edit", "Activate", "Delete"]]
    assert badges(deactivated) == ["Deactivated"]
    assert in_div(read, "page-heading", ("a",)) == [[]]
    assert in_div(read, "row-actions", ("a", "button")) == []
    (title,) = long.find_all("h2")
    assert len(title.text()) == 200
    assert in_div(long, "page-heading", ("a",)) == [["Add students"]]
    assert in_div(long, "row-actions", ("a", "button")) == []


def test_the_row_note_stands_in_the_actions_cell(admin_client: TestClient) -> None:
    """Milestone 11.1 contracts/components.md §2: one row with Add, one with the note."""
    body = admin_client.get(GALLERY).text
    section = gallery_section(body, "table")
    notes = [s for s in section.find_all("span") if "row-note" in s.classes()]
    assert [n.text() for n in notes] == ["In this team"]
    (note,) = notes
    assert note.parent is not None and note.parent.tag == "td"
    assert "row-actions" in note.parent.classes()
    assert html.outer_html(body, note) == '<span class="row-note">In this team</span>'
    (table,) = [t for t in section.find_all("table") if "Students of KN-21" in t.text()]
    cells = [td for td in table.find_all("td") if "row-actions" in td.classes()]
    assert [(td.text(), td.children == []) for td in cells] == [
        ("Add", False),
        ("In this team", False),
        ("", True),
    ]


def test_the_page_navigation_variants(admin_client: TestClient) -> None:
    """Milestone 11 contracts/components.md §1: the range, Previous and Next as text at the ends,
    one current page per nav, and gaps; every link stays on the gallery."""
    body = admin_client.get(GALLERY).text
    found = [html.pagination(body, f"Pages, sample {n}") for n in (1, 2, 3)]
    assert all(nav is not None for nav in found)
    (first_range, first), (middle_range, middle), (last_range, last) = found  # type: ignore[misc]
    assert first_range == "Questions 1–5 of 5"
    assert [(e.text, e.href, e.current) for e in first] == [
        ("Previous", None, False),
        ("1", "/admin/components?page=1", True),
        ("Next", None, False),
    ]
    assert middle_range == "Questions 31–40 of 200"
    assert [e.text for e in middle] == ["Previous", "1", "2", "3", "4", "5", "…", "20", "Next"]
    assert [e.href for e in middle if e.text in ("Previous", "Next")] == [
        "/admin/components?page=3",
        "/admin/components?page=5",
    ]
    assert last_range == "Questions 191–200 of 200"
    assert [e.text for e in last] == ["Previous", "1", "…", "19", "20", "Next"]
    assert last[-1].href is None
    for entries in (first, middle, last):
        assert [e.text for e in entries if e.current] in (["1"], ["4"], ["20"])
        assert all(e.href is None or e.href.startswith(GALLERY) for e in entries)
    (gap,) = [s for s in html.parse(body).find_all("span") if "pagination-gap" in s.classes()][:1]
    assert gap.attrs.get("aria-hidden") == "true"


def test_the_two_button_form_and_the_textareas(admin_client: TestClient) -> None:
    """Milestone 11 contracts/components.md §2–§3: the main save first, then the secondary save,
    then Cancel; a textarea keeps its line breaks and wires its hint and error."""
    body = admin_client.get(GALLERY).text
    (actions,) = [
        d
        for d in html.parse(body).find_all("div")
        if "form-actions" in d.classes() and "Save question" in d.text()
    ]
    buttons = [
        (b.text(), b.attrs.get("name"), b.attrs.get("value"), b.classes())
        for b in actions.find_all("button")
    ]
    assert buttons == [
        ("Save question", "then", "list", []),
        ("Save and add one more question", "then", "another", ["secondary"]),
    ]
    assert [a.text() for a in actions.find_all("a")] == ["Cancel"]
    assert 'aria-describedby="gallery-text-empty-hint"' in body
    assert 'aria-describedby="gallery-text-error-error" aria-invalid="true"' in body
    assert (
        '<textarea id="gallery-text-filled" name="gallery-text-filled" rows="6">Name the three'
        " states of matter.\nFor each" in body
    )


def test_the_actions_menu_variants(admin_client: TestClient) -> None:
    """Milestone 12.1 contracts/components.md §1, with the entries of milestones 12.2
    (contracts/components.md §2), 12.3 (contracts/components.md §4) and 12.4 (contracts/
    components.md §5, which adds **Grades** and a non-destructive **Finish competition**): an open
    menu with every entry in order, the last one destructive; a closed one for a 200-character
    name, in progress; and the two-entry read-only menu."""
    body = admin_client.get(GALLERY).text
    section = gallery_section(body, "actions-menu")
    menus = [d for d in section.find_all("details") if "actions-menu" in d.classes()]
    assert [m.attrs.get("name") for m in menus] == ["row-actions"] * 3
    assert ["open" in m.attrs for m in menus] == [True, False, False]
    summaries = [m.find_all("summary")[0].text() for m in menus]
    assert summaries[0] == "Actions for “Spring final”"
    assert summaries[1].startswith("Actions for “Regional robotics")
    assert len(summaries[1]) == len("Actions for “”") + 200
    links = [(a.text(), a.classes()) for a in menus[0].find_all("a")]
    assert links == [
        ("Edit", ["actions-menu-link"]),
        ("Questions", ["actions-menu-link"]),
        ("Teams", ["actions-menu-link"]),
        ("Answers", ["actions-menu-link"]),
        ("Grades", ["actions-menu-link"]),
        ("Finish competition", ["actions-menu-link"]),
        ("Cancel competition", ["actions-menu-link", "actions-menu-link-destructive"]),
    ]
    assert [a.text() for a in menus[1].find_all("a")] == [
        "Questions",
        "Teams",
        "Answers",
        "Finish competition",
        "Cancel competition",
    ]
    assert [a.text() for a in menus[2].find_all("a")] == ["Questions", "Teams"]


def test_a_short_value_stays_on_one_line(admin_client: TestClient) -> None:
    """Milestone 12.3: `cell(..., nowrap=True)` marks only its own cell."""
    body = admin_client.get(GALLERY).text
    assert '<td data-label="Answered" class="cell-nowrap">3 of 6</td>' in body
    assert body.count("cell-nowrap") == 1


def test_the_answer_sheet(admin_client: TestClient) -> None:
    """Milestone 12.3 contracts/components.md §1: one post form holding the hidden field, an
    `ol.answer-sheet` of three numbered text cards, each with its labelled answer field (the hint,
    the placeholder and the 2,000-character limit), the third one invalid and linked from the
    error summary above, and one primary "Save answers" after the list."""
    body = admin_client.get(GALLERY).text
    section = gallery_section(body, "answer-sheet")
    (summary,) = [e for e in section.iter() if "error-summary" in e.classes()]
    assert [a.attrs["href"] for a in summary.find_all("a")] == ["#gallery-answer-3"]
    (form,) = section.find_all("form")
    assert form.attrs["method"] == "post"
    assert [(i.attrs["name"], i.attrs["value"]) for i in form.find_all("input")] == [("back", "1")]
    (sheet,) = form.find_all("ol")
    assert sheet.classes() == ["answer-sheet"]
    items = sheet.find_all("li")
    assert len(items) == 3
    for number, item in enumerate(items, start=1):
        (card,) = item.find_all("article")
        assert "text-card" in card.classes()
        assert card.find_all("h3")[0].text() == f"Question {number}"
        (textarea,) = item.find_all("textarea")
        field_id = f"gallery-answer-{number}"
        assert textarea.attrs["id"] == textarea.attrs["name"] == field_id
        (label,) = item.find_all("label")
        assert label.attrs["for"] == field_id
        assert label.text() == f"Answer to question {number}"
        assert textarea.attrs["placeholder"] == "Not answered"
        assert textarea.attrs["maxlength"] == "2000"
        assert f"{field_id}-hint" in textarea.attrs["aria-describedby"]
        hints = [e.text() for e in item.iter() if e.attrs.get("id") == f"{field_id}-hint"]
        assert hints == ["Up to 2,000 characters."]
    assert "aria-invalid" not in items[0].find_all("textarea")[0].attrs
    assert items[2].find_all("textarea")[0].attrs["aria-invalid"] == "true"
    errors = [e.text() for e in items[2].iter() if e.attrs.get("id") == "gallery-answer-3-error"]
    assert errors == ["Answer to question 3 can be at most 2,000 characters."]
    assert ">Sodium chloride\nNaCl</textarea>" in body
    buttons = form.find_all("button")
    assert [(b.text(), b.classes()) for b in buttons] == [("Save answers", [])]
    assert buttons[0].start > sheet.end
    assert not [a for a in form.find_all("a") if a.text() == "Cancel"]


def test_the_placeholder_stays_under_its_label_and_hint(admin_client: TestClient) -> None:
    """Milestone 12.3 contracts/components.md §2: the empty field of `#forms` keeps its label and
    hint, and shows "Not answered" as its placeholder only."""
    body = admin_client.get(GALLERY).text
    assert (
        '<label for="gallery-placeholder">Answer to question 2</label>\n'
        '<small id="gallery-placeholder-hint" class="field-hint">Up to 2,000 characters.</small>\n'
        '<textarea id="gallery-placeholder" name="gallery-placeholder" rows="6"'
        ' aria-describedby="gallery-placeholder-hint" placeholder="Not answered"></textarea>'
    ) in body


def test_the_region_group_variants(admin_client: TestClient) -> None:
    """Milestone 12.2 contracts/components.md §1: each group a section labelled by its `h2`
    header, a plural and a singular total, a 200-character name, and a data table inside each,
    with the "(deleted)" and "Already in this competition" row notes."""
    body = admin_client.get(GALLERY).text
    section = gallery_section(body, "region-group")
    groups = [g for g in section.find_all("section") if "region-group" in g.classes()]
    assert len(groups) == 3
    headers = []
    for group in groups:
        (header,) = group.find_all("h2")
        assert "region-group-header" in header.classes()
        assert header.attrs["id"] == group.attrs["aria-labelledby"]
        (table,) = group.find_all("table")
        assert "data-table" in table.classes()
        assert table.find_all("caption") == []
        headers.append(header.text())
    assert headers[:2] == ["Kyiv · 14 teams", "Lviv · 1 team"]
    assert headers[2].endswith(" · 3 teams")
    assert len(headers[2]) == 200 + len(" · 3 teams")
    assert len({g.attrs["aria-labelledby"] for g in groups}) == 3
    notes = [s.text() for s in section.find_all("span") if "row-note" in s.classes()]
    assert notes == ["(deleted)", "Already in this competition"]


def test_the_local_time_variants(admin_client: TestClient) -> None:
    """Milestone 12.1 contracts/components.md §4: the same moment with a zone and without."""
    section = gallery_section(admin_client.get(GALLERY).text, "time")
    times = [(t.attrs.get("datetime"), t.text()) for t in section.find_all("time")]
    assert times == [
        ("2027-03-14T08:00Z", "14 March 2027, 10:00"),
        ("2027-03-14T08:00Z", "14 March 2027, 08:00 UTC"),
    ]


def test_the_date_and_time_pair(admin_client: TestClient) -> None:
    """Milestone 12.1 contracts/components.md §2: a date and a time field, the zone hint and the
    hidden zone, each error beside its field."""
    body = admin_client.get(GALLERY).text
    section = gallery_section(body, "forms")
    pairs = [f for f in section.find_all("fieldset") if "date-time-fields" in f.classes()]
    assert len(pairs) == 3
    for fieldset in pairs:
        assert fieldset.find_all("legend")[0].text() == "Start"
        inputs = [(i.attrs.get("type"), "required" in i.attrs) for i in fieldset.find_all("input")]
        assert inputs == [("date", True), ("time", True), ("hidden", False)]
    filled = pairs[1]
    assert [i.attrs.get("value") for i in filled.find_all("input")] == [
        "2027-03-14",
        "10:00",
        "Europe/Kyiv",
    ]
    assert "Time zone: Europe/Kyiv" in filled.text()
    assert html.field_error(body, "gallery-start-errors_date") == "Enter a real start date."
    assert html.field_error(body, "gallery-start-errors_time") == (
        "There is no 03:30 on 28 March 2027 in Europe/Kyiv because the clocks go forward."
        " Enter another time."
    )


def test_the_confirmation_with_a_back_label(admin_client: TestClient) -> None:
    """Milestone 12.1 contracts/components.md §5: a time in the question, and **Keep
    competition** as the link back."""
    section = gallery_section(admin_client.get(GALLERY).text, "confirmations")
    (keep,) = [c for c in section.find_all("section") if "Keep competition" in c.text()]
    assert keep.find_all("h1")[0].text() == (
        "Cancel competition “Spring final” of Chemistry, starting 14 March 2027, 10:00?"
    )
    assert len(keep.find_all("time")) == 1
    assert [a.text() for a in keep.find_all("a")] == ["Keep competition"]


def test_the_primary_confirmation(admin_client: TestClient) -> None:
    """Milestone 12.4 contracts/components.md §1: a second confirmation whose button is primary
    (no destructive class), with **Keep in progress** as the link back."""
    section = gallery_section(admin_client.get(GALLERY).text, "confirmations")
    (finish,) = [c for c in section.find_all("section") if "Keep in progress" in c.text()]
    assert finish.find_all("h1")[0].text() == (
        "Finish competition “Spring round” of Chemistry, started 14 March 2027, 10:00?"
    )
    buttons = finish.find_all("button")
    assert [(b.text(), b.classes()) for b in buttons] == [("Finish competition", [])]
    assert [a.text() for a in finish.find_all("a")] == ["Keep in progress"]
    others = [c for c in section.find_all("section") if "Keep competition" in c.text()]
    assert [b.classes() for b in others[0].find_all("button")] == [["destructive"]]


def test_the_grading_sheet(admin_client: TestClient) -> None:
    """Milestone 12.4 contracts/components.md §2: one post form holding the hidden field, an
    `ol.answer-sheet` of three numbered text cards, each with its reference answer; questions 1 and
    3 with a labelled text field (numeric keypad, the hint, the "Not graded" placeholder), question
    2 "Not answered" with no field; question 3 invalid and linked from the error summary; one
    primary "Save grades". Then the read-only variant with grades and without: no form, no field,
    no reference answer."""
    body = admin_client.get(GALLERY).text
    section = gallery_section(body, "grading-sheet")
    (summary,) = [e for e in section.iter() if "error-summary" in e.classes()]
    assert [a.attrs["href"] for a in summary.find_all("a")] == ["#gallery-grade-3"]
    (form,) = section.find_all("form")
    assert form.attrs["method"] == "post"
    sheets = [o for o in section.find_all("ol") if "answer-sheet" in o.classes()]
    assert len(sheets) == 3
    sheet, with_grades, without_grades = sheets
    assert sheet.start > form.start and sheet.end < form.end
    items = sheet.find_all("li")
    assert len(items) == 3
    for number, item in enumerate(items, start=1):
        (card,) = item.find_all("article")
        assert "text-card" in card.classes()
        assert card.find_all("h3")[0].text() == f"Question {number}"
        assert "Reference answer" in card.text()
    for number in (1, 3):
        item = items[number - 1]
        field_id = f"gallery-grade-{number}"
        (field,) = [i for i in item.find_all("input")]
        assert field.attrs["type"] == "text"
        assert field.attrs["inputmode"] == "numeric"
        assert field.attrs["placeholder"] == "Not graded"
        assert field.attrs["id"] == field.attrs["name"] == field_id
        for absent in ("pattern", "maxlength", "min", "max"):
            assert absent not in field.attrs
        (label,) = item.find_all("label")
        assert label.attrs["for"] == field_id
        assert label.text() == f"Grade for question {number}"
        assert f"Answer to question {number}" in item.text()
        hints = [e.text() for e in item.iter() if e.attrs.get("id") == f"{field_id}-hint"]
        assert hints == ["A whole number from 0 to 10."]
    assert items[0].find_all("input")[0].attrs["value"] == "7"
    assert "aria-invalid" not in items[0].find_all("input")[0].attrs
    assert items[2].find_all("input")[0].attrs["aria-invalid"] == "true"
    assert html.field_error(body, "gallery-grade-3") == "Enter a whole number from 0 to 10."
    assert items[1].find_all("input") == [] and items[1].find_all("label") == []
    assert "Not answered" in items[1].text()
    buttons = form.find_all("button")
    assert [(b.text(), b.classes()) for b in buttons] == [("Save grades", [])]
    assert buttons[0].start > sheet.end
    assert not [a for a in form.find_all("a") if a.text() == "Cancel"]
    for read_only in (with_grades, without_grades):
        assert read_only.start > form.end
        assert read_only.find_all("input") == []
        assert read_only.find_all("button") == []
        assert "Reference answer" not in read_only.text()
        assert "Answer to question 1" in read_only.text()
        assert "Not answered" in read_only.text()
    assert "Grade: 7 of 10" in with_grades.text()
    assert "Not graded yet" in with_grades.text()
    assert "Grade:" not in without_grades.text()
    assert "Not graded yet" not in without_grades.text()


def test_the_filter_links(admin_client: TestClient) -> None:
    """Milestone 12.4 contracts/components.md §3: a labelled `nav.filter-links`, exactly one link
    current with `aria-current="true"`, never `"page"`."""
    section = gallery_section(admin_client.get(GALLERY).text, "filter-links")
    (nav,) = section.find_all("nav")
    assert nav.classes() == ["filter-links"]
    assert nav.attrs["aria-label"] == "Show"
    links = [(a.text(), a.attrs.get("aria-current")) for a in nav.find_all("a")]
    assert links == [("All teams", "true"), ("Ungraded only", None)]


def test_the_option_group(admin_client: TestClient) -> None:
    """Milestone 12.1 contracts/components.md §6: a deactivated subject in its group, selected."""
    section = gallery_section(admin_client.get(GALLERY).text, "selectors")
    (group,) = section.find_all("optgroup")
    assert group.attrs.get("label") == "Deactivated subjects"
    assert [(o.text(), "selected" in o.attrs) for o in group.find_all("option")] == [
        ("Astronomy", True)
    ]


def test_the_gallery_is_no_tab(admin_client: TestClient) -> None:
    body = admin_client.get(GALLERY).text
    tabs = html.nav(body, "Administrator area")
    assert tabs, "the gallery is inside the administrator area"
    assert GALLERY not in [tab.href for tab in tabs]
    assert [tab for tab in tabs if tab.attrs.get("aria-current")] == []


@pytest.mark.parametrize(
    ("email", "role"),
    [
        (TEACHER_EMAIL, Role.TEACHER),
        (STUDENT_EMAIL, Role.STUDENT),
        (ADMIN_STUDENT_EMAIL, Role.STUDENT),
    ],
)
def test_other_current_roles_are_refused(client_as: ClientAs, email: str, role: Role) -> None:
    response = client_as(email, role).get(GALLERY)
    assert response.status_code == 403
    assert html.h1(response.text) == "Access denied"
    assert f"Your current role, {role.label}, cannot open this page." in response.text


def test_anonymous_visitors_are_sent_to_sign_in(client: TestClient) -> None:
    response = client.get(GALLERY, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Fadmin%2Fcomponents"


def test_the_gallery_reads_no_data(admin_client: TestClient) -> None:
    """FR-037: the handler takes no session. Every request still reads the visitor's session and
    roles to authorise it (`resolve_access`), so those are the only statements allowed."""
    statements: list[str] = []

    def record(*args: Any) -> None:
        statements.append(args[2])

    event.listen(app.state.engine, "before_cursor_execute", record)
    try:
        assert admin_client.get(GALLERY).status_code == 200
    finally:
        event.remove(app.state.engine, "before_cursor_execute", record)
    tables = {table for statement in statements for table in re.findall(r"FROM (\w+)", statement)}
    assert tables, "no statement was recorded"
    assert tables <= {"sessions", "users", "user_roles"}, tables


@pytest.mark.usefixtures("production")
@pytest.mark.parametrize("who", ["anonymous", ADMIN_EMAIL, TEACHER_EMAIL, STUDENT_EMAIL])
def test_in_production_it_is_an_unknown_address_for_everyone(
    client: TestClient, client_as: ClientAs, who: str
) -> None:
    browser = client if who == "anonymous" else client_as(who)
    response = browser.get(GALLERY, follow_redirects=False)
    unknown = browser.get("/no-such-page", follow_redirects=False)
    assert response.status_code == unknown.status_code == 404
    assert response.text.replace(GALLERY, "/no-such-page") == unknown.text
