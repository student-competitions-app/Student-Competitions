"""Query rendered pages by meaning, not by markup.

See specs/010-design-system-ui-guidelines/research.md D17.

Milestone 10 rebuilds every template, so a test that matches literal markup (`<td class="…">`,
`<nav class="admin-tabs"`) fails for reasons that are not regressions. These helpers answer the
questions the tests actually ask — which heading, which links, which forms and fields, which rows,
which messages — so the tests keep asserting behaviour exactly (addresses, methods, texts,
statuses) while the markup is free to change.

Built on the standard library's `html.parser`, with no third-party dependency. Every function
takes the response body as `str`. Text is returned with its whitespace collapsed and stripped,
and with character references decoded, so `'` is compared as `'` and not as `&#39;`.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import NamedTuple

from app.core.config import APP_NAME

VOID_ELEMENTS = frozenset(
    {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
        "track", "wbr",
    }
)  # fmt: skip
REGION_TAGS = ("header", "main", "footer")


@dataclass(eq=False)
class Element:
    """One element of the parsed page, with the source offsets of its HTML: `start`/`end` around
    the whole element, `inner_start`/`inner_end` around its content."""

    tag: str
    attrs: dict[str, str]
    parent: "Element | None" = None
    children: list["Element | str"] = field(default_factory=list)
    start: int = 0
    end: int | None = None
    inner_start: int = 0
    inner_end: int | None = None

    def iter(self) -> Iterator["Element"]:
        """This element and every element inside it, in document order."""
        yield self
        for child in self.children:
            if isinstance(child, Element):
                yield from child.iter()

    def find_all(self, tag: str) -> list["Element"]:
        return [element for element in self.iter() if element.tag == tag and element is not self]

    def classes(self) -> list[str]:
        return self.attrs.get("class", "").split()

    def text(self) -> str:
        return _collapse("".join(self._raw_text()))

    def _raw_text(self) -> Iterator[str]:
        for child in self.children:
            if isinstance(child, Element):
                yield from child._raw_text()
            else:
                yield child


def _collapse(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class _TreeBuilder(HTMLParser):
    def __init__(self, body: str) -> None:
        super().__init__(convert_charrefs=True)
        self.body = body
        self.line_starts = [0] + [m.end() for m in re.finditer(r"\n", body)]
        self.root = Element("#document", {}, inner_start=0, inner_end=len(body))
        self.stack = [self.root]

    def _offset(self) -> int:
        line, column = self.getpos()
        return self.line_starts[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        start_tag = self.get_starttag_text() or ""
        start = self._offset()
        element = Element(
            tag,
            {name: value or "" for name, value in attrs},
            parent=self.stack[-1],
            start=start,
            inner_start=start + len(start_tag),
        )
        self.stack[-1].children.append(element)
        if tag in VOID_ELEMENTS:
            element.inner_end = element.end = element.inner_start
        else:
            self.stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        # Tolerant: close up to the matching open element; ignore a stray end tag.
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                end = self._offset()
                after = self.body.find(">", end) + 1 or len(self.body)
                for element in self.stack[depth:]:
                    element.inner_end = end
                    element.end = end if element is not self.stack[depth] else after
                del self.stack[depth:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def parse(body: str) -> Element:
    """The page as a tree; the functions below are built on it."""
    builder = _TreeBuilder(body)
    builder.feed(body)
    builder.close()
    return builder.root


def outer_html(body: str, element: Element) -> str:
    """The element's own source, tags included, so it can be queried again as a fragment."""
    return body[element.start : element.end]


def _scopes(body: str, within: str | None) -> list[Element]:
    root = parse(body)
    return [root] if within is None else root.find_all(within)


def _unique(elements: Iterator[Element]) -> list[Element]:
    seen: set[int] = set()
    found = []
    for element in elements:
        if id(element) not in seen:
            seen.add(id(element))
            found.append(element)
    return found


def text(body: str, within: str | None = None) -> str:
    """The visible text of the page, or of every `within` element (joined by a space)."""
    return _collapse(" ".join(scope.text() for scope in _scopes(body, within)))


def h1(body: str) -> str:
    """The text of the page's only `h1`."""
    headings = parse(body).find_all("h1")
    assert len(headings) == 1, f"expected exactly one <h1>, found {len(headings)}"
    return headings[0].text()


class Link(NamedTuple):
    href: str
    text: str
    attrs: dict[str, str]


def _links_in(scopes: list[Element]) -> list[Link]:
    anchors = _unique(a for scope in scopes for a in scope.find_all("a"))
    return [Link(a.attrs["href"], a.text(), a.attrs) for a in anchors if "href" in a.attrs]


