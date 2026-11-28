"""The question bank CSV file, pure: the writer, the parser, every check and the README section.

See specs/012.11-question-bank-csv/contracts/csv-format.md and research R2–R4, R12. No database:
the whole format lives in `app.services.question_csv`. The messages are asserted verbatim, in
English, the language outside a request.
"""

import re
from pathlib import Path

import pytest

from app.schemas.question import QUESTION_FIELD_MAX_LENGTH
from app.services.question_csv import (
    ERRORS_SHOWN,
    HEADER,
    MAX_FILE_BYTES,
    MAX_QUESTIONS,
    QuestionFileCheck,
    QuestionRow,
    UnclosedQuote,
    check_question_file,
    parse_records,
    write_question_csv,
)

BOM = b"\xef\xbb\xbf"
HEADER_ERROR = "The first row must be the header: question, answer, additional."
README = Path(__file__).resolve().parents[2] / "README.md"


def errors(check: QuestionFileCheck) -> list[tuple[int | None, str]]:
    return [(error.row, str(error.message)) for error in check.errors]


def rows(check: QuestionFileCheck) -> list[tuple[str, str, bool]]:
    assert check.ok, errors(check)
    return [(row.text, row.reference_answer, row.is_additional) for row in check.rows]


def refused(data: bytes | None, **options: bool) -> list[tuple[int | None, str]]:
    check = check_question_file(data, **options)
    assert not check.ok
    assert check.rows == ()
    return errors(check)


# ---------------------------------------------------------------------------------------------
# The writer (User Story 1, FR-017–FR-021)
# ---------------------------------------------------------------------------------------------


def test_an_empty_bank_is_the_header_only() -> None:
    assert write_question_csv([]) == BOM + b"question,answer,additional\r\n"


def test_the_writer_quotes_where_needed_and_keeps_everything_else() -> None:
    out = write_question_csv(
        [
            QuestionRow("Хто написав «Кобзар»?", "Тарас Шевченко", False),
            QuestionRow('Name a, "b"\nand c', "Line one\nline two", True),
        ]
    )
    assert out.startswith(BOM)
    assert out.decode("utf-8-sig") == (
        "question,answer,additional\r\n"
        "Хто написав «Кобзар»?,Тарас Шевченко,0\r\n"
        '"Name a, ""b""\nand c","Line one\nline two",1\r\n'
    )


@pytest.mark.parametrize("text", ["=SUM(A1)", "+380", "-1", "@home"])
def test_a_formula_like_text_is_written_as_it_is(text: str) -> None:
    out = write_question_csv([QuestionRow(text, "Answer.", False)])
    assert out.decode("utf-8-sig").splitlines()[1] == f"{text},Answer.,0"


def test_the_writer_keeps_the_order() -> None:
    bank = [QuestionRow(f"Q{n}", f"A{n}", n % 2 == 0) for n in (3, 1, 2)]
    assert [line.split(",")[0] for line in write_question_csv(bank).decode().splitlines()[1:]] == [
        "Q3",
        "Q1",
        "Q2",
    ]


# ---------------------------------------------------------------------------------------------
# The parser (research R2)
# ---------------------------------------------------------------------------------------------


def test_records_and_their_rows() -> None:
    text = 'h1,h2,h3\r\n"a\r\nb",x,1\r\n\r\nc,"d\ne",0\n'
    assert list(parse_records(text, ",")) == [
        (1, ["h1", "h2", "h3"]),
        (2, ["a\r\nb", "x", "1"]),
        (3, [""]),
        (4, ["c", "d\ne", "0"]),
    ]


def test_a_final_line_break_starts_no_record_but_a_blank_line_does() -> None:
    assert list(parse_records("a,b\n", ",")) == [(1, ["a", "b"])]
    assert list(parse_records("a,b", ",")) == [(1, ["a", "b"])]
    assert list(parse_records("a,b\n\n", ",")) == [(1, ["a", "b"]), (2, [""])]
    assert list(parse_records("a,b\rc,d", ",")) == [(1, ["a", "b"]), (2, ["c", "d"])]


def test_quotes() -> None:
    assert list(parse_records('"x""y","abc"def,The "Iliad",  "z",', ",")) == [
        (1, ['x"y', "abcdef", 'The "Iliad"', '  "z"', ""])
    ]


