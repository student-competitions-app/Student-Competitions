"""A competition's questions file and a subject's study materials, rendered from values built in
memory and read back (milestone 12.10).

See specs/012.10-questions-study-materials/contracts/files.md, spec.md US3 and US5, and research R4,
R5, R7. No database: the renderers are pure, so every case builds a `QuestionsSheet` or a
`StudyMaterials` and checks the bytes, or what a teacher would read in them (`tests/pdf.py`).
"""

import re
from datetime import UTC, date, datetime

import pytest

from app.core.i18n import Language
from app.services.question_files import (
    QuestionsSheet,
    StudyMaterials,
    questions_file_name,
    study_materials_file_name,
)
from app.services.question_files_pdf import render_questions_pdf, render_study_materials_pdf
from tests.pdf import pdf_fonts_embedded, pdf_metadata, pdf_page_texts, pdf_pages, pdf_text

STARTED = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)
"""10:00 in Kyiv."""
TODAY = date(2026, 11, 23)
CYRILLIC = "Чому ґрунт, їжак і є’вропейська ʼмова: «тест» №5?"

SIX = (
    "What is a covalent bond?",
    "Name the noble gases.",
    "Why is the sky blue?",
    "What is entropy?",
    "Define a mole.",
    "What is pH?",
)


def flat(text: str) -> str:
    """The text with every run of white space made one space, so wrapped lines compare equal."""
    return re.sub(r"\s+", " ", text).strip()


def sheet(*texts: str, name: str = "Spring round", subject: str = "Chemistry") -> QuestionsSheet:
    return QuestionsSheet(
        competition_name=name, subject_name=subject, starts_at=STARTED, texts=texts
    )


def materials(*entries: tuple[str, str], subject: str = "History", on: date = TODAY):
    return StudyMaterials(subject_name=subject, downloaded_on=on, entries=entries)


def numbered_order(text: str, items: tuple[str, ...]) -> list[int]:
    """The position of "<n>. <item>" for each item, in the flattened text."""
    found = flat(text)
    return [found.index(f"{n}. {item}") for n, item in enumerate(items, start=1)]


# ---------------------------------------------------------------------------------------------
# The questions file (User Story 3)
# ---------------------------------------------------------------------------------------------


def test_the_questions_header_holds_only_the_title_the_subject_and_the_start() -> None:
    """US3-1, FR-013."""
    content = render_questions_pdf(sheet(*SIX), Language.EN)
    first = flat(pdf_page_texts(content)[0])
    assert first.startswith(
        "Questions of “Spring round” Chemistry Started: 21 November 2026, 10:00 (Kyiv time) 1. "
    )
    for absent in ("Finished", "Published", "Maximum score", "Answer", "Downloaded"):
        assert absent not in first


def test_the_questions_are_numbered_in_their_order() -> None:
    """US3-2, FR-014."""
    positions = numbered_order(pdf_text(render_questions_pdf(sheet(*SIX), Language.EN)), SIX)
    assert positions == sorted(positions)


def test_the_questions_file_holds_the_texts_only() -> None:
    """US3-3, FR-015: no bank number, no mark; the input has no field for a reference answer."""
    text = pdf_text(render_questions_pdf(sheet(*SIX), Language.UK))
    for absent in ("Question ", "Питання 5", "Additional", "Додаткове", "Відповідь", "Answer"):
        assert absent not in text


@pytest.mark.parametrize(
    ("language", "sentence"),
    [
        (Language.EN, "This competition has no questions."),
        (Language.UK, "У цьому змаганні немає питань."),
    ],
)
def test_a_competition_with_no_questions(language: Language, sentence: str) -> None:
    """US3-5, FR-017."""
    text = flat(pdf_text(render_questions_pdf(sheet(), language)))
    assert sentence in text
    assert "1." not in text


def test_the_questions_file_in_ukrainian_with_cyrillic_text() -> None:
    """US3-7, FR-038: the labels in Ukrainian, the texts and names exactly as entered."""
    content = render_questions_pdf(
        sheet(CYRILLIC, name="Весняний тур", subject="Хімія"), Language.UK
    )
    text = flat(pdf_text(content))
    assert text.startswith("Питання змагань «Весняний тур» Хімія Початок: 21 листопада 2026")
    assert f"1. {CYRILLIC}" in text
    assert pdf_fonts_embedded(content)
    assert pdf_metadata(content)["/Lang"] == "uk-UA"
    assert pdf_metadata(content)["/Title"] == "Питання змагань «Весняний тур»"


def test_line_breaks_and_asterisks_are_kept() -> None:
    """FR-038, research R4: a text is never read as markdown; its line breaks stay."""
    text = pdf_text(render_questions_pdf(sheet("First line\nSecond line", "**bold**"), Language.EN))
    assert "First line\nSecond line" in text
    assert "**bold**" in text


def test_a_long_list_continues_with_a_running_title_and_page_numbers() -> None:
    """FR-039: every page after the first carries the running title; every page its number."""
    texts = tuple(f"Question text {n} " + "word " * 60 for n in range(40))
    pages = pdf_page_texts(render_questions_pdf(sheet(*texts), Language.EN))
    assert len(pages) > 2
    for number, page in enumerate(pages, start=1):
        assert f"Page {number} of {len(pages)}" in page
        if number > 1:
            assert flat(page).startswith("Questions of “Spring round”")


