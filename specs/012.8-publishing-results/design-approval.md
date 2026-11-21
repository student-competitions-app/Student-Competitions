# Design Approval: Milestone 12.8

**Feature**: [spec.md](./spec.md) (User Story 8, FR-038–FR-040, SC-008) | **Research**: [research.md](./research.md) R8, R12

- **Approver**: the product owner.
- **What is reviewed**: the design of the results files: the layout, the fonts, the size and place
  of the logo, the header, the spacing and the wording, in Ukrainian and in English. The content
  and order of the files are fixed by the spec ([contracts/results-file.md](./contracts/results-file.md))
  and are not part of the review.
- **The samples**: [samples/](./samples/), made by `uv run python scripts/make_results_samples.py`
  with the application's own renderer, so they are exactly what publishing stores. The script is
  deterministic: running it again without a design change leaves the files as they are.
- **The gate**: the milestone does not merge before a round below has the status **Approved** and
  its date (FR-040).

## The samples

| Set | Ukrainian | English | What it shows |
|---|---|---|---|
| Long list | [long-list-uk.pdf](./samples/long-list-uk.pdf) | [long-list-en.pdf](./samples/long-list-en.pdf) | Seven regions, sixty teams, Cyrillic names with ʼ, ’, ґ, є, ї; two pages with the running title and "Page n of N" |
| Long names | [long-names-uk.pdf](./samples/long-names-uk.pdf) | [long-names-en.pdf](./samples/long-names-en.pdf) | A competition, institution and team names of about 200 characters, wrapping |
| No teams | [no-teams-uk.pdf](./samples/no-teams-uk.pdf) | [no-teams-en.pdf](./samples/no-teams-en.pdf) | "No teams took part in this competition." |

## Round 1 (2026-11-21): the initial design

**Status**: changes requested (2026-11-21), made in round 2.

The starting point of research R8:

- **Page**: A4 portrait, 20 mm margins; Open Sans Regular and Bold, embedded as subsets.
- **Header, page 1**:
  - the emblem in dark ink, 18 mm high, top left;
  - the title "Results of “<name>”" / «Результати «<name>»», Bold 16 pt, wrapping;
  - the subject, 11 pt;
  - "Started:", "Finished:" (date and time, Kyiv time, labelled) and "Published:" (the date), 10 pt,
    muted.
- **Body**: per region, a Bold 12 pt heading over a thin rule, then one line per team,
  "Institution, Team, Score", 10.5 pt. A region heading never ends a page.
- **Every page**: "Page n of N" / «Сторінка n з N» centred at the foot, 9 pt, muted; from page 2,
  the title small at the top.

**Questions for the product owner** (any change is made within this milestone, FR-040):

1. **Logo**: is 18 mm the right size, and top left the right place?
2. **Team lines**: a long institution and team name wraps under itself, and the next team follows
   with no gap ([long-names-uk.pdf](./samples/long-names-uk.pdf)). Should the score stand in its
   own right-aligned column, or should entries be spaced apart?
3. **Header wording**: are «Початок», «Завершено» and «Опубліковано» the words you want, and
   should the publishing date carry a time?
4. **Anything else**: fonts, spacing, the running title, the page number.

**Decision** (2026-11-21): changes requested.

- **Maximum score**: under "Published", show the maximum score a team could get. Made: "Maximum
  score: <n>" / «Максимальний бал: <n>», 10 for each of the competition's questions.
- **A table per region**: under each region's heading, a table with the school, the team and the
  score, the last column just wide enough for the score. Made: the columns "Educational
  institution", "Team", "Score" («Заклад освіти», «Команда», «Бал»); the score column is measured
  to fit its heading or the widest score, right-aligned; the other two share the rest (56% / 44%),
  long names wrapping within their cell; the heading row repeats on a page the table continues
  onto. This also answers question 2 (long entries no longer run together).
- Recorded as rules in the spec's Clarifications, FR-023 and FR-025.

## Round 2 (2026-11-21): maximum score and tables

**Status**: **Approved** (2026-11-21).

The samples in [samples/](./samples/) are made again with the round 1 changes:

- [long-list-uk.pdf](./samples/long-list-uk.pdf) / [long-list-en.pdf](./samples/long-list-en.pdf):
  seven tables over four pages, the heading row repeated where a table continues;
- [long-names-uk.pdf](./samples/long-names-uk.pdf) / [long-names-en.pdf](./samples/long-names-en.pdf):
  names of about 200 characters wrapping inside their cells, the score column staying narrow;
- [no-teams-uk.pdf](./samples/no-teams-uk.pdf) / [no-teams-en.pdf](./samples/no-teams-en.pdf):
  the maximum score, then "No teams took part in this competition.".

Still open from round 1: the logo's size and place (question 1), the header wording and whether the
publishing date carries a time (question 3), and anything else (question 4).

**Decision** (2026-11-21): **approved**. The product owner's words: "I approve the pdfs in the
samples folder." The open questions are settled as the samples show them: the logo 18 mm high, top
left; «Початок», «Завершено», «Опубліковано» and «Максимальний бал» as they are; the publishing
date without a time; nothing else changed. The gate of FR-040 is met.
