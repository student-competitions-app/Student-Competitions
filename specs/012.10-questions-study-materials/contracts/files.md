# The Two PDF Files: Milestone 12.10

Both files follow the results file of milestone 12.8 through the shared `pdf_layout` module:

- A4 portrait, 20 mm margins;
- Open Sans Regular and Bold embedded as subsets;
- the dark logo at the top left, 18 mm high;
- the title in bold, then the subject, then the muted meta line;
- a running title on every page after the first;
- "Page n of N" at the foot of every page.

Every label is in the file's language (the current site language). Texts, answers and names are
drawn as entered, line breaks kept, never translated and never read as markdown. The values below
are the starting point of the design rounds (FR-046); the content and its order are fixed by the
spec.

## 1. The questions file

**Header**, and nothing else (FR-013):

| Line | English | Ukrainian |
|---|---|---|
| Title | Questions of “<name>” | Питання змагань «<name>» |
| Subject | <subject> | <subject> |
| Meta | Started: 21 November 2026, 10:00 (Kyiv time) | Початок: 21 листопада 2026, 10:00 (за київським часом) |

The meta line reuses the 12.8 message `Started: %(moment)s` and the 12.5 Kyiv-time format.

**Body**:

- **No questions**: the line "This competition has no questions." («У цьому змаганні немає
  питань.»).
- **Otherwise**: one entry per question of the competition, in its order. Each entry has its
  number ("1.", "2.", …) in a fixed column and its text beside it, wrapped lines aligned under the
  text.
- **Never in it**: a reference answer, a bank number ("Question 58") or an **Additional** mark.

**Running title**: "Questions of “<name>”".

**PDF metadata**:

- `/Title`: the title;
- `/Lang`: `uk-UA` or `en-GB`;
- `/CreationDate`: the competition's start;
- `/Producer`: "Student Competitions".

**File name**: `<name> <YYYY-MM-DD> questions.pdf` / `<name> <YYYY-MM-DD> питання.pdf`.

## 2. The study materials

**Header**, and nothing else (FR-026):

| Line | English | Ukrainian |
|---|---|---|
| Title | Study materials | Навчальні матеріали |
| Subject | <subject> | <subject> |
| Meta | Downloaded: 23 November 2026 | Завантажено: 23 листопада 2026 |

The date is the Kyiv date of the download, in the 12.5 date format (`format_local_date`).

**Body**:

- **No questions**: the line "This subject has no questions yet." («З цього предмета ще немає
  питань.»).
- **Otherwise**: one entry per question of the subject that is neither additional nor deleted,
  oldest first. Each entry has its number in the fixed column, its text beside it, and below the
  text, at the same indent, "**Answer:** <reference answer>" (the label bold, «**Відповідь:**»).
- **Never in it**: a bank number, an **Additional** mark, or anything of an additional or deleted
  question.

**Running title**: "Study materials: <subject>" («Навчальні матеріали: <subject>»).

**PDF metadata**: as §1, with `/CreationDate` at Kyiv midnight of the download date.

**File name**: `<subject> <YYYY-MM-DD> study materials.pdf` / `<subject> <YYYY-MM-DD> навчальні
матеріали.pdf`.

## 3. Shared rules

- **Keeping entries whole** (FR-040): an entry (the question, and in the study materials its
  answer with it) starts on a new page when it would not fit on the rest of the current page but
  fits on an empty one. An entry taller than a page is split by the automatic page break.
- **Page numbers**: "Page n of N" / «Сторінка n з N», the 12.8 message.
- **Determinism**: the same input and language always give the same bytes (no clock, no random
  ids beyond fpdf2's deterministic output).
- **Reading back**: every word of every text and answer can be extracted (pypdf), Cyrillic
  included. The tests rely on it.

## 4. New messages

Each message is whole (milestone 12.5). The texts in **Translation** are proposals that the
design rounds can change.

| English msgid | Ukrainian (proposal) |
|---|---|
| Download questions | Завантажити питання |
| Download study materials | Завантажити навчальні матеріали |
| Questions of “%(name)s” | Питання змагань «%(name)s» (the existing message of the Questions page, shared) |
| Study materials | Навчальні матеріали |
| Study materials: %(subject)s | Навчальні матеріали: %(subject)s |
| Downloaded: %(date)s | Завантажено: %(date)s |
| Answer: | Відповідь: |
| This competition has no questions. | У цьому змаганні немає питань. |
| This subject has no questions yet. | З цього предмета ще немає питань. |
| %(name)s %(date)s questions | %(name)s %(date)s питання |
| %(subject)s %(date)s study materials | %(subject)s %(date)s навчальні матеріали |

The other texts (`Started: %(moment)s`, `Page %(page)d of %(total)s`, `Subject not found`,
`This subject does not exist or is deactivated.`) are already in the catalogues.
