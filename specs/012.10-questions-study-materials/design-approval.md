# Design Approval: Milestone 12.10

**Feature**: [spec.md](./spec.md) (User Story 7, FR-046–FR-049, SC-010) | **Research**: [research.md](./research.md) R4, R8, R11

- **Approver**: the product owner.
- **What is reviewed**:
  - the design of the questions file and of the study materials (layout, fonts, spacing, the
    header, the numbering, the answer label and the wording), in Ukrainian and in English;
  - the look and place of the **Download study materials** link on the **Competitions** tab.
- **Not reviewed**: the content and order of the files, which the spec fixes
  ([contracts/files.md](./contracts/files.md)).
- **The samples**: [samples/](./samples/), made by
  `uv run python scripts/make_question_file_samples.py` with the application's own renderers,
  so they are exactly what a download gives. The script is deterministic: running it again
  without a design change leaves the files as they are.
- **The screenshots**: [samples/screenshots/](./samples/screenshots/). They come from an ad hoc
  headless Playwright run against a throwaway database (not part of the application), with a
  browser time zone set, as a real browser has.
- **The gate**: the milestone is not delivered before a round below has the status **Approved**
  and its date (FR-049). That is tasks T049 and T050, both by hand.

## The samples

| Set | Ukrainian | English | What it shows |
|---|---|---|---|
| Long questions | [questions-long-uk.pdf](./samples/questions-long-uk.pdf) | [questions-long-en.pdf](./samples/questions-long-en.pdf) | 24 long Ukrainian questions with ’, ґ, є, ї, subscripts and line breaks, over two pages with the running title and "Page n of N" |
| No questions | [questions-empty-uk.pdf](./samples/questions-empty-uk.pdf) | [questions-empty-en.pdf](./samples/questions-empty-en.pdf) | "This competition has no questions." |
| 150 questions | [study-materials-150-uk.pdf](./samples/study-materials-150-uk.pdf) | [study-materials-150-en.pdf](./samples/study-materials-150-en.pdf) | «Історія України», 150 questions with answers from one sentence to more than half a page, 34 pages |
| No questions | [study-materials-empty-uk.pdf](./samples/study-materials-empty-uk.pdf) | [study-materials-empty-en.pdf](./samples/study-materials-empty-en.pdf) | "This subject has no questions yet." |

The labels follow the file's language; the questions, answers and names are the same Ukrainian
text in both, since what people enter is never translated.

| Screenshot | Ukrainian | English |
|---|---|---|
| Desktop, light | [tab-uk-light-1280.png](./samples/screenshots/tab-uk-light-1280.png) | [tab-en-light-1280.png](./samples/screenshots/tab-en-light-1280.png) |
| Desktop, dark | [tab-uk-dark-1280.png](./samples/screenshots/tab-uk-dark-1280.png) | [tab-en-dark-1280.png](./samples/screenshots/tab-en-dark-1280.png) |
| Phone (360 px), light | [tab-uk-light-360.png](./samples/screenshots/tab-uk-light-360.png) | [tab-en-light-360.png](./samples/screenshots/tab-en-light-360.png) |
| Phone (360 px), dark | [tab-uk-dark-360.png](./samples/screenshots/tab-uk-dark-360.png) | [tab-en-dark-360.png](./samples/screenshots/tab-en-dark-360.png) |
| Gallery: the aside | [gallery-selectors-1280.png](./samples/screenshots/gallery-selectors-1280.png) | [gallery-selectors-360.png](./samples/screenshots/gallery-selectors-360.png) |

## Round 1 (2026-11-23): the initial design

**Status**: **Approved** (2026-11-23).

**Both files** share the results file's design (`app/services/pdf_layout.py`):

- **Page**: A4 portrait, 20 mm margins; Open Sans Regular and Bold, embedded as subsets.
- **Header**: the dark emblem, 18 mm high, top left; the title in Bold 16 pt; the subject in 11 pt;
  one muted 10 pt line:
  - questions file: «Початок: 21 листопада 2026, 10:00 (за київським часом)»;
  - study materials: «Завантажено: 23 листопада 2026».