def test_the_separator_inside_quotes_is_a_character() -> None:
    assert list(parse_records('"a;b";"c,d"', ";")) == [(1, ["a;b", "c,d"])]


def test_an_unclosed_quote_names_the_row_where_it_opens() -> None:
    records = parse_records('h\nok\n"open\nmore\nlines\n', ",")
    assert next(records) == (1, ["h"])
    assert next(records) == (2, ["ok"])
    with pytest.raises(UnclosedQuote) as raised:
        next(records)
    assert raised.value.row == 3


# ---------------------------------------------------------------------------------------------
# Reading a spreadsheet's file (User Story 4, FR-022–FR-029)
# ---------------------------------------------------------------------------------------------

THREE = [("Q1", "A1", False), ("Q2", "A2", True), ("Q3", "A3", False)]


@pytest.mark.parametrize("bom", [b"", BOM])
@pytest.mark.parametrize("newline", ["\r\n", "\n"])
@pytest.mark.parametrize("separator", [",", ";"])
def test_every_spreadsheet_variant_reads_the_same(bom: bytes, newline: str, separator: str) -> None:
    lines = [separator.join(HEADER)] + [separator.join(("Q1", "A1", "0")), "Q2;A2;1", "Q3;A3;"]
    if separator == ",":
        lines[2:] = ["Q2,A2,1", "Q3,A3,"]
    assert rows(check_question_file(bom + newline.join(lines).encode())) == THREE


def test_a_semicolon_in_a_comma_file_is_a_character() -> None:
    """The separator comes from the header row: a comma there means commas, so `;` and `;;` in
    the rows are text, not separators or an empty row."""
    data = b"question,answer,additional\na;b,;;,0\n"
    assert rows(check_question_file(data)) == [("a;b", ";;", False)]


def test_the_header_ignores_case_and_spaces() -> None:
    data = b"Question; ANSWER ;additional\nQ;A;0\n"
    assert rows(check_question_file(data)) == [("Q", "A", False)]


def test_empty_rows_are_skipped_but_counted() -> None:
    data = b"question;answer;additional\n;;\n\nQ;A;0\n  ; ;\nQ2;;\n"
    assert refused(data) == [(6, "Row 6: Enter the reference answer.")]
    data = b"question;answer;additional\n;;\n\nQ;A;0\n"
    assert rows(check_question_file(data)) == [("Q", "A", False)]


def test_a_row_with_only_additional_filled_is_not_empty() -> None:
    assert refused(b"question,answer,additional\n,,1\n") == [
        (2, "Row 2: Enter the question text."),
        (2, "Row 2: Enter the reference answer."),
    ]


@pytest.mark.parametrize(("value", "additional"), [(" 1 ", True), ("1", True), ("", False)])
def test_spaces_around_additional_and_an_empty_cell(value: str, additional: bool) -> None:
    data = f"question,answer,additional\nQ,A,{value}\n".encode()
    assert rows(check_question_file(data)) == [("Q", "A", additional)]


def test_quotes_kept_and_read_as_a_spreadsheet_does() -> None:
    data = b'question,answer,additional\nThe "Iliad",Homer,0\n"abc"def,y,0\n'
    assert rows(check_question_file(data)) == [
        ('The "Iliad"', "Homer", False),
        ("abcdef", "y", False),
    ]


def test_a_multi_line_cell_is_one_row_and_its_line_breaks_become_newlines() -> None:
    data = b'question,answer,additional\r\n"Line one\r\nline two",A,0\r\nQ,,0\r\n'
    assert refused(data) == [(3, "Row 3: Enter the reference answer.")]
    data = b'question,answer,additional\r\n"Line one\r\nline two",A,0\r\n'
    assert rows(check_question_file(data)) == [("Line one\nline two", "A", False)]


def test_the_texts_are_trimmed_as_on_the_add_form() -> None:
    data = b'question,answer,additional\n"  Q  ",\t A \t,0\n'
    assert rows(check_question_file(data)) == [("Q", "A", False)]


