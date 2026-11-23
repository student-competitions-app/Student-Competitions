"""The design shared by every PDF file of the application: the results file (milestone 12.8), a
competition's questions file and a subject's study materials (milestone 12.10).

See specs/012.8-publishing-results/contracts/results-file.md and
specs/012.10-questions-study-materials/contracts/services.md §1, research R3. One place for the
page, the fonts, the colours and the header, so the three files keep one look through the design
review rounds with the product owner.

**The look**: A4 portrait, 20 mm margins, Open Sans Regular and Bold embedded as subsets (fpdf2),
so Cyrillic renders on any device and the text can be read back; the logo of milestone 12.7 in
dark ink at the top left; the title in bold, the subject, then the muted meta lines; a running
title on every page after the first; "Page n of N" at the foot of every page.

**Pure**: no session, no request, no clock. Every function is called inside `use_language`, so
the footer's label is in the file's language.
"""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.core.i18n import Language, _

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
HEADING_FILL = (0xEE, 0xF0, 0xF4)

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
"""Space above each region heading of the results file, and above the body of the other files."""
CELL_PADDING = 1.6
"""mm, around the text of every table cell."""


class PdfDocument(FPDF):
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


def open_document(
    title: str, language: Language, created_at: datetime, running_title: str | None = None
) -> PdfDocument:
    """A new document with its first page added: the margins, the automatic page break, both
    fonts, the page count alias and the metadata (`/Title` is `title`). The running title of the
    pages after the first is `running_title`, or `title` when it is `None`."""
    document = PdfDocument(running_title=title if running_title is None else running_title)
    document.set_margins(MARGIN, MARGIN, MARGIN)
    document.set_auto_page_break(auto=True, margin=MARGIN)
    document.add_font(FAMILY, "", FONT_REGULAR)
    document.add_font(FAMILY, "B", FONT_BOLD)
    document.alias_nb_pages()
    document.set_title(title)
    document.set_lang(PDF_LANGUAGE[language])
    document.set_creation_date(created_at)
    document.set_producer(PRODUCER)
    document.add_page()
    return document


def draw_header(document: FPDF, title: str, subject: str, meta: Sequence[str]) -> None:
    """The logo, the title in bold, the subject, then the muted meta lines; the ink is back to
    `INK` afterwards."""
    document.image(LOGO, x=MARGIN, y=MARGIN, h=LOGO_HEIGHT)
    document.set_y(MARGIN + LOGO_HEIGHT + 6)
    document.set_text_color(*INK)
    document.set_font(FAMILY, "B", TITLE_SIZE)
    document.multi_cell(0, TITLE_LEADING, title, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    document.ln(1.5)
    document.set_font(FAMILY, "", META_SIZE + 1)
    document.multi_cell(
        0, META_LEADING + 0.5, subject, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    document.ln(1)
    document.set_font(FAMILY, "", META_SIZE)
    document.set_text_color(*MUTED)
    for text in meta:
        document.multi_cell(0, META_LEADING, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    document.set_text_color(*INK)