- **Every page**: «Сторінка n з N» centred at the foot. From page 2, a small running title at the
  top: «Питання змагань «<name>»» or «Навчальні матеріали: <subject>».

**The list** (research R4):

- **Numbering**: "1.", "2.", … in Bold 10.5 pt, in a column as wide as the widest number. The text
  is in Regular 10.5 pt beside it, and wrapped lines align under the text. Entries are 4 mm apart.
- **Answers** (study materials only): 1.5 mm under the question, at the text's indent: «**Відповідь:**»
  in bold, then the answer in regular type.
- **Line breaks** are kept.
- **Keeping entries whole**: an entry (with its answer) that does not fit on the rest of a page
  starts on the next one. An entry taller than a page is split.

**The link**: a small secondary outline button, «Завантажити навчальні матеріали» / **Download
study materials**. On a wide screen it sits in the third column beside **Subject** and **Status**,
level with the bottom of the lists. On a phone it sits under them.

**Measured**: the 150-question study materials take about 0.8 s to make on a development
laptop (Apple silicon). The hosting plan's single slow processor will take longer, which is why
the file is kept in memory between changes.

**Questions for the product owner** (any change is made within this milestone):

1. **Ukrainian wording**: are these the words you want?
   - «Навчальні матеріали» (title and file name);
   - «Завантажено: …» (download date);
   - «Відповідь:» (answer label);
   - «З цього предмета ще немає питань.» (empty study materials);
   - «У цьому змаганні немає питань.» (empty questions file);
   - «питання» in the file name;
   - «Завантажити питання» and «Завантажити навчальні матеріали» (menu entry and link).

   The questions file's title reuses the existing title of the **Questions** page, «Питання
   змагань «<name>»», so the two read the same.
2. **The answer label**: bold «Відповідь:» on the same line as the answer, or a separate small
   line above it?
3. **Spacing**: is 4 mm between entries right, for reading on paper and for writing an answer
   by hand?
4. **A page with only the header** ([study-materials-150-uk.pdf](./samples/study-materials-150-uk.pdf),
   page 1): the first question has an answer of about a page. Keeping it whole moves it to page
   2, which leaves page 1 with only the header. Is that acceptable for such rare long answers, or
   should an entry taller than the rest of the first page start right after the header and split?
5. **Symbols the font lacks**: Open Sans has no glyph for some symbols a teacher may type, such
   as the arrow "→" in a chemical equation. In
   [questions-long-uk.pdf](./samples/questions-long-uk.pdf), question 3, it prints as nothing:
   "2H₂ + O₂  2H₂O". The subscripts (₂, ₄) do render. Options:
   - a fallback font for such symbols (a new embedded font file);
   - a note in the question form;
   - accept it as rare.
6. **The link**: are its place and its look right, or should it be a plain text link or
   somewhere else?

**Decision** (2026-11-23): approved as shown. The product owner reviewed the sample files and
the screenshots and asked for no change. The open points above stay as the samples show them:
- the Ukrainian wording;
- the answer label on the same line as the answer;
- 4 mm between entries;
- a long first entry moving to page 2;
- the "→" glyph printing as nothing, accepted as rare;
- the link's place and look.

The approved round is round 1, with the samples and screenshots committed beside this record.

## Found while making the screenshots (not part of this milestone)

On a 360 px screen in Ukrainian, when the browser has not yet reported its time zone, the start
time in a competition's card, «1 березня 2027, 10:00 (за київським часом)», does not wrap and the
page scrolls sideways by about 30 px. With the browser's zone known (every real visit after the
first page), the label is not shown and every view fits. This comes from the start-time column of
milestones 12.1 and 12.5, not from the new link.

**Decision** (2026-11-23): the product owner confirmed this behaviour is correct. It is not a
defect, and no fix is planned.
