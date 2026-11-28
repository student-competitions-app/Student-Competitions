# Feature Specification: Exporting and Importing a Subject's Questions as CSV Files (Administrator) (Milestone 12.11)

**Feature Branch**: `012.11_csv_export_import`

**Created**: 2026-11-28

**Status**: Draft

**Input**: User description: milestone 12.11 of `docs/requirements/milestones.md` ("Exporting and
importing a subject's questions as CSV files (administrator)"), as refined on 2026-11-28, with
`product-requirements.md` (the "Administrator", "Teacher responsibilities", "Teacher access rights"
and "Additional questions" sections), the constitution v2.8.0 (Principles II, III, IV and VII),
`docs/requirements/ui-guidelines.md` (the actions menu, confirmations, forms and the error summary),
and the milestone 5, 6, 7, 10, 10.1, 11, 12.1, 12.2, 12.4, 12.5, 12.8, 12.9 and 12.10 specifications
as reference.

## Overview

Milestone 12.11 of the walking skeleton for the Student Competitions application. Today a question
enters the bank only through the teacher's add form (milestone 11), one at a time, while a bank holds
a hundred questions or more per subject (milestone 12.10). Preparing a bank that way is slow, and
nothing lets anyone keep a copy of a bank outside the application.

This milestone lets an administrator export every question of a subject to a CSV file, edit it in a
spreadsheet and import it again, or have an AI assistant such as Claude Desktop write a new file from
the format described in the README and import that. The import replaces the subject's questions with
those of the file. Ten things become true when this milestone is done:

1. **The Subjects tab shows how many questions each subject has**, in a new **Questions** column, the
   additional ones included and the deleted ones left out.
2. **A subject's actions move into an actions menu**, in the order **Rename**, **Export questions**,
   **Import questions**, **Deactivate** or **Activate**, **Delete**; **Deactivate** and **Activate**
   each open a confirmation page first.
3. **An administrator exports a subject's questions** with **Export questions**, a link marked as a
   download, for an active or a deactivated subject: every question not deleted, oldest first, the
   additional ones marked.
4. **The CSV format is fixed and the same in both languages**: a header row `question`, `answer`,
   `additional`, then one row per question, UTF-8 with a byte-order mark, separated by commas.
5. **An administrator imports a CSV file** on the page **Import questions: <subject>**, a destructive
   confirmation with a file field, and the file's questions replace the subject's questions.
6. **The import accepts what a spreadsheet saves back**: commas or semicolons, with or without the
   byte-order mark, either line ending, empty rows skipped.
7. **The whole file is checked before anything changes**: a bad file is refused with every error
   found, each with the row number a spreadsheet shows, at most 20 of them, and the bank stays as it
   was.
8. **Replacing is safe for everything that uses the questions**: the old questions are soft-deleted,
   so competitions keep their copies and results, and the bank is locked for writing while an import
   runs, so a teacher's change never ends up mixed with the imported questions.
9. **The README describes the format** in a section "Question bank CSV files", written so that an AI
   assistant given only that section writes a file that imports without an error; a test imports the
   section's example file.
10. **Three new UI patterns** (a confirmation with a form, a file field, and row errors in the error
    summary) are added to the component library, the component gallery and the UI guidelines before
    the page uses them.

Only administrators have the export and the import. Teachers keep the **Questions** tab as it is,
and students get nothing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An administrator exports a subject's questions (Priority: P1)

Iryna is an administrator. On the **Subjects** tab, the row of "History" shows **124** in the
**Questions** column. Iryna opens its actions menu and chooses **Export questions**. The browser saves
"History 2026-11-28 question bank.csv" straight away; Iryna stays on the tab and the loading bar does
not appear. She opens the file in a spreadsheet: the Ukrainian texts read correctly, a question with
two lines stays in one cell, and the 124 questions are listed oldest first, with `1` in the
`additional` column for the three additional ones. In Ukrainian, the same file is named
"Історія 2026-11-28 банк питань.csv" and has the same header row.

**Why this priority**: The export is how an administrator gets a bank to edit, and how a bank is kept
before an import replaces it.

**Independent Test**: As an administrator, export the bank of an active subject, of a deactivated
subject and of a subject with no questions, in both languages, and check the link's download marking,
the file name, the bytes, the rows, their order and the marks.

**Acceptance Scenarios**:

1. **Given** an administrator on the **Subjects** tab, **When** they open the actions menu of an
   active or a deactivated subject, **Then** it offers **Export questions** as a link marked as a
   download.
2. **Given** a subject with questions, some additional and some deleted, **When** the administrator
   chooses **Export questions**, **Then** the file downloads with no page in between, the
   administrator stays on the tab, the loading bar does not start, and this works without JavaScript.
3. **Given** the downloaded file, **Then** it starts with the byte-order mark, its first row is
   `question,answer,additional`, and each further row holds one question that is not deleted, oldest
   first, with its text and reference answer exactly as stored and `1` for an additional question,
   `0` for every other.
4. **Given** a question with Cyrillic letters, a comma, a quote and a line break in its text or
   answer, **When** it is exported, **Then** the field is quoted, the quote doubled and the line
   break kept inside the field, so a spreadsheet shows it in one cell exactly as stored.
5. **Given** a question text that starts with `=`, `+`, `-` or `@`, **When** it is exported, **Then**
   it is written as it is, with no prefix added.
6. **Given** a subject with no questions, or only deleted ones, **When** it is exported, **Then** the
   file holds the header row only.
7. **Given** the site in English on 28 November 2026 in Kyiv, **When** "History" is exported,
   **Then** the file is named "History 2026-11-28 question bank.csv"; in Ukrainian, "Історія
   2026-11-28 банк питань.csv"; characters a file name cannot hold are replaced as in milestone 12.8.
8. **Given** a teacher adds a question after an export, **When** the administrator exports again,
   **Then** the new file holds it: the export reads the bank as it is and is never stored.

---

### User Story 2 - An administrator replaces a subject's questions with a file (Priority: P1)

Iryna extends the exported "History" file to 150 questions in a spreadsheet and saves it. She chooses
**Import questions** in the menu of "History". The page "Import questions: History" says that History
has 124 questions now, and warns that importing deletes all of them and replaces them with the
questions of the file, that this cannot be undone, and to export the current questions first to keep
them. Iryna chooses the file and presses **Replace questions**. She is back on the **Subjects** tab,
where "History" shows **150**. Olena, a teacher, opens the **Questions** tab for History and sees
the 150 questions in the file's order, under new numbers. The **Upcoming** "Spring round", which held
two of the old questions, still holds them, each with the "Deleted from the question bank" mark.

**Why this priority**: The import is the point of the milestone: a bank of a hundred questions or
more is prepared in a spreadsheet instead of one question at a time.

**Independent Test**: As an administrator, import a valid file into a subject with questions, some
of them in competitions, and check the subject's bank, the other subjects' banks, the deleted
questions, the competitions, the subject's deletion and the log line.

**Acceptance Scenarios**:

1. **Given** an administrator, **When** they choose **Import questions** for an active or a
   deactivated subject, **Then** the page "Import questions: <subject>" opens, says how many
   questions the subject has now, warns that importing deletes all of them and replaces them with
   the questions of the file, that this cannot be undone, and to export the current questions first
   to keep them, and holds a file field that accepts `.csv`, the destructive button **Replace
   questions** and **Cancel** back to the tab.
2. **Given** a valid file, **When** the administrator presses **Replace questions**, **Then** every
   question of the subject that was not deleted is deleted the way a teacher deletes it, every row
   of the file becomes a new question of the subject in the file's order with the additional mark
   of its row, and the administrator returns to the **Subjects** tab, where the **Questions** column
   shows the new number.
3. **Given** the import is done, **Then** the first row of the file is the subject's oldest
   question, each new question has a new bank number, and no number of a deleted question is used
   again.
4. **Given** questions of other subjects, **When** a subject is imported, **Then** they are
   unchanged.
5. **Given** an exported file, **When** it is imported back unchanged, **Then** the bank holds the
   same texts, answers, additional marks and order under new numbers.
6. **Given** a competition in any status that holds a question the import deletes, **Then** it keeps
   its copy, its answers, grades and results, and the question shows the "Deleted from the question
   bank" mark of milestone 12.2; nothing else in the competition changes. In an **Upcoming** one, a
   teacher with **Can manage competitions** may remove it and add a new one, as for any deleted
   question.
7. **Given** a subject whose questions were all replaced, **When** an administrator tries to delete
   it, **Then** it is still refused as in use, since its deleted questions are still stored; it can
   still be deactivated.
8. **Given** the import is done, **Then** one log line records the subject's id, the number of
   deleted questions and the number of added questions, and no question text.
9. **Given** the import is done, **When** a teacher next downloads the subject's study materials
   (milestone 12.10), **Then** they show the new questions, without the additional ones, as for any
   other change of the bank.
10. **Given** the administrator presses **Cancel**, **Then** they return to the **Subjects** tab and
    nothing changes.

---

### User Story 3 - A bad file is refused with every error, and nothing changes (Priority: P1)

Iryna imports a file of 150 rows. In row 7 the answer is empty, row 12 has `yes` in the `additional`
column, and row 40 has both cells empty except `additional`. The page "Import questions: History"
shows again with the error summary: "Row 7: Enter the reference answer.", "Row 12: Additional must be 0, 1 or empty.", "Row 40: Enter
the question text.", "Row 40: Enter the reference answer.". The file field is empty again, and
History still has its 124 questions. Iryna fixes the rows in her spreadsheet, chooses the file again
and imports it.

**Why this priority**: An import that half-succeeds, or an error the administrator cannot find in
the spreadsheet, would damage a bank of a hundred questions or more.

**Independent Test**: Import each kind of bad file, and a file with 25 bad rows, then check the
messages, their row numbers and order, the limit of 20, the empty file field and the unchanged bank.

**Acceptance Scenarios**:

1. **Given** any file that fails a check, **When** it is imported, **Then** the page shows again with
   every error found in the error summary, and the subject's questions, and every other question,
   stay exactly as they were.
2. **Given** a row error, **Then** it names its row as a spreadsheet shows it: the header is row 1,
   a field with line breaks inside keeps its record one row, and skipped empty rows are counted.
3. **Given** a row with an empty text and an empty answer, **Then** it gives two errors, in column
   order: the text's, then the answer's.
4. **Given** errors in several rows, **Then** they are listed in row order, and within a row in
   column order.
5. **Given** a file with 25 bad rows of one error each, **Then** the summary lists the first 20
   errors, then the line "And 5 more errors.".
6. **Given** each of these files, **When** it is imported, **Then** it is refused with its own
   message and nothing changes: no file chosen; larger than 2 MB; not UTF-8 ("Save the file as CSV
   UTF-8"); no header row or a wrong one; no question; more than 1,000 questions.
7. **Given** each of these rows, **When** the file is imported, **Then** the row is refused with its
   row number: a different number of fields than the header; `additional` anything but `0`, `1` or
   empty; a question text or reference answer that is empty after trimming, longer than 2,000
   characters or holding a null character, with the add form's message.
8. **Given** a quote that is opened in row 9 and never closed, **When** the file is imported,
   **Then** it is refused with "A quote opened in row 9 is never closed." and the check stops there.
9. **Given** an error of the whole file, **Then** it has no row number.
10. **Given** the page shows errors, **Then** the file field is empty, and the administrator chooses
    the file again.
11. **Given** two rows with the same text, **Then** both are accepted, as on the add form.

---

### User Story 4 - A file saved back by a spreadsheet imports (Priority: P1)

Iryna opens the exported file in Excel with a Ukrainian regional setting, edits it and saves it as
CSV. Excel writes semicolons, no byte-order mark, `\r\n` line endings and a few `;;` rows where she
cleared rows. The file imports without an error, the empty rows are skipped, and an error in a later
row would still carry the row number Excel shows.

**Why this priority**: The administrators prepare banks in a spreadsheet; a file the spreadsheet
writes must import as it is.

**Independent Test**: Import files that differ only in separator, byte-order mark, line endings,
empty rows, spaces around `additional`, header case and spaces, and an unquoted quote, and compare
the resulting banks.

**Acceptance Scenarios**:

1. **Given** a file separated by semicolons, **When** it is imported, **Then** it is read as one
   separated by semicolons, since its header row holds no comma and a semicolon.
2. **Given** a file with or without the byte-order mark, and with `\r\n` or `\n` line endings,
   **Then** it imports the same.
3. **Given** a blank line or a row of only separators and spaces (`;;`), **Then** it is skipped and
   still counted in the row numbers; a row with only some fields empty is checked like any other.
4. **Given** spaces around the `additional` value (` 1 `), or an empty `additional` cell, **Then**
   they are read as `1` and `0`.
5. **Given** a header written `Question; ANSWER ;additional`, **Then** it is accepted: names are
   matched ignoring case and the spaces around them; a header with the names in another order is
   refused.
6. **Given** an unquoted field with a quote inside (`The "Iliad" by Homer`), **Then** the quote is
   kept as a character.
7. **Given** a text that starts with `=`, exported and imported back, **Then** it is unchanged.

---

### User Story 5 - The Subjects tab shows the count and puts actions in a menu (Priority: P2)

On a phone, the **Subjects** tab shows each subject as a card with its name, status and number of
questions, and one **Actions** button. In the menu of "History", **Import questions**, **Deactivate**
and **Delete** are in the danger colour. Iryna chooses **Deactivate**: the page "Deactivate
“History”?" says that the subject's questions and every one of its competitions that is not finished
are hidden from teachers until it is activated again. She presses **Deactivate** and returns to the
tab. Later she chooses **Activate**, confirms on "Activate “History”?", and the subject is active
again.

**Why this priority**: Five actions do not fit a phone card, and the menu only allows links, so the
two actions that used to act straight from the row need confirmation pages.

**Independent Test**: As an administrator, open the menu of an active and a deactivated subject on a
wide screen and at 360 px, check the entries and their order, then deactivate and activate through
the confirmation pages and with **Cancel**.

**Acceptance Scenarios**:

1. **Given** an administrator on the **Subjects** tab, **Then** every row shows a **Questions**
   column with the number of the subject's questions, the additional ones included and the deleted
   ones left out, `0` for none.
2. **Given** an active subject, **When** its actions menu is opened, **Then** it offers **Rename**,
   **Export questions**, **Import questions**, **Deactivate**, **Delete** in that order; for a
   deactivated subject, **Activate** in place of **Deactivate**. **Import questions**, **Deactivate**
   and **Delete** are destructive entries.
3. **Given** **Deactivate**, **Then** it opens the destructive confirmation "Deactivate “<subject>”?",
   saying that the subject's questions and every one of its competitions that is not finished are
   hidden from teachers until it is activated again, with **Deactivate** and **Cancel**; confirming
   deactivates the subject and returns to the tab.
4. **Given** **Activate**, **Then** it opens the primary confirmation "Activate “<subject>”?", saying
   that they are shown again, with **Activate** and **Cancel**; confirming activates the subject and
   returns to the tab.
5. **Given** either confirmation, **When** the administrator presses **Cancel**, **Then** they return
   to the tab and nothing changes.
6. **Given** a row, **Then** no action changes a subject straight from the row: every menu entry is a
   link to a page, and **Export questions** is a download that changes nothing.
7. **Given** a screen 360 px wide, **Then** the tab, the menu and every new page are usable without
   sideways scrolling, in both languages and both themes.

---

### User Story 6 - An AI assistant writes a file from the README (Priority: P2)

Iryna opens Claude Desktop, which has no access to the application, pastes the README section
"Question bank CSV files" and asks: "Write 150 history questions with their answers, three of them
additional." The assistant writes a file, goes through the section's checklist and hands it over.
Iryna imports it without an error.

**Why this priority**: A bank is often written outside the application; the README section is the
one description of the format for anyone outside it.

**Independent Test**: Read the README section and check that it states every rule of the import;
the automated test takes its example file from the README and imports it.

**Acceptance Scenarios**:

1. **Given** the README, **Then** it has a section "Question bank CSV files" that stands on its own
   and states every rule of the import exactly: the header row and column order; UTF-8 with the
   byte-order mark recommended; commas as the separator; how to quote a field (quoting every field
   is safe), double a quote inside it and keep a line break inside it; the `.csv` extension;
   `additional` as `0` or `1`; 1 to 2,000 characters for the text and the answer, counted in Unicode
   characters after trimming, with no null character; 1 to 1,000 questions and at most 2 MB a file.
2. **Given** the section, **Then** it says what the import does with the file: it replaces every
   question of the subject, so a file holds the whole bank, and to add questions the administrator
   exports the bank and gives the assistant the exported file to extend; the rows become the bank in
   their order, oldest first, which the study materials follow; texts are shown exactly as written
   and never translated, so they are plain text in the language of the competition, without Markdown
   and without a number of their own, and never start with `=`; the reference answer is what a
   team's answer is graded against, so it is complete enough to grade by; the additional questions
   are kept back from participants until a competition that holds them starts.
3. **Given** the section, **Then** it ends with a complete example file of a few Ukrainian
   questions, one of them additional, with a comma, a quote and a line break inside a field, and a
   short checklist the assistant goes through before handing the file over.
4. **Given** the example file taken from the README by the automated test, **When** it is imported,
   **Then** there is no error and the bank holds its questions in order, with the additional one
   marked.

---

### User Story 7 - An import and a teacher's change never mix (Priority: P2)

While Iryna's import of History runs, Olena adds a question to History. Olena's save waits until the
import ends, and her question is added after the imported ones. Had she saved a moment earlier, her
question would have been added before the import and replaced with the rest. Petro, who had the edit
form of a History question open, saves after the import and gets the page he would get for any
deleted question.

**Why this priority**: Without the lock, a question added during an import could end up beside the
imported ones, and the bank would not be what the file says.

**Independent Test**: On both database engines, start an import and send a teacher's add, edit,
delete or mark change of the bank, and another import, while it runs; check that each waits and that
reading the bank does not.

**Acceptance Scenarios**:

1. **Given** an import is running, **When** any other change of the bank of any subject is sent (a
   teacher adding, editing, deleting or marking a question, or another import), **Then** it waits
   until the import ends.
2. **Given** an import is running, **When** a teacher reads the bank, **Then** the read is not
   blocked.
3. **Given** a question added at the same moment as an import, **Then** it is either added before
   the import and replaced with the rest, or added after it, never left beside the imported
   questions.
4. **Given** a teacher editing or deleting a question of the subject while it is replaced, **When**
   they save, **Then** they get the page they would get for any deleted question (milestone 11).

---

### User Story 8 - Only administrators have the files (Priority: P2)

Olena, a teacher with **Can manage competitions**, types the address of **Export questions** for
History and gets the "access denied" page; so does a student, and so does Olena for **Import
questions** and for its form. Iryna opens the export of a subject that does not exist and gets the
page "Subject not found".

**Why this priority**: The file holds the additional questions, which are kept back from everyone
but the teachers with the setting (constitution Principle IV); only administrators may have it.

**Independent Test**: As a teacher with and without the setting, a student and an administrator,
request both addresses and send the import form, for an existing and a missing subject.

**Acceptance Scenarios**:

1. **Given** a teacher, with or without **Can manage competitions**, or a student, **When** they
   request the export, the import page or send the import form, for any subject or a missing one,
   **Then** they get the "access denied" page (milestone 5), the response holds no question, and
   nothing changes.
2. **Given** an administrator, **When** they request either address for a subject that does not
   exist, **Then** they get 404 with the page "Subject not found" (milestone 6).
3. **Given** a teacher, **Then** the **Questions** tab of the teacher area is unchanged and offers
   neither file.
4. **Given** an administrator, **Then** no page shows them a question: they see only the
   **Questions** column's numbers and the import page's count.

---

### User Story 9 - The new patterns are in the component library first (Priority: P3)

Before the import page is built, the component gallery shows a destructive confirmation with a file
field inside, the file field on its own with its label, hint and error, and the error summary with
row errors and the "And 5 more errors." line. The UI guidelines describe all three.

**Why this priority**: Constitution Principle II requires every new pattern in the library, the
gallery and the guidelines before a page uses it.

**Independent Test**: Open the component gallery and the UI guidelines and check the three patterns
in both languages and both themes.

**Acceptance Scenarios**:

1. **Given** the confirmation component, **Then** it accepts optional form content, placed between
   the consequence and the buttons, and sends a file when that content holds one.
2. **Given** the file field component, **Then** it is a native file input with its label, a hint
   ("A CSV file in the format described in the README, at most 2 MB") and its error.
3. **Given** the error summary, **Then** a new variant lists errors not linked to a field, each with
   its row, at most 20, then the line saying how many more there are; an error of the whole file has
   no row.
4. **Given** the component gallery and the UI guidelines, **Then** they show and describe all three
   patterns, and the guidelines give the **Subjects** tab's menu order.
5. **Given** the file field and the **Import questions** page, **Then** the product owner checks
   their look from screenshots in both languages and both themes, as a manual step of the
   implementation.

---

### Edge Cases

- **A subject with no questions**: the **Questions** column shows `0`, the export gives the header
  row only, and the import page says the subject has no questions yet; importing still asks for the
  destructive confirmation and adds the file's questions.
- **A subject whose only questions are deleted**: the column shows `0` and the export gives the header
  row only; after an import it still cannot be deleted.
- **A file whose every question is additional**: accepted; the bank then holds only additional
  questions, and the study materials of the subject are empty.
- **A file with only the header row, or only empty rows after it**: refused as holding no question.
- **An empty file, or one holding only the byte-order mark**: refused as having no header row.
- **A header with neither a comma nor a semicolon**: refused as a wrong header.
- **A header with a comma and a semicolon**: read with commas.
- **A header with an extra empty column** (`question;answer;additional;`): refused as a wrong header,
  since it has four fields.
- **A file that ends with or without a final line break**: both are accepted; the final line break
  does not make an empty row.
- **A quoted field followed by characters before the separator** (`"abc"def`): the characters are kept
  after the field's text, as a spreadsheet reads them.
- **A quote opened in a row after other rows with errors**: the earlier errors are listed, then the
  unclosed quote, and the check stops.
- **More than 1,000 questions and bad rows**: the whole-file error is listed first, then the row
  errors, up to 20 in all.
- **A file of 1,000 questions of 2,000 characters each**: larger than 2 MB, so refused by size; the
  limits are checked independently.
- **A file saved as UTF-16 or in a Windows Cyrillic code page**: refused with "Save the file as CSV
  UTF-8".
- **A file with a `.txt` extension but CSV content**: the file field offers `.csv`, but the content
  decides; it imports if it is valid.
- **A text with `\r\n` line breaks inside a field**: made uniform by the add form's line-ending rule,
  so it is stored as a text entered on the form would be.
- **Spaces around a question text or answer**: trimmed, as on the add form; a cell of only spaces is
  empty.
- **The subject is deleted or renamed while the import page is open**: deleted, the form answers
  "Subject not found"; renamed, the import works.
- **The subject is deactivated or activated while the import page is open**: the import works, since
  both are allowed.
- **Two administrators import the same subject at the same time**: the second waits for the first,
  then replaces its result.
- **The same file imported twice**: the second import deletes the first one's questions and adds
  them again under new numbers.
- **A teacher on the Questions tab of the subject during an import**: the page shows the bank before
  or after the import, never a mix.
- **An export just before and just after midnight in Kyiv** gives two file names with different dates.
- **A subject name with characters a file name cannot hold** (`A/B: History?`): replaced as in
  milestone 12.8; Cyrillic is kept.
- **A request to the export or import address by someone not signed in**: handled as for any page of
  the administrator area (milestone 5).

## Requirements *(mandatory)*

### Functional Requirements

#### The Subjects tab

- **FR-001**: The **Subjects** tab MUST show a **Questions** column with the number of each subject's
  questions, the additional ones included and the deleted ones left out, for active and deactivated
  subjects.
- **FR-002**: A subject's row actions MUST be in the actions menu of milestone 12.1, in this order:
  **Rename**, **Export questions**, **Import questions**, **Deactivate** (active subject) or
  **Activate** (deactivated subject), **Delete**. **Import questions**, **Deactivate** and **Delete**
  MUST be destructive entries. **Export questions** MUST be a download entry.
- **FR-003**: Every menu entry MUST be a link to a page or a download, never a form that changes data.
- **FR-004**: **Deactivate** MUST open a destructive confirmation page "Deactivate “<subject>”?" that
  says the subject's questions and every one of its competitions that is not finished are hidden from
  teachers until it is activated again, with **Deactivate** and **Cancel**. **Activate** MUST open a
  primary confirmation page "Activate “<subject>”?" that says they are shown again, with **Activate**
  and **Cancel**. Both MUST return to the **Subjects** tab.
- **FR-005**: Nothing else about deactivating, activating, renaming or deleting a subject changes
  (milestone 6): confirming a status the subject already has changes nothing and shows no error.
- **FR-006**: The **Subjects** tab MUST NOT show any question, only the count.

#### Access and checks

- **FR-007**: The export, the import page and the import form MUST be open to administrators only.
  Teachers, with or without **Can manage competitions**, and students MUST get the "access denied"
  page (milestone 5) for every subject and for a missing one, and nothing MUST change.
- **FR-008**: The checks MUST run in this order, the first failing one deciding the answer: the role
  ("access denied", before any id is read); then the subject (404 "Subject not found" for a subject
  that does not exist). The **Deactivate** and **Activate** pages MUST follow the same rules.
- **FR-009**: The import form and both confirmation forms MUST pass the existing cross-site request
  check; a cross-site submission MUST be refused and change nothing.
- **FR-010**: Following the export link or opening the export address MUST never change anything
  stored.
- **FR-011**: Both actions MUST be available for an active and for a deactivated subject.
- **FR-012**: The teacher area's **Questions** tab MUST stay as it is and offer neither file.

#### Export

- **FR-013**: **Export questions** MUST be a link marked as a download, like **Download results**
  (milestone 12.8): the file downloads straight away with no page in between, the administrator stays
  on the tab, the loading bar of milestone 10.1 does not start, and it works without JavaScript.
- **FR-014**: The export MUST hold every question of the subject's bank that is not deleted, the
  additional ones included, oldest first. A subject with no such question MUST give a file with the
  header row only.
- **FR-015**: The export MUST read the bank as it is at that moment and MUST NOT be stored.
- **FR-016**: The file MUST be named "<subject> <YYYY-MM-DD> question bank.csv", with the date of the
  export in Kyiv time and the words "question bank" in the current site language. Characters a file
  name cannot hold MUST be replaced as in milestone 12.8, and other characters, Cyrillic included,
  kept.

#### The CSV format

- **FR-017**: A file MUST have one header row and one row per question, with three columns in this
  order: `question`, `answer`, `additional`. The header row MUST be the same in both site languages.
- **FR-018**: `question` and `answer` MUST hold the question text and the reference answer exactly as
  stored, line breaks included; `additional` MUST hold `1` for an additional question (milestone 12.9)
  and `0` for every other.
- **FR-019**: The export MUST be UTF-8 with a byte-order mark, separated by commas, with fields quoted
  where needed and quotes inside a field doubled (RFC 4180), so a spreadsheet opens it with Cyrillic
  text intact and line breaks inside a cell.
- **FR-020**: A text that starts with `=`, `+`, `-` or `@` MUST be exported as it is, without a
  prefix, so the file imports back unchanged.
- **FR-021**: The file MUST NOT hold the bank number of a question, or anything about competitions.

#### Reading a file at import

- **FR-022**: The import MUST accept UTF-8 with or without the byte-order mark, separated by commas or
  semicolons, with `\r\n` or `\n` line endings.
- **FR-023**: The separator MUST be taken from the header row: a comma in it means commas; otherwise a
  semicolon means semicolons; a header with neither is wrong.
- **FR-024**: The header names MUST be matched ignoring case and the spaces around them, and MUST be
  exactly `question`, `answer`, `additional` in this order.
- **FR-025**: A row MUST be a record of the file, as a spreadsheet shows it: a quoted field with line
  breaks inside keeps its record one row. Row numbers MUST count the header as row 1 and MUST count
  skipped empty rows.
- **FR-026**: A row MUST be empty, and skipped, when every one of its fields is empty or only spaces
  (a blank line, or `;;`). A row with only some fields empty MUST be checked like any other.
- **FR-027**: Spaces around the value of `additional` MUST be ignored, and an empty `additional` MUST
  mean `0`.
- **FR-028**: `question` and `answer` MUST be cleaned by the rules of the teacher's add form
  (milestone 11): line endings made uniform, trimmed, and checked for a null character and for 1 to
  2,000 characters.
- **FR-029**: A quote inside a field that is not quoted MUST be kept as a character.

#### The import page

- **FR-030**: **Import questions** MUST open a page titled "Import questions: <subject>", a
  destructive confirmation (UI guidelines, "Confirmations") that says how many questions the subject
  has now and warns that importing deletes all of them and replaces them with the questions of the
  file, that this cannot be undone, and to export the current questions first to keep them.
- **FR-031**: The page MUST hold a file field that accepts `.csv`, with its label, the hint "A CSV
  file in the format described in the README, at most 2 MB" and its error; the destructive button
  **Replace questions**; and **Cancel** back to the **Subjects** tab.
- **FR-032**: After an error the page MUST show again with the file field empty, since a browser never
  refills a file field.
- **FR-033**: After a successful import the administrator MUST be sent back to the **Subjects** tab,
  so reloading does not repeat the import, and the **Questions** column MUST show the new number.

#### Checking the file

- **FR-034**: The whole file MUST be checked before anything changes, and the import MUST be all or
  nothing: if any check fails, the page shows again with every error found and the subject's
  questions stay exactly as they were.
- **FR-035**: The file MUST be refused when no file is chosen, when it is larger than 2 MB, when it is
  not UTF-8 ("Save the file as CSV UTF-8"), when the header row is missing or wrong, when it holds no
  question, or when it holds more than 1,000 questions. These are errors of the whole file and have no
  row number.
- **FR-036**: A row MUST be refused when it has a different number of fields than the header, when its
  `additional` is anything but `0`, `1` or empty, or when its question text or reference answer breaks
  a rule of the add form, with the add form's message. Each row error MUST start with its row number,
  as in "Row 7: Enter the reference answer.". A row with a different number of fields MUST give that
  error only.
- **FR-037**: A quote that is opened and never closed MUST be refused with "A quote opened in row N is
  never closed.", at the row where it opens, and the check MUST stop there.
- **FR-038**: Errors MUST be listed in row order, and within a row in column order; errors of the
  whole file come first. Each error counts once: a row with an empty text and an empty answer gives
  two errors.
- **FR-039**: At most the first 20 errors MUST be shown, followed by a line saying how many more there
  are ("And 5 more errors.").
- **FR-040**: Two rows with the same text MUST be allowed.

#### Replacing the questions

- **FR-041**: The import MUST happen in one transaction: every question of the subject that is not yet
  deleted is deleted the way a teacher deletes it (milestone 11), a soft deletion that keeps it
  stored; then every row of the file becomes a new question of the subject, in the order of the file,
  so the first row is the oldest, each with a new bank number and the additional mark of its row.
- **FR-042**: The numbers of the deleted questions MUST never be reused.
- **FR-043**: A competition that holds a deleted question MUST keep it, with the "Deleted from the
  question bank" mark of milestone 12.2, in every status; nothing else in a competition changes. Its
  answers, grades and stored results files (milestones 12.3, 12.4, 12.8) MUST stay unchanged.
- **FR-044**: The questions of every other subject MUST stay unchanged.
- **FR-045**: A subject that has had questions MUST still be refused deletion after an import, since
  its deleted questions are still stored (milestone 6); it can still be deactivated.
- **FR-046**: The study materials (milestone 12.10) MUST show the new questions at their next download,
  as for any other change of the bank.
- **FR-047**: The import MUST log one line with the subject id and the numbers of deleted and added
  questions, never a question text, an email address or a person's name.

#### Concurrency

- **FR-048**: While an import replaces the questions, the question bank MUST be locked for writing in
  the same transaction: every other change of the bank of any subject (a teacher adding, editing,
  deleting or marking a question, or another import) waits until the import ends. Reading the bank
  MUST NOT be blocked.
- **FR-049**: A question a teacher adds at the same moment MUST end either before the import, and be
  replaced with the rest, or after it, never beside the imported questions. A teacher who edits or
  deletes a question of the subject while it is replaced MUST get the page they would get for any
  deleted question (milestone 11).
- **FR-050**: The lock MUST hold on both supported database engines.

#### Components and guidelines

- **FR-051**: The confirmation component MUST get optional form content, placed between the
  consequence and the buttons, and MUST send a file when that content holds one.
- **FR-052**: A new file field component MUST be added: a native file input with its label, hint and
  error.
- **FR-053**: The error summary of milestone 10 MUST get a variant that lists errors not linked to a
  field, each with its row, at most 20, then the line saying how many more there are; an error of the
  whole file has no row.
- **FR-054**: These three patterns MUST be added to the component library, the component gallery
  (`/admin/components`) and the UI guidelines before the import page uses them (constitution
  Principle II). The UI guidelines MUST also give the **Subjects** tab's menu order.
- **FR-055**: Every new or changed page MUST be built from the component library with design tokens
  only, MUST follow the UI guidelines, MUST work without JavaScript, and MUST be usable at 360 px width
  with no sideways scrolling, in both themes and both languages.

#### The README

- **FR-056**: The README MUST get a section "Question bank CSV files", written for an AI assistant that
  has no access to the application, its code or its database, which stands on its own and states every
  rule of the import exactly, as listed in User Story 6, scenarios 1 and 2.
- **FR-057**: The section MUST end with a complete example file of a few Ukrainian questions, one of
  them additional, with a comma, a quote and a line break inside a field, and a short checklist the
  assistant goes through before handing the file over.
- **FR-058**: The section MUST be the one description of the format for anyone outside the
  application and MUST agree with this specification. An automated test MUST take the example file
  from the README and import it, so the README cannot drift from the import.

#### Languages

- **FR-059**: Every new text of the tab, the menu, the pages, the components, the errors and the file
  name MUST be in both message catalogues, Ukrainian and English, translated, with plural forms where
  a number is shown, and with no unused or obsolete entries, as the milestone 12.5 catalogue checks
  require. The texts quoted in this specification are the English ones. The CSV header row is never
  translated.

#### Documents

- **FR-060**: The product requirements and the constitution v2.8.0 already state the rules of this
  milestone; the implementation MUST NOT contradict them. When the milestone is delivered, its summary
  in `milestones.md` MUST be compacted into the "Delivered" section with a link to this specification.

#### Verification and scope

- **FR-061**: Automated tests MUST cover the acceptance scenarios of this specification and the
  milestone's "_Test:_" line: who sees the column and the two entries, and the refusals of teachers and
  students from both addresses; the 404 for an unknown subject; the menu order and the confirmation
  pages of **Deactivate** and **Activate**; the export's download marking, content, order, marks,
  encoding, byte-order mark, file name, and the empty subject; the round trip; the replacement, the
  other subjects, the deleted questions, the competitions and the refused subject deletion; on
  PostgreSQL, a teacher's change waiting for a running import; the spreadsheet variants (semicolons,
  no byte-order mark, `\r\n`, empty rows, spaces around `additional`, an unquoted quote); a text
  starting with `=`; the unclosed quote; two errors from one row; every refused file and row, with its
  row number and an unchanged bank; 25 bad rows giving 20 errors and "And 5 more errors."; the README
  example; the three patterns in the gallery; and the empty file field after a refused file.
- **FR-062**: The look of the file field and of the **Import questions** page, in both languages and
  both themes, MUST be checked by the product owner from screenshots, as a manual step of the
  implementation, and MUST NOT be automated.
- **FR-063**: This milestone MUST NOT add anything listed under **Out of Scope** below.

### Key Entities *(include if feature involves data)*

- **Question (of the bank)** (existing, milestones 11 and 12.9): its text, reference answer and
  additional mark are what a file holds; its bank number never is. An import soft-deletes the
  subject's questions and creates new ones; no new data is stored.
- **Subject** (existing, milestone 6): the bank a file belongs to; its name and the date name the
  export; its count of questions is shown on the **Subjects** tab.
- **A competition's question (copy)** (existing, milestone 12.2): kept unchanged when the question it
  came from is deleted by an import.
- **Question bank CSV file** (new, not stored): a header row and one row per question with
  `question`, `answer` and `additional`; made at every export, read and checked at every import.
- **Import error** (new, not stored): a message with an optional row number, shown on the import page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator replaces a subject's bank of 150 questions with a prepared file from
  the **Subjects** tab in under 1 minute, with three choices (**Actions**, **Import questions**,
  **Replace questions**) and one file choice.
- **SC-002**: In 100% of the tested round trips, a bank exported and imported back unchanged has the
  same texts, answers, additional marks and order.
- **SC-003**: In 100% of the tested refused files, the bank of every subject is exactly as it was
  before the import.
- **SC-004**: 100% of the tested row errors carry the row number a spreadsheet shows for that row,
  empty rows and multi-line cells included.
- **SC-005**: 100% of the tested files saved by spreadsheets (semicolons or commas, with or without the
  byte-order mark, `\r\n` or `\n`, with empty rows) import without an error.
- **SC-006**: The README's example file imports with 0 errors.
- **SC-007**: In the automated access check, 0 responses to teachers or students from the export and
  import addresses hold a question, and 100% are "access denied".
- **SC-008**: In 100% of the concurrency checks, a teacher's change sent during an import ends either
  before it and replaced, or after it, never beside the imported questions.
- **SC-009**: The export of a bank of 1,000 questions starts within 2 seconds, and the import of a valid
  file of 1,000 questions finishes within 10 seconds.
- **SC-010**: The **Subjects** tab, its menu and every new page are usable at 360 px width in both
  languages and both themes, with no sideways scrolling.
- **SC-011**: The product owner approves the look of the file field and the **Import questions** page
  from screenshots before the milestone is closed.

## Assumptions

- **The Ukrainian texts** follow the glossary: **Export questions** «Експортувати питання»,
  **Import questions** «Імпортувати питання», **Replace questions** «Замінити питання», "Import
  questions: <subject>" «Імпорт питань: <subject>», the file name words «банк питань», the
  **Questions** column «Питання», "Deactivate “<subject>”?" «Деактивувати «<subject>»?», "Activate
  “<subject>”?" «Активувати «<subject>»?». The exact wording is checked in review.
- **The messages the milestone does not give** are proposed as: "Choose a CSV file." (no file), "The
  file can be at most 2 MB." (too large), "The first row must be the header: question, answer,
  additional." (missing or wrong header), "The file holds no questions." (no question), "The file can
  hold at most 1,000 questions." (too many), "Row N: The row must have 3 fields." (wrong width),
  "Row N: Additional must be 0, 1 or empty." (wrong `additional`), and "And 1 more error." in the
  singular. The milestone's own texts are kept as given.
- **The checks that stop the reading**: no file, too large, not UTF-8, a missing or wrong header and an
  unclosed quote stop the check, since the rest of the file cannot be read; the errors already found
  are kept. More than 1,000 questions does not stop it: the rows are still checked.
- **The whole-file errors are shown on the file field** as its error and in the summary, linked to the
  field; row errors are in the summary only, not linked to a field.
- **2 MB** is 2 × 1024 × 1024 bytes, counted on the file as sent.
- **"Oldest first"** is the order in which the questions were added to the bank, as in milestone 12.10.
- **The 1,000-question limit** counts the rows that are not empty, the header left out.
- **A quoted field followed by other characters** before the separator keeps those characters after
  its text, as spreadsheets read it.
- **No success notice** is shown after an import, as after the other subject actions; the **Questions**
  column shows the result.
- **The Questions column** comes after the status column; its place is part of the screenshot review.
- **The import page offers no export link of its own**: the warning tells the administrator to export
  first, and **Export questions** is in the subject's menu.
- **No data change is needed**: nothing new is stored in the database.
- **The hosting plan runs the application as one process**; the lock is in the database, so it holds
  however many processes run.
- **Every quoted text above** is taken from the milestone where the milestone gives it.

## Dependencies

- **Constitution v2.8.0** (amended on 2026-11-28 for this milestone): Principle II (component library
  first), Principle III (allowed and denied access tested on every route), Principle IV
  (administrators, and only they, export and import a subject's bank as CSV files, additional questions
  included; the import soft-deletes the replaced questions; administrators see no question on any page)
  and Principle VII (soft deletion keeps competitions' copies and results; a database-specific lock is
  justified in the plan).
- **Product requirements** (updated with the milestone): the "Administrator", "Teacher
  responsibilities", "Teacher access rights" and "Additional questions" sections.
- **Milestone 5**: roles, "access denied" and the automated route check.
- **Milestone 6**: the **Subjects** tab, its actions, "Subject not found" and the in-use check.
- **Milestone 7**: the confirmation page before **Deactivate** for a region and an institution.
- **Milestones 10 and 10.1**: the component library, the gallery, the UI guidelines, the error summary
  and the loading feedback.
- **Milestone 11**: the question bank, the add form's cleaning rules and messages, soft deletion, bank
  numbers and the page for a deleted question.
- **Milestone 12.1**: the actions menu.
- **Milestone 12.2**: a competition's copies of questions and the "Deleted from the question bank" mark.
- **Milestones 12.3, 12.4 and 12.8**: the answers, grades and results files a deleted question keeps,
  and the download entry and file name rule of milestone 12.8.
- **Milestone 12.5**: the two languages, the message catalogues and Kyiv time.
- **Milestone 12.9**: the additional mark the file carries.
- **Milestone 12.10**: the study materials, which follow the bank's order.

## Out of Scope

- Exporting or importing for teachers or students, or for anyone not signed in.
- Adding to a bank, merging, or updating questions by matching rows to existing ones; the import only
  replaces.
- A preview of the file before the import, importing the valid rows and skipping the bad ones, or
  undoing an import.
- Showing, adding or editing single questions in the administrator area.
- Other formats (spreadsheet files, JSON, plain text), several subjects in one file, or files that
  hold bank numbers, deleted questions or anything about competitions.
- Storing the exported or imported files.
- Protecting texts that start with `=`, `+`, `-` or `@` from being read as formulas by a spreadsheet,
  an accepted risk.
- Writing questions with an AI assistant inside the application.
- Answer evaluation by an LLM (milestone 13) and results on the web pages (milestone 14).
