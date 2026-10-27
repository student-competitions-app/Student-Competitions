"""Paging: the page number from an address, the range, the ends and the gap rule.

See specs/011-question-bank/research.md R9 and contracts/services.md §services/paging (US2-10,
US2-11, SC-005). The gap table is checked against hand-written cases and, for every page of
every list of 1–12 pages and of 200 pages, against the rule stated independently below.
"""

import pytest

from app.services.paging import MAX_PAGE, PAGE_SIZE, Paging, parse_page


@pytest.mark.parametrize(
    "raw", [None, "", "abc", "-1", "0", "00", "+2", "1.5", " 2", "٣"], ids=repr
)
def test_a_value_that_is_not_a_page_reads_as_the_first(raw: str | None) -> None:
    assert parse_page(raw) == 1


@pytest.mark.parametrize(
    ("raw", "page"), [("1", 1), ("4", 4), ("007", 7), ("999999999", 999_999_999)]
)
def test_a_page_number_is_read(raw: str, page: int) -> None:
    assert parse_page(raw) == page


@pytest.mark.parametrize("raw", ["1" * 10, "9" * 5000], ids=["ten-digits", "five-thousand"])
def test_a_very_long_number_reads_as_the_largest_page(raw: str) -> None:
    assert parse_page(raw) == MAX_PAGE


def test_the_page_size_is_ten() -> None:
    assert PAGE_SIZE == 10


@pytest.mark.parametrize(
    ("page", "total", "number", "last", "first_item", "last_item"),
    [
        (4, 200, 4, 20, 31, 40),
        (3, 25, 3, 3, 21, 25),
        (1, 1, 1, 1, 1, 1),
        (1, 0, 1, 1, 0, 0),
        (5, 0, 1, 1, 0, 0),
        (0, 25, 1, 3, 1, 10),
        (99, 25, 3, 3, 21, 25),
        (MAX_PAGE, 200, 20, 20, 191, 200),
    ],
)
def test_the_range(
    page: int, total: int, number: int, last: int, first_item: int, last_item: int
) -> None:
    paging = Paging.build(page, total)
    assert (paging.number, paging.last, paging.total) == (number, last, total)
    assert (paging.first_item, paging.last_item) == (first_item, last_item)
    assert paging.offset == (number - 1) * PAGE_SIZE
    assert paging.size == PAGE_SIZE


def test_previous_and_next_at_the_ends() -> None:
    first, middle, last = Paging.build(1, 25), Paging.build(2, 25), Paging.build(3, 25)
    assert (first.previous, first.next) == (None, 2)
    assert (middle.previous, middle.next) == (1, 3)
    assert (last.previous, last.next) == (2, None)
    only = Paging.build(1, 5)
    assert (only.previous, only.next) == (None, None)


def _rendered(paging: Paging) -> str:
    return " ".join("…" if link.number is None else str(link.number) for link in paging.links)


@pytest.mark.parametrize(
    ("page", "last", "expected"),
    [
        (1, 1, "1"),
        (1, 2, "1 2"),
        (1, 4, "1 2 3 4"),
        (1, 5, "1 2 … 5"),
        (3, 5, "1 2 3 4 5"),
        (4, 7, "1 2 3 4 5 6 7"),
        (4, 8, "1 2 3 4 5 … 8"),
        (5, 9, "1 … 4 5 6 … 9"),
        (3, 20, "1 2 3 4 … 20"),
        (10, 20, "1 … 9 10 11 … 20"),
        (20, 20, "1 … 19 20"),
        (19, 20, "1 … 18 19 20"),
        (4, 200, "1 2 3 4 5 … 200"),
        (100, 200, "1 … 99 100 101 … 200"),
    ],
)
def test_the_gap_table(page: int, last: int, expected: str) -> None:
    assert _rendered(Paging.build(page, last * PAGE_SIZE)) == expected


def _expected_by_the_rule(number: int, last: int) -> str:
    """The rule from R9, stated without the module's algorithm: a page is shown if it is the first,
    the last, the current or next to it, or if it is a lone hidden page between shown ones."""
    core = {1, last, number - 1, number, number + 1}
    shown = [
        page
        for page in range(1, last + 1)
        if page in core or (page - 1 in core and page + 1 in core)
    ]
    entries: list[str] = []
    for index, page in enumerate(shown):
        if index and page - shown[index - 1] > 1:
            entries.append("…")
        entries.append(str(page))
    return " ".join(entries)


CASES = [(page, last) for last in [*range(1, 13), 200] for page in range(1, last + 1)]


@pytest.mark.parametrize(("page", "last"), CASES)
def test_every_page_follows_the_gap_rule(page: int, last: int) -> None:
    paging = Paging.build(page, last * PAGE_SIZE)
    assert _rendered(paging) == _expected_by_the_rule(page, last)
    assert len(paging.links) <= 7
    current = [link for link in paging.links if link.current]
    assert len(current) == 1
    assert current[0].number == paging.number == page
