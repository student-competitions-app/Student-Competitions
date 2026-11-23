"""The results file and its name: what the renderer puts in a file, in each language, and the
download's file name (milestone 12.8).

See specs/012.8-publishing-results/contracts/results-file.md, contracts/services.md §1–§2 and
research R2, R8, R9. The files are read back with pypdf (`tests.pdf`), as a teacher would read
them; no database is needed, since the renderer takes a snapshot.
"""

from datetime import UTC, datetime

import pytest
from fontTools.ttLib import TTFont

from app.core.i18n import Language
from app.services.file_names import ascii_file_name
from app.services.results import RegionResults, ResultLine, ResultsSnapshot, results_file_name
from app.services.results_pdf import FONT_BOLD, FONT_REGULAR, render_results_pdf
from tests.pdf import (
    pdf_fonts_embedded,
    pdf_images,
    pdf_metadata,
    pdf_page_texts,
    pdf_pages,
    pdf_text,
)

STARTED = datetime(2027, 3, 14, 8, 0, tzinfo=UTC)
"""10:00 in Kyiv."""
FINISHED = datetime(2027, 3, 14, 10, 30, tzinfo=UTC)
PUBLISHED = datetime(2027, 3, 21, 9, 0, tzinfo=UTC)

UKRAINIAN_UPPER = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
COVERED = (
    UKRAINIAN_UPPER
    + UKRAINIAN_UPPER.lower()
    + "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    + "'’ʼ“”«»–№,.:()"
)


def snapshot(*regions: RegionResults, name: str = "Spring round") -> ResultsSnapshot:
    return ResultsSnapshot(
        competition_name=name,
        subject_name="Chemistry",
        starts_at=STARTED,
        finished_at=FINISHED,
        published_at=PUBLISHED,
        max_score=40,
        regions=regions,
    )


TWO_REGIONS = snapshot(
    RegionResults(
        "Kyiv",
        (
            ResultLine("School No. 5", "Comets", 17),
            ResultLine("School No. 5", "Rockets", 0),
        ),
    ),
    RegionResults("Львівська", (ResultLine("Ліцей №2 імені Ґете", "Зорі ʼЄдність", 22),)),
)


# ---------------------------------------------------------------------------------------------
# The fonts (research R2)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("font", [FONT_REGULAR, FONT_BOLD], ids=["regular", "bold"])
def test_the_fonts_cover_ukrainian_english_and_the_punctuation(font: object) -> None:
    cmap = TTFont(font).getBestCmap()
    assert [c for c in COVERED if ord(c) not in cmap] == []


# ---------------------------------------------------------------------------------------------
# The file (contracts/results-file.md)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("language", list(Language))
def test_a_file_is_a_self_contained_pdf(language: Language) -> None:
    content = render_results_pdf(TWO_REGIONS, language)
    assert content.startswith(b"%PDF-")
    assert pdf_fonts_embedded(content)
    assert pdf_images(content, 0) == 1
    metadata = pdf_metadata(content)
    assert metadata["/Lang"] == {Language.UK: "uk-UA", Language.EN: "en-GB"}[language]
    assert metadata["/Producer"] == "Student Competitions"
    assert metadata["/CreationDate"].startswith("D:20270321090000")
    assert "/Author" not in metadata
    assert "Spring round" in metadata["/Title"]


def test_the_same_snapshot_gives_the_same_bytes() -> None:
    """Nothing reads the wall clock, so a file can be made again identically (the samples)."""
    for language in Language:
        assert render_results_pdf(TWO_REGIONS, language) == render_results_pdf(
            TWO_REGIONS, language
        )


def test_a_very_long_name_wraps() -> None:
    long = "Науково-технічний ліцей " * 9
    content = render_results_pdf(
        snapshot(RegionResults("Kyiv", (ResultLine(long.strip(), "Comets", 3),)), name=long),
        Language.EN,
    )
    text = pdf_text(content).replace("\n", " ")
    assert "Comets 3" in text
    assert text.count("Науково-технічний") >= 18


def test_the_english_file() -> None:
    """The header, then the regions in the snapshot's order, each with its lines."""
    text = pdf_text(render_results_pdf(TWO_REGIONS, Language.EN))
    expected = [
        "Results of “Spring round”",
        "Chemistry",
        "Started: 14 March 2027, 10:00 (Kyiv time)",
        "Finished: 14 March 2027, 12:30 (Kyiv time)",
        "Published: 21 March 2027",
        "Maximum score: 40",
        "Kyiv",
        "Educational institution Team Score",
        "School No. 5 Comets 17",
        "School No. 5 Rockets 0",
        "Львівська",
        "Ліцей №2 імені Ґете Зорі ʼЄдність 22",
        "Page 1 of 1",
    ]
    lines = [line.strip() for line in text.splitlines()]
    positions = [lines.index(part) for part in expected]
    assert positions == sorted(positions)