def test_a_round_trip_through_the_writer() -> None:
    bank = [
        QuestionRow("=SUM(A1)", "+1", True),
        QuestionRow("-1", "@home", False),
        QuestionRow('Кома, "лапки"\nі новий рядок', "Відповідь", False),
        QuestionRow("Same?", "Same.", False),
        QuestionRow("Same?", "Same.", False),
    ]
    assert check_question_file(write_question_csv(bank)).rows == tuple(bank)


# ---------------------------------------------------------------------------------------------
# Refusing a bad file (User Story 3, FR-034–FR-040)
# ---------------------------------------------------------------------------------------------


def test_no_file() -> None:
    assert refused(None) == [(None, "Choose a CSV file.")]


def test_too_large() -> None:
    assert refused(None, too_large=True) == [(None, "The file can be at most 2 MB.")]
    data = b"question,answer,additional\n" + b"x" * MAX_FILE_BYTES
    assert refused(data) == [(None, "The file can be at most 2 MB.")]


def test_exactly_the_limit_is_read() -> None:
    header = b"question,answer,additional\n"
    data = header + b"Q,A,0\n" * ((MAX_FILE_BYTES - len(header)) // 6)
    assert len(data) <= MAX_FILE_BYTES
    assert refused(data) == [(None, "The file can hold at most 1,000 questions.")]


@pytest.mark.parametrize(
    "data",
    [
        "question,answer,additional\nПитання,Відповідь,0\n".encode("utf-16"),
        "question,answer,additional\nПитання,Відповідь,0\n".encode("cp1251"),
    ],
)
def test_not_utf8(data: bytes) -> None:
    assert refused(data) == [(None, "Save the file as CSV UTF-8.")]


@pytest.mark.parametrize(
    "data",
    [
        b"",
        BOM,
        b"\n\nquestion,answer,additional\n",
        b"question answer additional\nQ A 0\n",
        b"question;answer;additional;\nQ;A;0;\n",
        b"answer,question,additional\nQ,A,0\n",
        b"question,answer\nQ,A\n",
        b'"question,answer,additional\nQ,A,0\n',
    ],
)
def test_a_missing_or_wrong_header(data: bytes) -> None:
    assert refused(data) == [(None, HEADER_ERROR)]


def test_no_question() -> None:
    assert refused(b"question,answer,additional\n") == [(None, "The file holds no questions.")]
    assert refused(b"question;answer;additional\n;;\n\n ; ;\n") == [
        (None, "The file holds no questions.")
    ]


def test_too_many_questions_comes_first_and_the_rows_are_still_checked() -> None:
    lines = ["question,answer,additional"] + ["Q,A,0"] * MAX_QUESTIONS + ["Q,,0"]
    assert refused("\n".join(lines).encode()) == [
        (None, "The file can hold at most 1,000 questions."),
        (MAX_QUESTIONS + 2, f"Row {MAX_QUESTIONS + 2}: Enter the reference answer."),
    ]


def test_exactly_a_thousand_questions_is_accepted() -> None:
    lines = ["question,answer,additional"] + [f"Q{n},A,0" for n in range(MAX_QUESTIONS)]
    assert len(check_question_file("\n".join(lines).encode()).rows) == MAX_QUESTIONS


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("x,y", "Row 2: The row must have 3 fields."),
        ("x,y,0,", "Row 2: The row must have 3 fields."),
        ("x,y,yes", "Row 2: Additional must be 0, 1 or empty."),
        ("x,y,2", "Row 2: Additional must be 0, 1 or empty."),
        (
            f"{'q' * (QUESTION_FIELD_MAX_LENGTH + 1)},y,0",
            "Row 2: The question text can be at most 2,000 characters.",
        ),
        ("x,y\x00z,0", "Row 2: The reference answer cannot contain a null character."),
    ],
)
def test_a_bad_row(row: str, message: str) -> None:
    assert refused(f"question,answer,additional\n{row}\n".encode()) == [(2, message)]


def test_exactly_two_thousand_characters_is_accepted() -> None:
    text = "q" * QUESTION_FIELD_MAX_LENGTH
    data = f"question,answer,additional\n {text} ,y,0\n".encode()
    assert rows(check_question_file(data)) == [(text, "y", False)]


def test_a_row_of_the_wrong_width_gives_that_error_only() -> None:
    assert refused(b"question,answer,additional\nx,\n") == [
        (2, "Row 2: The row must have 3 fields.")
    ]


