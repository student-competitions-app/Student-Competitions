"""The results file of a published competition: one PDF in one language (milestone 12.8).

See specs/012.8-publishing-results/contracts/results-file.md, contracts/services.md §2 and research
R1, R2, R8.

**Pure**: it takes a `ResultsSnapshot` and a language and returns the file's bytes. No session, no
request, no wall clock, so the same snapshot and language always give the same bytes, the
publishing transaction calls it once per language, and the sample script calls it with snapshots
built in memory.

**What a file holds**, in order: the logo of milestone 12.7 (dark ink, for white paper); the title
"Results of “<name>”"; the subject; the start and the finish in Kyiv time, labelled, and the date
of publishing; then a heading per region with one line per team, "School No. 5, Comets, 17", or
"No teams took part in this competition."; and "Page n of N" at the foot of every page. Every
label goes through the catalogues in the file's language; names are shown as entered, never
translated.

**The look** (layout, fonts, sizes, spacing, wording) is the starting point of the design review
rounds with the product owner (FR-038, `design-approval.md`): A4 portrait, 20 mm margins, Open Sans
Regular and Bold embedded as subsets (fpdf2), so Cyrillic renders on any device and the text can be
read back.
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.core.i18n import Language, _, use_language
from app.core.time_zone import format_local_date, format_local_time

if TYPE_CHECKING:
    from app.services.results import ResultsSnapshot

STATIC = Path(__file__).resolve().parent.parent / "static"
FONT_REGULAR = STATIC / "fonts" / "OpenSans-Regular.ttf"
FONT_BOLD = STATIC / "fonts" / "OpenSans-Bold.ttf"
LOGO = STATIC / "img" / "logo" / "logo-dark-192.png"
"""The emblem in dark ink (`#1c1c22`), for white paper (milestone 12.7)."""

FAMILY = "OpenSans"
PRODUCER = "Student Competitions"
PDF_LANGUAGE = {Language.UK: "uk-UA", Language.EN: "en-GB"}

MARGIN = 20.0
"""mm, on every side."""
LOGO_HEIGHT = 18.0
INK = (0x1C, 0x1C, 0x22)
MUTED = (0x5A, 0x5D, 0x6B)
RULE = (0xC8, 0xCB, 0xD3)

TITLE_SIZE = 16
META_SIZE = 10
REGION_SIZE = 12
LINE_SIZE = 10.5
FOOTER_SIZE = 9
RUNNING_SIZE = 8

TITLE_LEADING = 7.5
META_LEADING = 5.5
REGION_LEADING = 7.0
LINE_LEADING = 5.6
REGION_GAP = 6.0
"""Space above each region heading."""


class _ResultsDocument(FPDF):
    """An A4 page with the running title on every page after the first and the page number at
    the foot of every page. Pages are drawn inside `use_language`, so the footer's label is in
    the file's language; fpdf2 replaces `{nb}` with the page count when the file is written."""

    def __init__(self, running_title: str) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.running_title = running_title

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font(FAMILY, "", RUNNING_SIZE)
        self.set_text_color(*MUTED)
        self.set_y(MARGIN / 2)
        self.cell(0, 4, self.running_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(MARGIN)

    def footer(self) -> None:
        self.set_y(-MARGIN / 2 - 4)
        self.set_font(FAMILY, "", FOOTER_SIZE)
        self.set_text_color(*MUTED)
        label = _("Page %(page)d of %(total)s", page=self.page_no(), total="{nb}")
        self.cell(0, 4, str(label), align="C")


def _moment(moment: datetime) -> str:
    """A start or finish: the date and time in Kyiv time, labelled ("14 March 2027, 10:00 (Kyiv
    time)"), as the pages show a time when no browser zone is known (milestone 12.5)."""
    return format_local_time(moment, None)


def render_results_pdf(snapshot: "ResultsSnapshot", language: Language) -> bytes:
    """The results file of `snapshot` with every label in `language`."""
    with use_language(language):
        title = str(_("Results of “%(name)s”", name=snapshot.competition_name))
        document = _ResultsDocument(running_title=title)
        document.set_margins(MARGIN, MARGIN, MARGIN)
        document.set_auto_page_break(auto=True, margin=MARGIN)
        document.add_font(FAMILY, "", FONT_REGULAR)
        document.add_font(FAMILY, "B", FONT_BOLD)
        document.alias_nb_pages()
        document.set_title(title)
        document.set_lang(PDF_LANGUAGE[language])
        document.set_creation_date(snapshot.published_at)
        document.set_producer(PRODUCER)
        document.add_page()

        document.image(LOGO, x=MARGIN, y=MARGIN, h=LOGO_HEIGHT)
        document.set_y(MARGIN + LOGO_HEIGHT + 6)
        document.set_text_color(*INK)
        document.set_font(FAMILY, "B", TITLE_SIZE)
        document.multi_cell(0, TITLE_LEADING, title, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        document.ln(1.5)
        document.set_font(FAMILY, "", META_SIZE + 1)
        document.multi_cell(
            0,
            META_LEADING + 0.5,
            snapshot.subject_name,
            align="L",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        document.ln(1)
        document.set_font(FAMILY, "", META_SIZE)
        document.set_text_color(*MUTED)
        meta = (
            str(_("Started: %(moment)s", moment=_moment(snapshot.starts_at))),
            str(_("Finished: %(moment)s", moment=_moment(snapshot.finished_at))),
            str(_("Published: %(date)s", date=format_local_date(snapshot.published_at, None))),
        )
        for text in meta:
            document.multi_cell(
                0, META_LEADING, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
            )
        document.set_text_color(*INK)

        if not snapshot.regions:
            document.ln(REGION_GAP)
            document.set_font(FAMILY, "", LINE_SIZE)
            document.multi_cell(
                0, LINE_LEADING, str(_("No teams took part in this competition.")), align="L"
            )
        for region in snapshot.regions:
            # Never leave a region heading alone at the foot of a page.
            if document.will_page_break(REGION_GAP + REGION_LEADING + 2 + LINE_LEADING):
                document.add_page()
            else:
                document.ln(REGION_GAP)
            document.set_font(FAMILY, "B", REGION_SIZE)
            document.multi_cell(
                0, REGION_LEADING, region.name, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
            )
            y = document.get_y() + 0.6
            document.set_draw_color(*RULE)
            document.set_line_width(0.3)
            document.line(MARGIN, y, document.w - MARGIN, y)
            document.set_y(y + 1.6)
            document.set_font(FAMILY, "", LINE_SIZE)
            for line in region.lines:
                text = str(
                    _(
                        "%(institution)s, %(team)s, %(score)d",
                        institution=line.institution,
                        team=line.team,
                        score=line.score,
                    )
                )
                document.multi_cell(
                    0, LINE_LEADING, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
                )
        return bytes(document.output())
