"""A competition's questions file and a subject's study materials: one PDF each, in one language
(milestone 12.10).

See specs/012.10-questions-study-materials/contracts/files.md and research R3, R4.

**Pure**: each function takes what the file shows (`QuestionsSheet`, `StudyMaterials`) and a
language and returns the file's bytes. No session, no request, no clock: the same input and
language always give the same bytes, which lets the study materials be kept and compared, the
tests compare bytes, and the sample script make the review samples without a database.

**What a file holds**: the header shared with the results file (`pdf_layout.draw_header`), then a
numbered list. Each entry has its number in a fixed column and its text beside it, wrapped lines
aligned under the text; in the study materials the reference answer follows below the text,
labelled. An entry, with its answer, starts on a new page rather than being split, unless it is
taller than a page (FR-040). Texts are drawn as entered, line breaks kept, never read as markdown,
never translated. Neither file can draw a bank number, a mark or (the questions file) a reference
answer: its input has no field for them.

**The look** (sizes, spacing, the answer label) is the starting point of the design review rounds
with the product owner (FR-046, `design-approval.md`).
"""

from collections.abc import Sequence
from datetime import datetime, time
from typing import TYPE_CHECKING

from fpdf.enums import MethodReturnValue, XPos, YPos

from app.core.i18n import Language, _, use_language
from app.core.time_zone import KYIV, format_local_date, format_local_time
from app.services.pdf_layout import (
    FAMILY,
    INK,
    LINE_LEADING,
    LINE_SIZE,
    REGION_GAP,
    PdfDocument,
    draw_header,
    open_document,
)

if TYPE_CHECKING:
    from app.services.question_files import QuestionsSheet, StudyMaterials

NUMBER_GAP = 2.5
"""mm between the widest number and the text."""
ENTRY_GAP = 4.0
"""mm between two entries."""
ANSWER_GAP = 1.5
"""mm between a question's text and its answer."""


def render_questions_pdf(sheet: "QuestionsSheet", language: Language) -> bytes:
    """The questions file of `sheet` with every label in `language`: the header (title, subject,
    start in Kyiv time), then every question's text, numbered from 1."""
    with use_language(language):
        title = str(_("Questions of “%(name)s”", name=sheet.competition_name))
        document = open_document(title, language, sheet.starts_at)
        started = format_local_time(sheet.starts_at, None)
        draw_header(
            document, title, sheet.subject_name, [str(_("Started: %(moment)s", moment=started))]
        )
        document.ln(REGION_GAP)
        if not sheet.texts:
            _sentence(document, str(_("This competition has no questions.")))
        else:
            _numbered_entries(document, [(text, None) for text in sheet.texts], "")
        return bytes(document.output())


def render_study_materials_pdf(materials: "StudyMaterials", language: Language) -> bytes:
    """The study materials of `materials` with every label in `language`: the header (title,
    subject, date of the download), then every question with its reference answer, numbered
    from 1."""
    with use_language(language):
        title = str(_("Study materials"))
        running = str(_("Study materials: %(subject)s", subject=materials.subject_name))
        created_at = datetime.combine(materials.downloaded_on, time(), KYIV)
        document = open_document(title, language, created_at, running_title=running)
        downloaded = format_local_date(created_at, None)
        draw_header(
            document,
            title,
            materials.subject_name,
            [str(_("Downloaded: %(date)s", date=downloaded))],
        )
        document.ln(REGION_GAP)
        if not materials.entries:
            _sentence(document, str(_("This subject has no questions yet.")))
        else:
            _numbered_entries(document, list(materials.entries), str(_("Answer:")))
        return bytes(document.output())


def _sentence(document: PdfDocument, text: str) -> None:
    """The one line an empty file holds in place of the list."""
    document.set_font(FAMILY, "", LINE_SIZE)
    document.set_text_color(*INK)
    document.multi_cell(0, LINE_LEADING, text, align="L")


def _numbered_entries(
    document: PdfDocument, entries: Sequence[tuple[str, str | None]], answer_label: str
) -> None:
    """Each `(text, answer)` numbered from 1; `answer` is `None` in the questions file."""
    document.set_text_color(*INK)
    document.set_font(FAMILY, "B", LINE_SIZE)
    number_width = (
        max(document.get_string_width(f"{n}.") for n in range(1, len(entries) + 1)) + NUMBER_GAP
    )
    text_x = document.l_margin + number_width
    text_width = document.epw - number_width
    for number, (text, answer) in enumerate(entries, start=1):
        height = _entry_height(document, text, answer, answer_label, text_width)
        if number > 1:
            height += ENTRY_GAP
        # Keep an entry whole: it starts on a new page when it would not fit on the rest of this
        # one but fits on an empty one; an entry taller than a page is split (FR-040).
        if height <= document.eph and document.will_page_break(height):
            document.add_page()
        elif number > 1:
            document.ln(ENTRY_GAP)
        top = document.get_y()
        document.set_font(FAMILY, "B", LINE_SIZE)
        document.set_x(document.l_margin)
        document.cell(number_width, LINE_LEADING, f"{number}.")
        document.set_xy(text_x, top)
        document.set_font(FAMILY, "", LINE_SIZE)
        document.multi_cell(
            text_width, LINE_LEADING, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
        if answer is not None:
            document.ln(ANSWER_GAP)
            _answer(document, answer_label, answer, text_x)


def _answer(document: PdfDocument, label: str, answer: str, indent: float) -> None:
    """ "**Answer:** <answer>" at the text's indent: the label bold, the answer regular, wrapped
    lines aligned under the label."""
    margin = document.l_margin
    document.set_left_margin(indent)
    document.set_x(indent)
    document.set_font(FAMILY, "B", LINE_SIZE)
    document.write(LINE_LEADING, f"{label} ")
    document.set_font(FAMILY, "", LINE_SIZE)
    document.write(LINE_LEADING, answer)
    document.ln(LINE_LEADING)
    document.set_left_margin(margin)
    document.set_x(margin)


def _entry_height(
    document: PdfDocument, text: str, answer: str | None, label: str, width: float
) -> float:
    """The height an entry will take, measured without drawing. The answer is measured with its
    label in bold, which is never narrower than the regular answer, so the estimate is never too
    small and an entry that is kept whole is never split."""
    document.set_font(FAMILY, "", LINE_SIZE)
    height = document.multi_cell(
        width, LINE_LEADING, text, dry_run=True, output=MethodReturnValue.HEIGHT
    )
    if answer is not None:
        document.set_font(FAMILY, "B", LINE_SIZE)
        height += ANSWER_GAP + document.multi_cell(
            width, LINE_LEADING, f"{label} {answer}", dry_run=True, output=MethodReturnValue.HEIGHT
        )
    return float(height)
