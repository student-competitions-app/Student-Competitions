"""The question bank CSV file (milestone 12.11): its format, the writer, the reader and every check.

See specs/012.11-question-bank-csv/contracts/csv-format.md and research R2–R4. This module is pure:
no I/O, no database, no logging. The README section "Question bank CSV files" describes the same
format for people and AI assistants, and `tests/unit/test_question_csv.py` imports its example and
compares its limits with the constants below, so the two cannot drift apart.

- **The shape**: a header row `question,answer,additional`, never translated, then one row per
  question. The order of the rows is the order of the bank, oldest first. A file holds no bank
  number and nothing about competitions (`QuestionRow` has no field for either, FR-021).
- **The export** is UTF-8 with a byte-order mark, separated by commas, `\\r\\n` between rows, and
  quoted where needed (RFC 4180), so a spreadsheet keeps the Cyrillic text and the line breaks
  inside a cell. A text is written exactly as stored, even one that starts with `=`, `+`, `-` or
  `@` (FR-020).
- **The import** accepts what a spreadsheet saves back: with or without the byte-order mark,
  commas or semicolons (the separator is read from the header row), `\\r\\n`, `\\n` or `\\r`,
  empty rows. The whole file is checked before anything changes; every error found is returned,
  the whole-file error first, then the row errors in row order and, within a row, in column order.
  `question` and `answer` are cleaned by the add form's own rules and messages
  (`app.schemas.question.clean_question_field`).
"""

import csv
import io
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from app.core.i18n import Text, _
from app.schemas.question import InvalidQuestionField, clean_question_field

HEADER = ("question", "answer", "additional")
"""The header row, in this order, in every language."""

MAX_FILE_BYTES = 2 * 1024 * 1024
"""2 MB, counted on the file as sent."""

MAX_QUESTIONS = 1000
"""The most questions a file may hold; empty rows are not counted."""

ERRORS_SHOWN = 20
"""The most errors listed, in all; a line after the list says how many more there are."""

_BOM = b"\xef\xbb\xbf"


@dataclass(frozen=True)
class QuestionRow:
    """One question of a file. No field for a bank number or a competition, so neither can reach a
    file (FR-021). Read from a file, its text and answer are already cleaned by the add form's
    rules: 1–2,000 characters, `\\n` line endings, no null character."""

    text: str
    reference_answer: str
    is_additional: bool


@dataclass(frozen=True)
class QuestionFileError:
    """One error of a file. `row is None`: an error of the whole file (no file, too large, not
    UTF-8, the header, no question, too many), shown on the file field. Otherwise a row error,
    already worded "Row N: …", shown in the summary without a link."""

    row: int | None
    message: Text