def links(body: str, within: str | None = None) -> list[Link]:
    """Every link with an `href`; `within` is a tag name (`"header"`, `"main"`, `"footer"`,
    `"details"`, `"nav"`) limiting the search to those elements."""
    return _links_in(_scopes(body, within))


def content_links(body: str) -> list[Link]:
    """The links of the page's own content: inside `<main>`, outside any `<nav>` or `<header>`,
    so a tab or the top bar never satisfies "the page links back to …"."""

    def in_frame(element: Element) -> bool:
        parent = element.parent
        while parent is not None:
            if parent.tag in ("nav", "header"):
                return True
            parent = parent.parent
        return False

    anchors = _unique(a for main in parse(body).find_all("main") for a in main.find_all("a"))
    return [
        Link(a.attrs["href"], a.text(), a.attrs)
        for a in anchors
        if "href" in a.attrs and not in_frame(a)
    ]


class Button(NamedTuple):
    name: str | None
    value: str | None
    text: str
    attrs: dict[str, str]


class Input(NamedTuple):
    name: str | None
    type: str
    value: str


class Form(NamedTuple):
    method: str
    action: str
    buttons: list[Button]
    inputs: list[Input]
    attrs: dict[str, str]
    text: str


def _input(element: Element) -> Input:
    name = element.attrs.get("name")
    if element.tag == "select":
        options = element.find_all("option")
        chosen = [o for o in options if "selected" in o.attrs] or options[:1]
        value = chosen[0].attrs.get("value", chosen[0].text()) if chosen else ""
        return Input(name, "select", value)
    if element.tag == "textarea":
        return Input(name, "textarea", "".join(c for c in element.children if isinstance(c, str)))
    return Input(name, element.attrs.get("type", "text").lower(), element.attrs.get("value", ""))


def _form(element: Element) -> Form:
    controls = [e for e in element.iter() if e.tag in ("input", "select", "textarea")]
    buttons = [
        Button(b.attrs.get("name"), b.attrs.get("value"), b.text(), b.attrs)
        for b in element.find_all("button")
    ]
    return Form(
        element.attrs.get("method", "get").lower(),
        element.attrs.get("action", ""),
        buttons,
        [_input(c) for c in controls],
        element.attrs,
        element.text(),
    )


def forms(body: str, within: str | None = None) -> list[Form]:
    """Every form, in document order. `inputs` holds the inputs (hidden ones included), selects
    (type `"select"`, value the selected option) and textareas; `buttons` the `<button>`s."""
    return [_form(f) for f in _unique(f for s in _scopes(body, within) for f in s.find_all("form"))]


def control(body: str, name: str) -> dict[str, str]:
    """The attributes of the one form control (input, select, textarea) named `name`, with
    `"tag"` added, so a test can check `value`, `required`, `aria-invalid`, …"""
    found = [
        e
        for e in parse(body).iter()
        if e.tag in ("input", "select", "textarea") and e.attrs.get("name") == name
    ]
    assert len(found) == 1, f"expected one control named {name!r}, found {len(found)}"
    return {"tag": found[0].tag, **found[0].attrs}


class Option(NamedTuple):
    value: str
    text: str
    selected: bool


def options(body: str, name: str) -> list[Option]:
    """The options of the one `<select>` named `name`, in order."""
    selects = [e for e in parse(body).find_all("select") if e.attrs.get("name") == name]
    assert len(selects) == 1, f"expected one select named {name!r}, found {len(selects)}"
    return [
        Option(o.attrs.get("value", o.text()), o.text(), "selected" in o.attrs)
        for o in selects[0].find_all("option")
    ]


def details(body: str) -> list[tuple[str, str]]:
    """`(term, description)` for every `<dt>`/`<dd>` pair of the page's description lists."""
    pairs = []
    for dl in parse(body).find_all("dl"):
        term = None
        for child in dl.iter():
            if child.tag == "dt":
                term = child.text()
            elif child.tag == "dd" and term is not None:
                pairs.append((term, child.text()))
    return pairs


def form_targets(body: str, within: str | None = None) -> list[tuple[str, str]]:
    """`(method, action)` of every form: the shorthand for "the page posts to …"."""
    return [(f.method, f.action) for f in forms(body, within)]


def link_pairs(body: str, within: str | None = None) -> list[tuple[str, str]]:
    """`(href, text)` of every link: the shorthand for "the page links to … as …"."""
    return [(link.href, link.text) for link in links(body, within)]


