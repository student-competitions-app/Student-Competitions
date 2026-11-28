# Contract: The Question Bank CSV Format (Milestone 12.11)

This is the developer-facing contract. The README section "Question bank CSV files" states the
same rules for people and AI assistants (spec FR-056), and a test keeps the two in agreement
(research R12).

## 1. Shape

```text
question,answer,additional
<text>,<reference answer>,<0|1>
...
```

- **The header row** is `question`, `answer`, `additional`, in this order. It is never translated.
- **One row per question.** Its order in the file is its order in the bank: the first row is the
  oldest question.
- **The file holds nothing else**: no bank number and nothing about competitions.

## 2. Export (written)

| Aspect | Value |
|---|---|
| Encoding | UTF-8, with a byte-order mark (`EF BB BF`) |
| Separator | `,` |
| Line ending between rows | `\r\n` |
| Quoting | RFC 4180 minimal: a field holding `,`, `"`, `\r` or `\n` is quoted; `"` doubled inside |
| Line breaks inside a field | kept as stored (`\n`), inside the quoted field |
| `additional` | `1` or `0` |
| Formula-like text (`=`, `+`, `-`, `@` first) | written as stored, no prefix |
| Empty bank | the header row and its `\r\n` only |
| Order | `id` ascending; deleted questions left out; additional included |

## 3. Import (read): checks in order

| # | Check | Error | Row | Stops |
|---|---|---|---|---|
| 1 | a file was chosen | "Choose a CSV file." | — | yes |
| 2 | at most 2 MB (2,097,152 bytes) | "The file can be at most 2 MB." | — | yes |
| 3 | UTF-8, one leading BOM dropped | "Save the file as CSV UTF-8." | — | yes |
| 4 | separator from the first line: `,` if present, else `;` if present | (header error) | — | yes |
| 5 | the first record is `question`, `answer`, `additional` (stripped, case-folded, exactly 3) | "The first row must be the header: question, answer, additional." | — | yes |
| 6a | a row with every field empty or spaces | skipped, counted | | |
| 6b | exactly 3 fields | "Row N: The row must have 3 fields." | N | no |
| 6c | `question` by the add form's rules | "Row N: Enter the question text." / "… can be at most 2,000 characters." / "… cannot contain a null character." | N | no |
| 6d | `answer` by the add form's rules | "Row N: Enter the reference answer." / … | N | no |
| 6e | `additional` stripped is `""`, `0` or `1` | "Row N: Additional must be 0, 1 or empty." | N | no |
| 7 | every quote that opens a quoted field closes | "A quote opened in row N is never closed." | N | yes |
| 8 | 1 to 1,000 non-empty rows | "The file holds no questions." / "The file can hold at most 1,000 questions." | — | no |

- **Row numbers**: the header is row 1, and every record is one row, so a quoted field with line
  breaks does not add rows. Skipped empty rows are counted, and a final line break adds no row.
- **Order of the errors**: the whole-file error first, then the row errors in row order and,
  within a row, in column order. A row that fails 6b gives that error only.
- **Shown**: at most 20 errors in all, then "And N more error(s).".
- **Reading rules**:
  - accepted line endings are `\r\n`, `\n` and `\r`;
  - a `"` that is not at the start of a field is a character;
  - characters after a closing quote, before the separator, are kept;
  - spaces around `additional` are ignored;
  - `question` and `answer` are cleaned by `clean_question_field`: line endings become `\n`, NUL
    is refused, and the value is trimmed and must be 1 to 2,000 code points;
  - two equal rows are both kept.

## 4. Examples (each is a test case)

| Input (after the header) | Result |
|---|---|
| `"a\r\nb",x,1` | one question, text `a\nb`, additional |
| `;;` with `;` separator | skipped, counted |
| `The "Iliad",Homer,` | text `The "Iliad"`, not additional |
| `"abc"def,y,0` | text `abcdef` |
| `=SUM(A1),y,0` | text `=SUM(A1)` |
| `x,y, 1 ` | additional |
| `x,y,yes` | Row 2: Additional must be 0, 1 or empty. |
| `,,0` | Row 2: Enter the question text. / Row 2: Enter the reference answer. |
| `x,y` | Row 2: The row must have 3 fields. |
| `ok,1,0` then `"open,x,1` | A quote opened in row 3 is never closed. |
