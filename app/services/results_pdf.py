"""The results file of a published competition: one PDF in one language (milestone 12.8).

See specs/012.8-publishing-results/contracts/results-file.md, contracts/services.md §2 and research
R1, R2, R8.

**Pure**: it takes a `ResultsSnapshot` and a language and returns the file's bytes. No session, no
request, no wall clock, so the same snapshot and language always give the same bytes, the
publishing transaction calls it once per language, and the sample script calls it with snapshots
built in memory.

**What a file holds**, in order: the logo of milestone 12.7 (dark ink, for white paper); the title
"Results of “<name>”"; the subject; the start and the finish in Kyiv time, labelled, the date of
publishing and the maximum score; then a heading per region over a table of its teams
(educational institution, team, score; the score column just wide enough for the score), or "No
teams took part in this competition."; and "Page n of N" at the foot of every page. Every
label goes through the catalogues in the file's language; names are shown as entered, never
translated.

**The look** (layout, fonts, sizes, spacing, wording) was approved by the product owner (FR-038,
`design-approval.md`). The page, the fonts, the colours and the header are shared with the files of
milestone 12.10 through `app.services.pdf_layout`; this module draws only the results' body.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from fpdf import FPDF
from fpdf.enums import TableBordersLayout, XPos, YPos
from fpdf.fonts import FontFace

from app.core.i18n import Language, _, use_language
from app.core.time_zone import format_local_date, format_local_time
from app.services.pdf_layout import (
    CELL_PADDING,
    FAMILY,
    FONT_BOLD,
    FONT_REGULAR,
    HEADING_FILL,
    LINE_LEADING,
    LINE_SIZE,
    REGION_GAP,
    REGION_LEADING,
    REGION_SIZE,
    RULE,
    draw_header,
    open_document,
)

if TYPE_CHECKING:
    from app.services.results import RegionResults, ResultsSnapshot

__all__ = ["FONT_BOLD", "FONT_REGULAR", "render_results_pdf"]
"""`FONT_BOLD` and `FONT_REGULAR` stay importable here for the 12.8 tests of the embedded fonts."""

INSTITUTION_SHARE = 0.56
"""Of the width left after the score column: the educational institution's column; the team's
takes the rest."""


def _moment(moment: datetime) -> str:
    """A start or finish: the date and time in Kyiv time, labelled ("14 March 2027, 10:00 (Kyiv
    time)"), as the pages show a time when no browser zone is known (milestone 12.5)."""
    return format_local_time(moment, None)


def render_results_pdf(snapshot: "ResultsSnapshot", language: Language) -> bytes:
    """The results file of `snapshot` with every label in `language`."""
    with use_language(language):
        title = str(_("Results of “%(name)s”", name=snapshot.competition_name))
        meta = (
            str(_("Started: %(moment)s", moment=_moment(snapshot.starts_at))),
            str(_("Finished: %(moment)s", moment=_moment(snapshot.finished_at))),
            str(_("Published: %(date)s", date=format_local_date(snapshot.published_at, None))),
            str(_("Maximum score: %(score)d", score=snapshot.max_score)),
        )
        document = open_document(title, language, snapshot.published_at)
        draw_header(document, title, snapshot.subject_name, meta)

        if not snapshot.regions:
            document.ln(REGION_GAP)
            document.set_font(FAMILY, "", LINE_SIZE)
            document.multi_cell(
                0, LINE_LEADING, str(_("No teams took part in this competition.")), align="L"
            )
        headings = (str(_("Educational institution")), str(_("Team")), str(_("Score")))
        widths = _column_widths(document, snapshot, headings[2])
        for region in snapshot.regions:
            # Never leave a region heading alone at the foot of a page: keep it with the table's
            # heading row and its first team.
            if document.will_page_break(REGION_GAP + REGION_LEADING + 3 * (LINE_LEADING + 4)):
                document.add_page()
            else:
                document.ln(REGION_GAP)
            document.set_font(FAMILY, "B", REGION_SIZE)
            document.multi_cell(
                0, REGION_LEADING, region.name, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
            )
            document.ln(1.5)
            _region_table(document, region, headings, widths)
        return bytes(document.output())


def _column_widths(
    document: FPDF, snapshot: "ResultsSnapshot", score_heading: str
) -> tuple[float, float, float]:
    """The columns' widths in mm: the score column just wide enough for its heading or the widest
    score, whichever is wider; the rest shared between the institution and the team."""
    scores = [str(line.score) for region in snapshot.regions for line in region.lines]
    document.set_font(FAMILY, "B", LINE_SIZE)
    widest = document.get_string_width(score_heading)
    document.set_font(FAMILY, "", LINE_SIZE)
    widest = max([widest, *(document.get_string_width(score) for score in scores)])
    score = widest + 2 * CELL_PADDING + 1
    rest = document.epw - score
    return (rest * INSTITUTION_SHARE, rest * (1 - INSTITUTION_SHARE), score)


def _region_table(
    document: FPDF,
    region: "RegionResults",
    headings: tuple[str, str, str],
    widths: tuple[float, float, float],
) -> None:
    """One region's teams: a heading row (repeated at the top of a page the table continues on),
    then one row per team; long names wrap within their cell."""
    document.set_font(FAMILY, "", LINE_SIZE)
    document.set_draw_color(*RULE)
    document.set_line_width(0.2)
    with document.table(
        width=document.epw,
        col_widths=widths,
        align="LEFT",
        text_align=("LEFT", "LEFT", "RIGHT"),
        v_align="TOP",
        borders_layout=TableBordersLayout.HORIZONTAL_LINES,
        headings_style=FontFace(emphasis="BOLD", fill_color=HEADING_FILL),
        line_height=LINE_LEADING,
        padding=CELL_PADDING,
        repeat_headings=1,
    ) as table:
        heading = table.row()
        for text in headings:
            heading.cell(text)
        for line in region.lines:
            row = table.row()
            row.cell(line.institution)
            row.cell(line.team)
            row.cell(str(line.score))