@dataclass(frozen=True)
class QuestionFileCheck:
    """What a check found: the rows of a valid file, or the errors of a refused one, never both."""

    rows: tuple[QuestionRow, ...]
    errors: tuple[QuestionFileError, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def file_error(self) -> Text | None:
        """The error of the whole file, if any: at most one per check, always the first."""
        return next((error.message for error in self.errors if error.row is None), None)

    @property
    def row_errors(self) -> tuple[Text, ...]:
        """The row errors among the first `ERRORS_SHOWN` errors in all."""
        return tuple(error.message for error in self.errors[:ERRORS_SHOWN] if error.row is not None)

    @property
    def more(self) -> int:
        """How many errors were left out of the list."""
        return max(0, len(self.errors) - ERRORS_SHOWN)


class UnclosedQuote(ValueError):
    """A quoted field that is never closed: the rest of the file cannot be split into rows."""

    def __init__(self, row: int) -> None:
        super().__init__(f"A quote opened in row {row} is never closed")
        self.row = row


# ---------------------------------------------------------------------------------------------
# Writing (research R4)
# ---------------------------------------------------------------------------------------------


def write_question_csv(rows: Iterable[QuestionRow]) -> bytes:
    """The export: the byte-order mark, the header and one row per question, in the given order.

    The `csv` module's writer is RFC 4180 for writing: it quotes a field holding the separator, a
    quote or a line break, and doubles the quotes inside. Nothing else is changed: line breaks stay
    `\\n` inside the quoted field, and no text gets a formula prefix (FR-020)."""
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(HEADER)
    for row in rows:
        writer.writerow((row.text, row.reference_answer, "1" if row.is_additional else "0"))
    return buffer.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------------------------
# Reading (research R2)
# ---------------------------------------------------------------------------------------------

_UNQUOTED: dict[str, re.Pattern[str]] = {
    separator: re.compile(f"[^{separator}\r\n]*") for separator in (",", ";")
}
"""The rest of a field up to the separator or a line break."""


def parse_records(text: str, separator: str) -> Iterator[tuple[int, list[str]]]:
    """Every record of `text` with its row number as a spreadsheet shows it: row 1 is the first
    record, a quoted field with line breaks keeps its record one row, and a blank line is a record
    of one empty field. A line break at the very end starts no record. Raises `UnclosedQuote` with
    the row where a quoted field opens and never closes.

    A small parser of our own rather than the `csv` module, which cannot do both things a
    spreadsheet's file needs (research R2, checked on the module):

    | Case                   | `strict=False`        | `strict=True`        | Needed    |
    |------------------------|-----------------------|----------------------|-----------|
    | Unclosed quote         | rest of file, 1 field | error at end, no row | its row   |
    | `"abc"def`             | `abcdef`              | error                | `abcdef`  |
    | `The "Iliad"` unquoted | kept                  | kept                 | kept      |

    So: a field that starts with `"` is quoted; inside it `""` is a quote and the separator and
    line breaks are characters; characters after its closing quote, up to the separator, are kept
    after its text, as spreadsheets read them. A `"` anywhere else is a character, and spaces
    before an opening quote make the field unquoted. A record ends at `\\r\\n`, `\\n` or `\\r`.
    The scanning uses `str.find` and a regular expression, not a step per character."""
    unquoted = _UNQUOTED[separator]
    end = len(text)
    position = 0
    row = 0
    while position < end:
        row += 1
        fields: list[str] = []
        while True:
            if position < end and text[position] == '"':
                parts: list[str] = []
                position += 1
                while True:
                    close = text.find('"', position)
                    if close == -1:
                        raise UnclosedQuote(row)
                    parts.append(text[position:close])
                    if text.startswith('"', close + 1):
                        parts.append('"')
                        position = close + 2
                    else:
                        position = close + 1
                        break
                tail = unquoted.match(text, position)
                assert tail is not None
                parts.append(tail.group())
                position = tail.end()
                fields.append("".join(parts))
            else:
                match = unquoted.match(text, position)
                assert match is not None
                fields.append(match.group())
                position = match.end()
            if position >= end:
                break
            character = text[position]
            if character == separator:
                position += 1
                continue
            position += 2 if text.startswith("\r\n", position) else 1
            break
        yield row, fields


# ---------------------------------------------------------------------------------------------
# Checking (research R3, contracts/csv-format.md §3)
# ---------------------------------------------------------------------------------------------


def _refused(message: Text) -> QuestionFileCheck:
    return QuestionFileCheck(rows=(), errors=(QuestionFileError(None, message),))


def _header_error() -> QuestionFileCheck:
    return _refused(_("The first row must be the header: question, answer, additional."))


def _row_error(row: int, message: Text) -> QuestionFileError:
    return QuestionFileError(row, _("Row %(row)d: %(message)s", row=row, message=message))


def check_question_file(data: bytes | None, *, too_large: bool = False) -> QuestionFileCheck:
    """Check a whole file, as sent; never raises. `data is None` means no file was chosen, and
    `too_large` that the upload was larger than `MAX_FILE_BYTES` and not kept (research R7).

    No file, too large, not UTF-8, no separator in the first line, a missing or wrong header: the
    check stops with that one error. Otherwise every row is checked, and an unclosed quote stops the
    reading where it opens. The count of the non-empty rows (none, or more than `MAX_QUESTIONS`) is
    a whole-file error put before the row errors; it is not judged when the reading stopped early.
    """
    if data is None and not too_large:
        return _refused(_("Choose a CSV file."))
    if too_large or data is None or len(data) > MAX_FILE_BYTES:
        return _refused(_("The file can be at most 2 MB."))
    try:
        text = data.removeprefix(_BOM).decode("utf-8")
    except UnicodeDecodeError:
        return _refused(_("Save the file as CSV UTF-8."))
    first_line = re.split(r"[\r\n]", text, maxsplit=1)[0]
    if "," in first_line:
        separator = ","
    elif ";" in first_line:
        separator = ";"
    else:
        return _header_error()
    records = parse_records(text, separator)
    try:
        header = next(records)[1]
    except (StopIteration, UnclosedQuote):
        return _header_error()
    if tuple(name.strip().casefold() for name in header) != HEADER:
        return _header_error()

    rows: list[QuestionRow] = []
    row_errors: list[QuestionFileError] = []
    count = 0
    stopped = False
    try:
        for row, fields in records:
            if all(not value.strip() for value in fields):
                continue
            count += 1
            if len(fields) != len(HEADER):
                row_errors.append(_row_error(row, _("The row must have 3 fields.")))
                continue
            raw_text, raw_answer, raw_additional = fields
            cleaned: list[str] = []
            for raw, field in ((raw_text, "text"), (raw_answer, "reference_answer")):
                try:
                    cleaned.append(clean_question_field(raw, field))  # type: ignore[arg-type]
                except InvalidQuestionField as refused:
                    row_errors.append(_row_error(row, refused.message))
            additional = raw_additional.strip()
            if additional not in ("", "0", "1"):
                row_errors.append(_row_error(row, _("Additional must be 0, 1 or empty.")))
            elif len(cleaned) == 2:
                rows.append(QuestionRow(cleaned[0], cleaned[1], additional == "1"))
    except UnclosedQuote as unclosed:
        stopped = True
        row_errors.append(
            QuestionFileError(
                unclosed.row,
                _("A quote opened in row %(row)d is never closed.", row=unclosed.row),
            )
        )

    file_errors: list[QuestionFileError] = []
    if not stopped and count == 0:
        file_errors.append(QuestionFileError(None, _("The file holds no questions.")))
    elif not stopped and count > MAX_QUESTIONS:
        file_errors.append(QuestionFileError(None, _("The file can hold at most 1,000 questions.")))
    errors = tuple(file_errors + row_errors)
    return QuestionFileCheck(rows=() if errors else tuple(rows), errors=errors)