def nav(body: str, label: str) -> list[Link]:
    """The links inside `<nav aria-label="{label}">`; empty when there is no such nav."""
    navs = [n for n in parse(body).find_all("nav") if n.attrs.get("aria-label") == label]
    return _links_in(navs)


class PageEntry(NamedTuple):
    """One entry of a page navigation: Previous, a page number, a gap (`…`) or Next."""

    text: str
    href: str | None
    """`None` for text: an unavailable Previous or Next, or a gap."""
    current: bool


def pagination(body: str, label: str) -> tuple[str, list[PageEntry]] | None:
    """The range text and the entries of `<nav class="pagination" aria-label="{label}">`, or
    `None` when the page has no such nav."""
    navs = [n for n in parse(body).find_all("nav") if n.attrs.get("aria-label") == label]
    if not navs:
        return None
    (found,) = navs
    assert "pagination" in found.classes()
    (range_text,) = [p.text() for p in found.find_all("p") if "pagination-range" in p.classes()]
    entries = []
    for item in found.find_all("li"):
        (inner,) = [e for e in item.children if isinstance(e, Element)]
        href = inner.attrs.get("href") if inner.tag == "a" else None
        current = inner.attrs.get("aria-current") == "page"
        entries.append(PageEntry(inner.text(), href, current))
    return range_text, entries


def region(body: str, tag: str) -> str:
    """The inner HTML of the page's first `header`, `main` or `footer`."""
    assert tag in REGION_TAGS, f"region() takes one of {REGION_TAGS}"
    found = parse(body).find_all(tag)
    assert found, f"the page has no <{tag}>"
    return body[found[0].inner_start : found[0].inner_end]


def badges(body: str) -> list[str]:
    """The texts of the status badges, in document order."""
    return [e.text() for e in parse(body).iter() if "badge" in e.classes()]


def notices(body: str) -> list[tuple[str, str]]:
    """`(role, text)` for every element with `role="status"` or `role="alert"`."""
    return [
        (e.attrs["role"], e.text())
        for e in parse(body).iter()
        if e.attrs.get("role") in ("status", "alert")
    ]


class Summary(NamedTuple):
    heading: str
    items: list[tuple[str | None, str]]


def error_summary(body: str) -> Summary | None:
    """The error summary: its heading and, per entry, the link target (`None` for a message
    about the whole form) and the text. `None` when the page has no summary."""
    found = [e for e in parse(body).iter() if "error-summary" in e.classes()]
    if not found:
        return None
    assert len(found) == 1, f"expected one error summary, found {len(found)}"
    summary = found[0]
    headings = [e for e in summary.iter() if e.tag in ("h2", "h3")]
    items = []
    for item in summary.find_all("li"):
        anchors = [a for a in item.find_all("a") if "href" in a.attrs]
        items.append((anchors[0].attrs["href"] if anchors else None, item.text()))
    return Summary(headings[0].text() if headings else "", items)


def field_error(body: str, field_id: str) -> str | None:
    """The text of the element with `id="{field_id}-error"`, or `None`."""
    for element in parse(body).iter():
        if element.attrs.get("id") == f"{field_id}-error":
            return element.text()
    return None


def table_rows(body: str) -> list[dict[str, str]]:
    """One dict per `<tbody>` row of every table, keyed by each cell's `data-label`, falling back
    to the matching header cell's text by column index."""
    rows = []
    for table in parse(body).find_all("table"):
        headers = [th.text() for thead in table.find_all("thead") for th in thead.find_all("th")]
        for tbody in table.find_all("tbody"):
            for tr in tbody.find_all("tr"):
                cells = [c for c in tr.children if isinstance(c, Element) and c.tag in ("td", "th")]
                row = {}
                for index, cell in enumerate(cells):
                    label = cell.attrs.get("data-label")
                    if not label:
                        label = headers[index] if index < len(headers) else str(index)
                    row[label] = cell.text()
                rows.append(row)
    return rows


def html_attrs(body: str) -> dict[str, str]:
    """The attributes of the `<html>` element."""
    found = parse(body).find_all("html")
    assert found, "the page has no <html>"
    return found[0].attrs


def meta(body: str, name: str) -> str | None:
    """The `content` of `<meta name="{name}">`, or `None`."""
    for element in parse(body).find_all("meta"):
        if element.attrs.get("name") == name:
            return element.attrs.get("content", "")
    return None


def role_label(body: str) -> str:
    """The top bar's text without the application name and without its forms (role switch,
    Log out): what is left is the current role's label and the address."""
    header = text(body, "header")
    for form in forms(body, within="header"):
        header = header.replace(form.text, "")
    return _collapse(header.replace(APP_NAME, ""))