def test_an_entry_is_not_split_unless_it_is_taller_than_a_page() -> None:
    """FR-040: every entry of a page-filling list lies on one page; one taller than a page is
    split."""
    texts = tuple(f"Entry {n:02d} " + "filler " * (40 + 7 * n) for n in range(12))
    pages = [flat(p) for p in pdf_page_texts(render_questions_pdf(sheet(*texts), Language.EN))]
    assert len(pages) > 1
    for n, text in enumerate(texts, start=1):
        holding = [p for p in pages if f"{n}. Entry {n - 1:02d}" in p]
        assert len(holding) == 1, n
        assert flat(text) in holding[0], n
    tall = "Tall " + "line\n" * 200
    tall_pages = pdf_page_texts(render_questions_pdf(sheet("Short", tall), Language.EN))
    assert len(tall_pages) >= 2
    assert sum("line" in p for p in tall_pages) >= 2


def test_the_same_sheet_gives_the_same_bytes() -> None:
    """Research R5: no clock and nothing random, so the samples and the tests can compare bytes."""
    assert render_questions_pdf(sheet(*SIX), Language.EN) == render_questions_pdf(
        sheet(*SIX), Language.EN
    )


@pytest.mark.parametrize(
    ("name", "language", "expected"),
    [
        ("Spring round", Language.EN, "Spring round 2026-11-21 questions.pdf"),
        ("Spring round", Language.UK, "Spring round 2026-11-21 питання.pdf"),
        ("Весняний тур", Language.UK, "Весняний тур 2026-11-21 питання.pdf"),
        ("A/B: why? ", Language.EN, "A_B_ why_ 2026-11-21 questions.pdf"),
    ],
)
def test_the_questions_file_name(name: str, language: Language, expected: str) -> None:
    """US3-8, FR-019, FR-041."""
    assert questions_file_name(sheet(name=name), language) == expected


# ---------------------------------------------------------------------------------------------
# The study materials (User Story 5)
# ---------------------------------------------------------------------------------------------

ENTRIES = (
    ("What is a covalent bond?", "Two atoms share a pair of electrons."),
    ("Name the noble gases.", "He, Ne, Ar, Kr, Xe, Rn."),
    ("Why is the sky blue?", "Rayleigh scattering."),
)


def test_the_study_materials_header_holds_only_the_title_the_subject_and_the_date() -> None:
    """US5-1, FR-026."""
    first = flat(pdf_page_texts(render_study_materials_pdf(materials(*ENTRIES), Language.EN))[0])
    assert first.startswith("Study materials History Downloaded: 23 November 2026 1. ")
    for absent in ("Started", "Finished", "Published", "Maximum score"):
        assert absent not in first


def test_each_question_is_followed_by_its_answer() -> None:
    """US5-2, FR-027: numbered, oldest first as given, each answer labelled under its text."""
    text = flat(pdf_text(render_study_materials_pdf(materials(*ENTRIES), Language.EN)))
    positions = [
        text.index(f"{n}. {question} Answer: {answer}")
        for n, (question, answer) in enumerate(ENTRIES, start=1)
    ]
    assert positions == sorted(positions)
    assert "Question " not in text


@pytest.mark.parametrize(
    ("language", "sentence"),
    [
        (Language.EN, "This subject has no questions yet."),
        (Language.UK, "З цього предмета ще немає питань."),
    ],
)
def test_a_subject_with_no_questions(language: Language, sentence: str) -> None:
    """US5-5, FR-030."""
    assert sentence in flat(pdf_text(render_study_materials_pdf(materials(), language)))


def test_150_questions_continue_across_pages_in_ukrainian() -> None:
    """US5-6, FR-039: several pages; the running title names the subject; every page numbered."""
    entries = tuple(
        (f"Питання {n}: " + "чому ґрунт родючий " * 8, "Відповідь: " + "гумус " * 20)
        for n in range(150)
    )
    content = render_study_materials_pdf(materials(*entries, subject="Історія"), Language.UK)
    pages = pdf_page_texts(content)
    assert len(pages) > 5
    assert flat(pages[0]).startswith("Навчальні матеріали Історія Завантажено: 23 листопада 2026")
    for number, page in enumerate(pages, start=1):
        assert f"Сторінка {number} з {len(pages)}" in page
        if number > 1:
            assert flat(page).startswith("Навчальні матеріали: Історія")
    assert "Відповідь:" in pages[0]
    assert pdf_pages(content) == len(pages)


def test_a_question_and_its_answer_stay_together() -> None:
    """FR-040: the question and its answer are kept on one page."""
    entries = tuple(
        (f"Entry {n:02d} " + "question " * (10 + 3 * n), f"Reply {n:02d} " + "answer " * 40)
        for n in range(20)
    )
    pages = [
        flat(p)
        for p in pdf_page_texts(render_study_materials_pdf(materials(*entries), Language.EN))
    ]
    assert len(pages) > 1
    for n in range(20):
        (holding,) = [p for p in pages if f"Entry {n:02d}" in p]
        assert f"Reply {n:02d}" in holding, n


def test_the_date_changes_the_bytes_and_nothing_else_does() -> None:
    """Research R5: equal input, equal bytes; another day, another file."""
    first = render_study_materials_pdf(materials(*ENTRIES), Language.EN)
    assert render_study_materials_pdf(materials(*ENTRIES), Language.EN) == first
    later = render_study_materials_pdf(materials(*ENTRIES, on=date(2026, 11, 24)), Language.EN)
    assert later != first
    assert "Downloaded: 24 November 2026" in flat(pdf_text(later))


@pytest.mark.parametrize(
    ("subject", "language", "expected"),
    [
        ("History", Language.EN, "History 2026-11-23 study materials.pdf"),
        ("Історія", Language.UK, "Історія 2026-11-23 навчальні матеріали.pdf"),
    ],
)
def test_the_study_materials_file_name(subject: str, language: Language, expected: str) -> None:
    """US5-7, FR-031."""
    assert study_materials_file_name(materials(subject=subject), language) == expected
