"""Paging: the page number from an address, and the model behind the page navigation component.

See specs/011-question-bank/research.md R9 and contracts/services.md §services/paging. Pure, no
I/O. The logic belongs to the page navigation component (`components/pagination.html`), not to
questions: milestones 12 and 15 page their lists with it too.

A page number past the end is clamped to the last page rather than redirected, so the address
keeps what was typed and the navigation marks the real page.
"""

from dataclasses import dataclass
from math import ceil

PAGE_SIZE = 10
MAX_PAGE = 999_999_999
"""The largest page number read from an address: more than 9 digits reads as this, which is
then clamped to the last page. It also keeps Python's limit on long integer strings away."""


def parse_page(raw: str | None) -> int:
    """The page asked for: 1 for a missing, empty, non-ASCII-digit or zero value; `MAX_PAGE` for
    more than 9 digits. Never raises."""
    if raw is None or not raw.isascii() or not raw.isdigit():
        return 1
    if len(raw) > len(str(MAX_PAGE)):
        return MAX_PAGE
    return int(raw) or 1


@dataclass(frozen=True)
class PageLink:
    """One entry of the page list: a page number, or a gap (`number is None`)."""

    number: int | None
    current: bool


@dataclass(frozen=True)
class Paging:
    """One page of a list of `total` items, `size` per page."""

    number: int
    """The current page, 1..last."""
    last: int
    """The last page: at least 1, even for an empty list."""
    total: int
    size: int
    first_item: int
    """1-based position of the page's first item; 0 when the list is empty."""
    last_item: int
    previous: int | None
    next: int | None
    links: tuple[PageLink, ...]
    offset: int
    """How many items come before this page: `(number - 1) * size`."""

    @classmethod
    def build(cls, page: int, total: int, size: int = PAGE_SIZE) -> "Paging":
        """The paging for `page`, clamped to 1..last."""
        last = max(1, ceil(total / size))
        number = min(max(page, 1), last)
        offset = (number - 1) * size
        return cls(
            number=number,
            last=last,
            total=total,
            size=size,
            first_item=offset + 1 if total else 0,
            last_item=min(offset + size, total),
            previous=number - 1 if number > 1 else None,
            next=number + 1 if number < last else None,
            links=_links(number, last),
            offset=offset,
        )


def _links(number: int, last: int) -> tuple[PageLink, ...]:
    """The first and last pages, the current page and one on each side. A hidden run of two or
    more pages becomes one gap; a run of one is shown, since a gap would take the same room."""
    shown = {1, last, number - 1, number, number + 1}
    links: list[PageLink] = []
    page = 1
    while page <= last:
        if page in shown:
            links.append(PageLink(page, page == number))
            page += 1
            continue
        run_end = page
        while run_end + 1 <= last and run_end + 1 not in shown:
            run_end += 1
        if run_end == page:
            links.append(PageLink(page, False))
        else:
            links.append(PageLink(None, False))
        page = run_end + 1
    return tuple(links)