def test_the_ukrainian_file() -> None:
    """Every label in Ukrainian; the names exactly as entered, never translated."""
    text = pdf_text(render_results_pdf(TWO_REGIONS, Language.UK))
    for part in (
        "Результати «Spring round»",
        "Chemistry",
        "14 березня 2027, 10:00 (за київським часом)",
        "21 березня 2027",
        "Максимальний бал: 40",
        "Заклад освіти Команда Бал",
        "School No. 5 Comets 17",
        "Ліцей №2 імені Ґете Зорі ʼЄдність 22",
        "Сторінка 1 з 1",
    ):
        assert part in text
    for english in ("Results of", "Started", "Kyiv time", "Page 1", "Maximum score", "Team"):
        assert english not in text


@pytest.mark.parametrize("language", list(Language))
def test_no_teams(language: Language) -> None:
    text = pdf_text(render_results_pdf(snapshot(), language))
    no_teams = {
        Language.EN: "No teams took part in this competition.",
        Language.UK: "У цьому змаганні не брала участі жодна команда.",
    }[language]
    assert no_teams in text


def test_a_long_list_runs_over_numbered_pages() -> None:
    """FR-028: every page numbered with the right total; a region heading never ends a page; a
    table continued on a new page repeats its heading row."""
    lines = tuple(ResultLine(f"School No. {n}", f"Team {n:03d}", n % 11) for n in range(40))
    regions = tuple(RegionResults(f"Region {r}", lines) for r in range(3))
    content = render_results_pdf(snapshot(*regions), Language.EN)
    pages = pdf_pages(content)
    assert pages >= 3
    texts = pdf_page_texts(content)
    for number, page in enumerate(texts, start=1):
        assert f"Page {number} of {pages}" in page
        body = [line for line in page.splitlines() if line and not line.startswith("Page ")]
        assert not body[-1].startswith("Region "), f"page {number} ends with a heading"
        assert body[-1] != "Educational institution Team Score", f"page {number} ends with headings"
        if number > 1:
            rows = [line for line in body if line.startswith("School No. ")]
            if rows:
                first_row = body.index(rows[0])
                assert "Educational institution Team Score" in body[:first_row], number
    for r in range(3):
        assert sum(f"Region {r}" in page for page in texts) >= 1
    joined = "\n".join(texts)
    for n in range(40):
        assert joined.count(f"Team {n:03d} {n % 11}") == 3


# ---------------------------------------------------------------------------------------------
# The file name (research R9)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "starts_at", "expected"),
    [
        ("Spring round", STARTED, "Spring round 2027-03-14.pdf"),
        ("Spring round", datetime(2027, 3, 13, 23, 30, tzinfo=UTC), "Spring round 2027-03-14.pdf"),
        ("A/B: final?", STARTED, "A_B_ final_ 2027-03-14.pdf"),
        ('Back\\slash "quoted" <x>|*', STARTED, "Back_slash _quoted_ _x___ 2027-03-14.pdf"),
        ("  name.. ", STARTED, "name 2027-03-14.pdf"),
        ("...", STARTED, "results 2027-03-14.pdf"),
        ("Tab\there\x00", STARTED, "Tab_here_ 2027-03-14.pdf"),
        ("Весняний тур", STARTED, "Весняний тур 2027-03-14.pdf"),
    ],
)
def test_the_file_name(name: str, starts_at: datetime, expected: str) -> None:
    assert results_file_name(name, starts_at) == expected


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("Spring round 2027-03-14.pdf", "Spring round 2027-03-14.pdf"),
        ("Весняний тур 2027-03-14.pdf", "_ _ 2027-03-14.pdf"),
        ("Café (final) 2027-03-14.pdf", "Cafe (final) 2027-03-14.pdf"),
        ("A_B_ final_ 2027-03-14.pdf", "A_B_ final_ 2027-03-14.pdf"),
    ],
)
def test_the_ascii_fallback(file_name: str, expected: str) -> None:
    assert ascii_file_name(file_name) == expected


def test_the_score_column_is_just_wide_enough() -> None:
    """Design review round 1: the score column fits its heading or the widest score, and the
    institution and team columns share the rest of the width."""
    from fpdf import FPDF

    from app.services.results_pdf import (
        CELL_PADDING,
        FAMILY,
        LINE_SIZE,
        _column_widths,
    )

    document = FPDF(unit="mm", format="A4")
    document.set_margins(20, 20, 20)
    document.add_font(FAMILY, "", FONT_REGULAR)
    document.add_font(FAMILY, "B", FONT_BOLD)
    institution, team, score = _column_widths(document, TWO_REGIONS, "Score")
    document.set_font(FAMILY, "B", LINE_SIZE)
    assert score == pytest.approx(document.get_string_width("Score") + 2 * CELL_PADDING + 1)
    assert score < 20
    assert institution + team + score == pytest.approx(document.epw)
    assert institution > team > score