def test_errors_in_row_order_then_column_order() -> None:
    data = b"question,answer,additional\nok,1,0\n,,x\nok,2,0\nq,,0\n"
    assert refused(data) == [
        (3, "Row 3: Enter the question text."),
        (3, "Row 3: Enter the reference answer."),
        (3, "Row 3: Additional must be 0, 1 or empty."),
        (5, "Row 5: Enter the reference answer."),
    ]


def test_row_numbers_follow_the_spreadsheet() -> None:
    data = b'question,answer,additional\n"multi\nline\ncell",A,0\n\n,,\n , ,\nq,,0\n'
    assert refused(data) == [(6, "Row 6: Enter the reference answer.")]


def test_an_unclosed_quote_stops_the_check_and_keeps_the_earlier_errors() -> None:
    data = b'question,answer,additional\nok,1,0\nq,,0\n"open,x,1\nq,,0\nmore,\n'
    assert refused(data) == [
        (3, "Row 3: Enter the reference answer."),
        (4, "A quote opened in row 4 is never closed."),
    ]


def test_an_unclosed_quote_alone_is_not_also_no_question() -> None:
    assert refused(b'question,answer,additional\n"open,x,1\n') == [
        (2, "A quote opened in row 2 is never closed.")
    ]


def test_twenty_errors_are_shown_then_how_many_more() -> None:
    lines = ["question,answer,additional"] + [f"Q{n},A,bad" for n in range(25)]
    check = check_question_file("\n".join(lines).encode())
    assert len(check.errors) == 25
    assert check.file_error is None
    assert len(check.row_errors) == ERRORS_SHOWN
    assert str(check.row_errors[0]) == "Row 2: Additional must be 0, 1 or empty."
    assert str(check.row_errors[-1]) == "Row 21: Additional must be 0, 1 or empty."
    assert check.more == 5


def test_the_limit_counts_the_file_error_too() -> None:
    lines = ["question,answer,additional"] + ["Q,A,0"] * MAX_QUESTIONS + ["Q,A,x"] * 25
    check = check_question_file("\n".join(lines).encode())
    assert str(check.file_error) == "The file can hold at most 1,000 questions."
    assert len(check.row_errors) == ERRORS_SHOWN - 1
    assert check.more == 6


def test_two_equal_rows_are_both_kept() -> None:
    data = b"question,answer,additional\nSame?,Same.,0\nSame?,Same.,0\n"
    assert rows(check_question_file(data)) == [("Same?", "Same.", False)] * 2


# ---------------------------------------------------------------------------------------------
# The README section (User Story 6, FR-056–FR-058)
# ---------------------------------------------------------------------------------------------


def readme_section() -> str:
    text = README.read_text()
    start = text.index("\n## Question bank CSV files\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else None]


def readme_example() -> bytes:
    """The section's first `csv` block, exactly as written."""
    match = re.search(r"```csv\n(.*?)```", readme_section(), re.DOTALL)
    assert match, "the README section has no ```csv block"
    return match.group(1).encode("utf-8")


@pytest.mark.parametrize("bom", [b"", BOM])
def test_the_readme_example_imports(bom: bytes) -> None:
    check = check_question_file(bom + readme_example())
    found = rows(check)
    assert 3 <= len(found) <= 6
    assert [additional for _, _, additional in found].count(True) == 1
    texts = " ".join(text + answer for text, answer, _ in found)
    assert re.search("[А-Яа-яІіЇїЄєҐґ]", texts), "the example is in Ukrainian"
    assert any("," in text or "," in answer for text, answer, _ in found)
    assert any('"' in text or '"' in answer for text, answer, _ in found)
    assert any("\n" in text or "\n" in answer for text, answer, _ in found)


def test_the_readme_states_the_limits_and_the_header() -> None:
    section = readme_section()
    assert QUESTION_FIELD_MAX_LENGTH == 2000 and "2,000 characters" in section
    assert MAX_QUESTIONS == 1000 and "1,000 questions" in section
    assert MAX_FILE_BYTES == 2 * 1024 * 1024 and "2 MB" in section
    assert ",".join(HEADER) in section
