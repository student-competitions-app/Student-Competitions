# Feature Specification: Ukrainian Localisation (Milestone 12.5)

**Feature Branch**: `012.5-ukrainian-localisation`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User description: "create specification for the 12.5 localization feature": milestone 12.5
of `docs/requirements/milestones.md` ("Ukrainian localisation"), placed in the 12.x group before the
student's side is built, with `product-requirements.md`, `technical-requirements.md`, the constitution
v2.4.0 (the **Localisation** row of the Technology Stack, Principles II, III, IV, V and VII), the
milestone 4, 7, 8, 10, 10.1, 11.1 and 12.1 specifications and `docs/requirements/ui-guidelines.md` as
reference.

## Overview

Milestone 12.5 of the walking skeleton for the Student Competitions application. It is not about
competitions: it makes the whole application bilingual, Ukrainian and English, before the student's
side (milestone 13) is built, so every later milestone is written in both languages from the start.

The application is used in Ukrainian educational institutions, schools and colleges. Today every page,
email and consent text is in English, Ukrainian names sort in the wrong order (Ґ, Є, І and Ї after Я),
and times fall back to UTC. Ten things become true when this milestone is done:

1. **Ukrainian is the default.** Every page opens in Ukrainian, whatever the browser's own language
   preference, and the application is called «Студентські змагання» in Ukrainian.
2. **A language switch in the top bar of every page**, signed in or signed out, changes the language to
   English and back, keeping the reader on the same page. It works without JavaScript.
3. **The choice is kept per browser**, for a year, through signing in, switching role and signing out.
4. **Everything the application says is translated**: every page, component, form error, notice, error
   page, page title, hidden text for screen readers, label, count and date. What people enter is shown
   as they entered it.
5. **Ukrainian reads naturally**: a glossary fixes the word for every product term, and the Ukrainian
   text follows Ukrainian typography, plural forms, grammatical cases and a rule that never guesses a
   person's gender.
6. **Names sort in the order of the Ukrainian alphabet**, and names that differ only by the kind of
   apostrophe count as the same name.
7. **Times have one format in each language**, in the browser's time zone when it is known, and in Kyiv
   time, labelled, when it is not, and in every email.
8. **Emails follow the language**: the sign-in code and the data-deletion link in the chosen language;
   the invitation in Ukrainian followed by English.
9. **The consent texts are bilingual**: version 1 of the teacher text and of the student text is
   rewritten in place, Ukrainian first, and the Ukrainian wording prevails.
10. **The binding documents are updated**: the product requirements gain a **Languages** section and the
    UI guidelines cover localisation; the constitution (v2.4.0) and the technical requirements already
    list the Localisation stack.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A first visit opens in Ukrainian (Priority: P1)

Oksana, a teacher at a college in Lviv, opens the application for the first time on a laptop whose
browser prefers English. The sign-in page is in Ukrainian: the page title, the heading, the label of
the email field, the button and the hint. The top bar shows the application's name «Студентські
змагання» and, before where the user menu would be, a language switch showing the Ukrainian flag and
**Українська**.

**Why this priority**: The application's users are Ukrainian; a first page in English is the problem
this milestone solves.

**Independent Test**: With no language chosen and a browser that asks for English first, open the
sign-in page, the data-deletion page and an invitation link, and check that each is in Ukrainian and
marked as Ukrainian for assistive technology.

**Acceptance Scenarios**:

1. **Given** a browser that has never chosen a language, **When** it opens the sign-in page, **Then**
   every text on the page is Ukrainian and the page is marked as written in Ukrainian (`uk`).
2. **Given** a browser whose language preference is English, French or anything else, **When** no
   language was chosen in the application, **Then** the page is still Ukrainian.
3. **Given** a stored choice that is neither Ukrainian nor English (an old, damaged or crafted value),
   **When** a page opens, **Then** it is in the default language, Ukrainian, and nothing fails.
4. **Given** any page in Ukrainian, **When** it is read by a screen reader, **Then** the page language
   is Ukrainian, so the reader pronounces it as Ukrainian.

---

### User Story 2 - Anyone switches the language on any page (Priority: P1)

On the sign-in page Oksana opens the language switch. It lists the Ukrainian flag with **Українська**
and the United Kingdom flag with **English**, each name written in its own language; the current one is
marked. She chooses **English**: the same sign-in page comes back in English, and the switch now shows
the British flag and **English**. She signs in, switches role and signs out: the pages stay in English.
Later she chooses **Українська** on the **Competitions** tab and stays on the **Competitions** tab, now
in Ukrainian, with the same subject, status filter and page.

**Why this priority**: The switch is the only way to read the application in English, and staff who
prefer English need it on every page.

**Independent Test**: On a signed-out page, on a page of each role, on an error page and on a page that
was shown after a form error, choose each language with JavaScript turned off, and check where the
browser lands, in which language, and that the choice survives signing in and out.

**Acceptance Scenarios**:

1. **Given** any page, signed in or signed out, including the sign-in, code entry, role choice,
   invitation, data-deletion and error pages, **When** it is shown, **Then** the language switch is in
   the top bar, before the user menu where there is one.
2. **Given** the switch is opened, **When** the person reads it, **Then** it lists **Українська** with
   the Ukrainian flag and **English** with the United Kingdom flag, each name marked as written in its
   own language, the current language marked for assistive technology, and each option at least 44 by
   44 px.
3. **Given** a page with a query (a subject, a status filter, a page number), **When** a language is
   chosen, **Then** the browser returns to the same address, now in the chosen language.
4. **Given** a page that was only shown in answer to a form submission (a form with errors), **When** a
   language is chosen, **Then** the browser returns to the page of that address that can be opened
   directly, or, when there is none, to the home page signed in or the sign-in page signed out, as the
   theme switch does.
5. **Given** a crafted choice whose return address points to another site, a protocol-relative address
   or a sign-in step that only accepts form submissions, **When** it is sent, **Then** the browser goes
   to the home page signed in, or the sign-in page signed out, and the language is still changed.
6. **Given** a crafted choice naming a language other than Ukrainian or English, **When** it is sent,
   **Then** the stored choice is not changed to it, and the browser returns as above.
7. **Given** a choice sent from another site, **When** it arrives, **Then** it is refused by the
   application's existing cross-site check, like every other form submission.
8. **Given** English was chosen, **When** the person signs in, switches role or signs out, **Then** the
   pages stay in English; none of these reads or changes the choice.
9. **Given** a phone (below 768 px), **When** the switch is closed, **Then** it shows the flag alone;
   its language name is still read by screen readers; opened, it lists both languages in full.
10. **Given** JavaScript is turned off, **When** the switch is opened and a language chosen, **Then** it
    works exactly as with JavaScript.

---

### User Story 3 - Every screen of every role speaks the chosen language (Priority: P1)

Signed in as an administrator, a teacher and a student, the product owner goes through every tab with
Ukrainian chosen. Every heading, button, label, hint, placeholder, form error, notice, empty state,
confirmation, refusal, status badge, access level, role name, count, page navigation text, menu entry,
page title and hidden screen-reader text is in Ukrainian, with the glossary's terms. Names of subjects,
regions, institutions, classes, teams and competitions, people's names, questions, reference answers
and answers are shown exactly as entered.

**Why this priority**: A half-translated application is not usable by Ukrainian staff and students.

**Independent Test**: With Ukrainian and then English chosen, render every page and fragment of every
role and every error page, and check that no message of the application is left untranslated and that
user-entered texts are unchanged.

**Acceptance Scenarios**:

1. **Given** Ukrainian is chosen, **When** any page of the application is shown (outside the content of
   the component gallery), **Then** every text the application itself writes is Ukrainian.
2. **Given** a form submitted with errors, **When** the page is shown again, **Then** the error summary
   heading and every field error are in the chosen language, and the values entered are kept as typed.
3. **Given** a list with a count, **When** it shows 1, 2, 5, 11, 21, 22 or 25 items, **Then** the
   Ukrainian noun takes the right plural form (1 команда, 2 команди, 5 команд, 11 команд, 21 команда,
   22 команди, 25 команд), and the English one its singular or plural.
4. **Given** the statuses **Upcoming**, **In progress**, **Finished** and **Cancelled**, **Active** and
   **Deactivated**, the access levels **Read** and **Write**, and the three roles, **When** they are
   shown, **Then** each is the glossary's term in the chosen language, everywhere.
5. **Given** an "access denied" page, a "request refused" page or a "not found" page, **When** it is
   shown, **Then** its frame, heading and links are in the chosen language; a detail text that comes
   from the web framework itself ("Not Found", "Method Not Allowed") is shown as it comes.
6. **Given** a subject named "Physics" and a question written in English, **When** Ukrainian is chosen,
   **Then** both are shown exactly as entered, in English; a subject named «Фізика» stays «Фізика» in
   English.
7. **Given** the theme switch in the user menu and under the sign-in form, **When** it is shown, **Then**
   its options are in the chosen language.

---

### User Story 4 - Emails arrive in the right language (Priority: P1)

With Ukrainian chosen, Oksana asks for a sign-in code: the email's subject and text are Ukrainian. With
English chosen, the next code arrives in English. On the data-deletion page, with English chosen, she
asks to delete her data: the link arrives in English, saying it works until "22 October 2026, 17:05
(Kyiv time)". As an administrator she invites a teacher: the invitation's subject and text hold both
languages, Ukrainian first, whatever language she chose, because the invited person's language is not
known.

**Why this priority**: The sign-in code and the invitation are the first things a person reads; they
must be readable before the person has chosen anything.

**Independent Test**: Send the sign-in code and the data-deletion link with each language chosen and
with none, and send a teacher's and a student's invitation with each language chosen, and read the
captured messages.

**Acceptance Scenarios**:

1. **Given** Ukrainian is chosen (or no language), **When** a sign-in code is sent, **Then** its subject
   and text are Ukrainian; **Given** English is chosen, **Then** they are English. The code stays in the
   text only, never in the subject.
2. **Given** a language is chosen on the data-deletion page, **When** the link is sent, **Then** the
   email is in that language and gives its expiry in Kyiv time, labelled.
3. **Given** any language is chosen by the inviting administrator or teacher, **When** an invitation is
   sent, **Then** its subject holds the Ukrainian subject followed by the English one, and its text holds
   the whole Ukrainian message followed by the whole English message, each naming the role, the details
   that will be stored, the link and the expiry in Kyiv time, labelled in that language.
4. **Given** an invitation that names institutions, a class or a person, **When** it is sent, **Then**
   those names appear exactly as entered in both parts, and the inviter is named without a word that
   shows their gender ("X запрошує вас").
5. **Given** any email, **When** it is sent, **Then** the sender's name is the one configured for the
   deployment, unchanged.

---

### User Story 5 - The consent text is bilingual (Priority: P1)

A student opens an invitation with English chosen. The page around the consent text is in English, and
the consent text shows the Ukrainian wording first, under «Українською», then the English wording,
under "English". Both say that the Ukrainian wording prevails if the two differ. She accepts; her
profile shows the same bilingual text as the text she agreed to, version 1.

**Why this priority**: Consent is the legal basis for storing personal data, and its binding wording
must be the Ukrainian one.

**Independent Test**: Open a teacher's and a student's invitation in each language, accept, open the
profile in each language, and check the order, the headings, the language marking and the version
recorded.

**Acceptance Scenarios**:

1. **Given** a teacher's or a student's invitation, **When** it is opened in either language, **Then**
   the consent text shows the Ukrainian wording first and the English wording after it, under their
   headings, and the rest of the page follows the chosen language.
2. **Given** the consent text on a page, **When** a screen reader reads it, **Then** the English part is
   marked as English, and the Ukrainian part as Ukrainian.
3. **Given** a person accepts, **When** the record is stored, **Then** it points to version 1 of that
   role's text, which now holds both wordings, so it proves agreement to both.
4. **Given** the profile of a person who accepted, **When** it is opened in either language, **Then** it
   shows the accepted bilingual text in the same order.
5. **Given** the current consent texts, **When** they are compared with the pinned checksums, **Then**
   each role's current text is its bilingual version 1, each earlier wording is still pinned as
   superseded, and any further rewrite is refused.

---

### User Story 6 - Ukrainian names sort in alphabetical order (Priority: P2)

On the **Students** tab, a class lists "Гончаренко, Ґудзь, Євтушенко, Іваненко, Їжакевич, Ющенко,
Яковенко" in that order, in both languages, where today Ґудзь, Євтушенко, Іваненко and Їжакевич come
after Яковенко. An administrator who tries to create the region "Мар’янівка" next to an existing
"Мар'янівка" is told that a region with that name already exists.

**Why this priority**: Wrong order makes long lists of names hard to scan, and two regions that differ
only by an invisible apostrophe variant confuse everyone; but the application works without it.

**Independent Test**: Create names covering every Ukrainian letter, Latin names, Russian-only letters,
digits and the five apostrophe variants in every list ordered by a name, and check the order and the
duplicate refusals in both languages.

**Acceptance Scenarios**:

1. **Given** any list ordered by a name, **When** it is shown, **Then** it follows the Ukrainian
   alphabet (А Б В Г Ґ Д Е Є Ж З И І Ї Й К Л М Н О П Р С Т У Ф Х Ц Ч Ш Щ Ь Ю Я), ignoring case, in both
   languages.
2. **Given** Latin and Cyrillic names, **When** they are listed together, **Then** the Latin names come
   first, in their existing order.
3. **Given** a name with a Russian-only letter (Ё, Ъ, Ы, Э), **When** it is listed, **Then** that letter
   comes after the letters of the Ukrainian alphabet, in Unicode order.
4. **Given** "Мар'яна", "Мар’яна", "Марʼяна", "Мар‘яна" and "Мар`яна", **When** they are sorted,
   **Then** the apostrophe is ignored; **When** one of them is entered as the name of a subject, region,
   institution, class, team or competition where another already exists in the same scope, **Then** it
   is refused as a duplicate with the existing duplicate-name message.
5. **Given** a name entered with any apostrophe, **When** it is saved, **Then** it is stored and shown
   exactly as typed.
6. **Given** people's names, **When** they are listed, **Then** they are ordered by last name, then
   first name, each by the Ukrainian alphabet.

---

### User Story 7 - Times read the same way everywhere (Priority: P2)

A teacher whose browser reports Europe/Kyiv sees "Spring round" starting «14 березня 2027, 10:00» in
Ukrainian and "14 March 2027, 10:00" in English, with no label. In a browser that blocks scripts, the
same start reads «14 березня 2027, 10:00 (за київським часом)», and the competition form's hint says
"Time zone: Europe/Kyiv". Back in her own browser, her profile's consent record reads «Прийнято 22
жовтня 2026, 17:05» instead of "Accepted 2026-10-22 14:05 UTC".

**Why this priority**: Times are read in competitions and in emails; one format avoids mistakes, and
Kyiv time is what every reader in Ukraine expects when the browser's zone is unknown.

**Independent Test**: Render every page that shows a time or a date with a known zone, with no zone and
in each language, and render each email, and compare the texts.

**Acceptance Scenarios**:

1. **Given** a known browser time zone, **When** a time is shown on a page, **Then** it reads "14 March
   2027, 10:00" or «14 березня 2027, 10:00» in that zone, with no label: the day without a leading
   zero, the month in full (in Ukrainian in the genitive case), a 24-hour clock.
2. **Given** no known browser time zone, **When** a time is shown on a page, **Then** it is in Kyiv time
   and labelled "(Kyiv time)" or «(за київським часом)».
3. **Given** no known browser time zone, **When** a competition's start is entered in a form, **Then**
   the time entered is read as Kyiv time, and the hint says "Time zone: Europe/Kyiv" in the chosen
   language.
4. **Given** the profile's consent records, the invitation page's expiry and the administrator's
   **Teachers** list, **When** they are shown, **Then** their times and dates use the same format and
   zones as the competitions; a date alone reads "15 October 2026" or «15 жовтня 2026».
5. **Given** any email that gives a time, **When** it is sent, **Then** the time is in Kyiv time and
   labelled in the email's language.
6. **Given** a time on either side of a daylight-saving change in Kyiv, **When** it is shown, **Then** it
   is the correct local time for that date.

---

### User Story 8 - Ukrainian text is natural and consistent (Priority: P2)

The product owner reads the Ukrainian pages. Each product term is always the same word, the one in the
glossary. Quotation marks are «…». A name never changes its ending to fit the sentence: «Видалити
предмет «Фізика»?», «Назад до регіону «Київ»», «Вилучити зі списку: Олена Коваленко?». No sentence about
another person guesses their gender: "Олена Коваленко запрошує вас", not "запросила". The reader is
addressed as «ви».

**Why this priority**: Wrong cases, gendered guesses and inconsistent terms look careless and confuse
young readers; the product owner approves the glossary before acceptance.

**Independent Test**: Review every Ukrainian message against the glossary and the writing rules, and
check automatically that no message is built from pieces and that every message has its translation.

**Acceptance Scenarios**:

1. **Given** the glossary, **When** any page uses a product term, **Then** it uses the glossary's word.
2. **Given** a message that includes a name people entered, **When** it is shown in Ukrainian, **Then**
   the name appears unchanged, in quotation marks, after a noun in the case the sentence needs, or, for
   a person's name, after a colon.
3. **Given** a message about another person, **When** it is shown in Ukrainian, **Then** no verb,
   participle or adjective in it changes with that person's gender.
4. **Given** a quotation inside a quotation, **When** it is shown in Ukrainian, **Then** the outer marks
   are «…» and the inner „…“.
5. **Given** any Ukrainian text the application writes, **When** it contains an apostrophe, **Then** it is
   ʼ.

---

### User Story 9 - The layout holds in Ukrainian (Priority: P2)

Ukrainian text is about a quarter longer than English. On a 375 px phone, the teacher's area with its
four Ukrainian tab names, the top bar with the application's name, the longest role name, the flag and
the account icon, still fits: nothing scrolls sideways, no button, tab, badge or table header is cut
off, and the pinned frame takes less than a quarter of the screen.

**Why this priority**: Most students use phones; a broken frame in the default language would be seen on
every page.

**Independent Test**: Check every page in both languages and both themes at 375 px and on a desktop;
measure the pinned frame in Ukrainian at 360 × 640 and 375 × 667 on an administrator page and a teacher
page.

**Acceptance Scenarios**:

1. **Given** any page in Ukrainian or English, light or dark, **When** it is shown at 375 px or on a
   desktop, **Then** nothing scrolls sideways and no button, tab, badge or table header is cut off.
2. **Given** an administrator page and a teacher page in Ukrainian, with the longest role name, **When**
   the pinned frame is measured at 360 × 640 and 375 × 667, **Then** it is within the frame clearances
   (raised if needed) and under a quarter of a 375 × 667 screen, and the measurements are recorded in the
   UI guidelines.

---

### User Story 10 - An upgrade stops on names that now clash (Priority: P3)

Before upgrading, a deployment holds the institutions "Мар'янівський ліцей", with a straight apostrophe,
and "Мар’янівський ліцей", with a typographic one, in the same region (a hypothetical case: production holds no such
data). The upgrade stops with a message naming both, so an administrator renames one and upgrades again.

**Why this priority**: The new duplicate rule must not leave two names that the database would treat as
the same; the case is unlikely, since production holds no real data yet.

**Independent Test**: Run the upgrade on a database holding two names in the same scope that differ
only by apostrophe, in each kind of named record, and check that it stops, names both and changes
nothing; run it on a clean database and check that every key is recomputed.

**Acceptance Scenarios**:

1. **Given** two existing names in the same scope that now count as the same, **When** the upgrade runs,
   **Then** it stops before changing anything and names both records.
2. **Given** no such clash, **When** the upgrade runs, **Then** the stored duplicate-checking keys of
   subjects, regions, institutions, classes, teams and competitions are recomputed, and the names
   themselves are unchanged.
3. **Given** the upgrade is reversed, **When** the downgrade runs, **Then** the earlier keys and the
   earlier consent wordings are restored.

---

### User Story 11 - The documents and the gallery come first (Priority: P3)

Before any page uses the language switch, it is in the component library and in the component gallery,
closed and open, and the UI guidelines describe it, the glossary, the Ukrainian writing rules, the time
formats and the new checks. The product requirements gain a **Languages** section.

**Why this priority**: The constitution requires every new pattern in the library, the gallery and the
guidelines before it is used, and the binding documents must not contradict the application.

**Independent Test**: Read the updated documents and open the gallery.

**Acceptance Scenarios**:

1. **Given** the component gallery, **When** an administrator opens it outside production, **Then** it
   shows the language switch closed and open; its own sample content stays in English while its frame
   follows the chosen language.
2. **Given** the UI guidelines, **When** they are read, **Then** they describe the top bar with the
   switch, the switch component, times in both languages and the Kyiv-time fallback, the Ukrainian form
   of every wording pattern, the glossary and writing rules, the switch at phone width, a Languages
   section and the catalogue checks.
3. **Given** the product requirements, **When** they are read, **Then** a **Languages** section states
   the default language, the alternative, the bilingual consent and that entered content is never
   translated.

---

### User Story 12 - A developer adds or changes a message (Priority: P3)

A developer adds a button to a page. The README explains how to mark the new text, extract it, add the
Ukrainian translation and check it. If they forget the translation, or the Ukrainian translation uses a
different placeholder, the automated checks fail.

**Why this priority**: Every later milestone is written in both languages; the process must be written
down and enforced.

**Independent Test**: Follow the README to add a message; remove a translation, mark one as uncertain,
and change a placeholder, and check that the test suite fails each time.

**Acceptance Scenarios**:

1. **Given** the README, **When** a developer reads it, **Then** it says how to add or change a message
   and its translations.
2. **Given** a message in use with no Ukrainian or English translation, one marked as uncertain (fuzzy),
   or one whose placeholders differ between languages, **When** the tests run, **Then** they fail.
3. **Given** the built application image and the test run, **When** they start, **Then** the
   translations are compiled from the catalogues, so nobody commits compiled files by hand.

---

### Edge Cases

- **A stored choice of `ua`, `UK`, `en-GB`, an empty value or a very long value** means the default
  language; only `uk` and `en`, exactly, are languages.
- **Choosing the language that is already current** stores it again and returns to the page; nothing
  else happens.
- **Choosing Ukrainian in an environment whose default is English** (the test suite) stores `uk`, so
  the pages are Ukrainian: the choice is always stored, never deleted to mean the default.
- **A page reached by a link in an email** opens in the browser's chosen language, or Ukrainian when
  none was chosen; the email's language does not change the page's.
- **An invitation accepted in a browser with English chosen** records the same version 1 as one accepted
  in Ukrainian.
- **A sign-in code requested in Ukrainian and entered after switching to English** is accepted; the code
  has no language.
- **Two browsers of the same person** can hold different languages; nothing is linked to the account.
- **The data-deletion link is opened in another browser** than the one that asked for it: the page
  follows the language of the browser that opens it.
- **A name made only of Latin letters with an apostrophe** ("O'Brien", "O’Brien") follows the same
  apostrophe rules.
- **Names equal by the sort key** ("Іваненко" and "іваненко") keep their existing tie-break: the record
  that was created first comes first.
- **A name starting with a digit or punctuation** ("5-А", "«Зоря»") sorts before letters, in Unicode
  order, as today.
- **A list ordered by something else first** (competitions by start time) uses the Ukrainian order for
  its name tie-break.
- **A time at 00:05 or on the 1st of a month** reads "1 March 2027, 00:05": the day has no leading zero,
  the hour keeps two digits.
- **A date near midnight UTC** is shown on the date it has in the displayed zone.
- **The browser's own validation messages** (a required or email field checked before sending) follow
  the browser's language, not the switch.
- **A request the framework answers before the application** (a malformed request, an unhandled server
  error) keeps the framework's own response.
- **The component gallery** keeps its sample texts in English in both languages.
- **The status address** used by monitoring keeps its machine-readable response, untranslated.
- **A consent text with the "English" line in the Ukrainian part** cannot occur: the split is fixed by
  the published texts, which are pinned.
- **Production holds a consent record when 12.5 is deployed**: the milestone forbids this; 12.5 reaches
  production before the first real invitation is accepted (test acceptances by the product team are not
  real consent).

## Requirements *(mandatory)*

### Functional Requirements

#### Languages and the default

- **FR-001**: The application MUST offer two languages, Ukrainian and English, for every page and every
  email it writes.
- **FR-002**: The default language MUST be a deployment setting that accepts `uk` or `en`; when it is not
  set the default MUST be Ukrainian, and any other value MUST stop the application at startup with a
  message naming the setting, as other invalid settings do. The test configuration MUST set English,
  and the tests of the default MUST set Ukrainian.
- **FR-003**: The language of a request MUST be the browser's stored choice when it is exactly `uk` or
  `en`, and the default language otherwise. The browser's language preference (`Accept-Language`) MUST
  be ignored.
- **FR-004**: The language MUST be worked out once per request, and every page, fragment, message and
  email of that request MUST use the same one.
- **FR-005**: Every page MUST declare its language as `uk` or `en` on the whole document. The code for
  Ukrainian MUST be `uk` (ISO 639-1) wherever a language is named (the stored choice, the setting, the
  page's declared language, the translation folders); `ua`, Ukraine's country code, MUST NOT be used as
  a language code.

#### The language switch

- **FR-006**: The top bar of every page, signed in or signed out, including the sign-in, code entry,
  role choice, invitation, data-deletion and error pages, MUST hold the language switch, placed before
  the user menu where there is one.
- **FR-007**: The switch MUST look like a drop-down list: closed, it shows the current language's flag
  and name; open, it lists **Українська** with the Ukrainian flag and **English** with the United
  Kingdom flag, in that order, each name written and marked in its own language. The current language
  MUST be marked for assistive technology.
- **FR-008**: The switch MUST work without JavaScript, as a native disclosure with a small form, like the
  user menu.
- **FR-009**: The flags MUST be small images served by the application, named by the country's code
  (`ua` for Ukraine, `gb` for the United Kingdom) and hidden from assistive technology; flag emoji MUST
  NOT be used.
- **FR-010**: At phone width (below 768 px) the closed switch MUST show the flag alone, with the language
  name still available to screen readers. Every option MUST be a touch target of at least 44 by 44 px.
- **FR-011**: Choosing a language MUST be a form submission to the application's language address that
  stores the choice and returns the browser to the page it was on, now in the chosen language. It MUST
  pass the application's existing cross-site check.
- **FR-012**: The return address MUST be checked exactly as the theme switch checks it: only a plain
  local path of a page that can be opened directly is accepted; anything refused returns to the home
  page signed in, or the sign-in page signed out.
- **FR-013**: A submitted language other than `uk` or `en` MUST NOT be stored; the browser returns as in
  FR-012.

#### The stored choice

- **FR-014**: The choice MUST be kept in one browser cookie, `sc_lang`, holding `uk` or `en`, with the
  attributes of the theme cookie: available to the whole application (`Path=/`), `SameSite=Lax`, not
  readable by scripts (`HttpOnly`), `Secure` in production, and kept for one year.
- **FR-015**: Choosing a language MUST always store it, Ukrainian as well as English; the cookie MUST
  NOT be deleted to mean the default.
- **FR-016**: The cookie MUST hold only the choice. It MUST NOT be linked to an account or a session,
  MUST NOT be stored in the database, is not personal data, needs no consent, and MUST NOT be named in
  any log line.
- **FR-017**: Signing in, switching role and signing out MUST neither read nor change the choice.

#### What is translated

- **FR-018**: Everything the application writes on a page MUST be in the request's language: every
  page and component, heading, button, link, label, hint, placeholder, form error and error summary,
  notice, empty state, confirmation, refusal, menu entry, row note, badge, page navigation text, page
  title, hidden screen-reader text, accessible name and description, the status, role and access-level
  labels, the theme switch's options, the footer, counts and dates.
- **FR-019**: The application's name MUST be «Студентські змагання» in Ukrainian and "Student
  Competitions" in English, in the top bar, page titles and emails.
- **FR-020**: Every count MUST take its plural form from the translations for the request's language:
  Ukrainian has three forms (1 команда, 2–4 команди, 5–20 команд, 21 команда, 22 команди); no message
  may choose a form by comparing the number with 1.
- **FR-021**: Every message MUST be one whole sentence or label with named placeholders. No message may be
  assembled from translated pieces (a label plus "date", "Enter a " plus a field name, "as a " plus a
  role), since Ukrainian words change form with their grammatical case.
- **FR-022**: Messages raised by the application's rules (validation, refusals, duplicates) MUST be
  translated when the page is shown or the email is written, in the request's language; they MUST NOT
  be fixed in English when the application starts.
- **FR-023**: The English wording of a message MUST remain its identifier, so specifications keep
  quoting the interface in English.
- **FR-024**: Text meant for developers only (component contract errors, log lines, the status address's
  response) MUST stay in English.

#### What is not translated

- **FR-025**: Anything people enter MUST be shown as entered, in the language they wrote it: names of
  subjects, regions, institutions, classes, teams and competitions, people's names, questions, reference
  answers, answers and any other text a person types. The sample questions seeded by milestone 3 MUST
  stay as they are.
- **FR-026**: The web framework's own error texts MUST NOT be translated: the detail text of an HTTP
  error that the framework provides ("Not Found", "Method Not Allowed") is shown as it comes inside the
  application's error page, whose frame, heading and links are translated; the framework's response to
  a malformed request and its plain-text server error stay as they are.
- **FR-027**: The content of the component gallery (`/admin/components`) MUST stay in English, MUST NOT
  be in the translations, and MUST be left out of the translation completeness check; the frame around
  it follows the chosen language.
- **FR-028**: The email sender's name MUST stay as configured for the deployment.
- **FR-029**: Messages the browser itself shows before a form is sent follow the browser's language and
  are not part of the application's translations.

#### Ukrainian wording

- **FR-030**: A glossary in the UI guidelines MUST fix the Ukrainian word for every product term, and
  every page MUST use it. It MUST cover at least the application's name («Студентські змагання»), the
  three roles (**Адміністратор** for the administrator), «заклад освіти» for an educational institution,
  the statuses, the access levels, and the names of tabs and buttons.
- **FR-031**: Since participants come from schools and colleges, the Ukrainian words for the teacher and
  the student roles MUST fit both: «учень» and «вчитель» (school only) and «студент» and «викладач»
  (college only) MUST NOT be used for a role. The glossary proposes the words (for example «Педагог» and
  «Здобувач освіти») and the product owner approves them.
- **FR-032**: Ukrainian text MUST follow the plain-language rules of the UI guidelines, use the quotation
  marks «…» with „…“ for a quotation inside a quotation, use the apostrophe ʼ, and address the reader as
  «ви».
- **FR-033**: A name people entered MUST never be declined. A Ukrainian message MUST put it in quotation
  marks after a noun that takes the case the sentence needs («Видалити предмет «Фізика»?», «Назад до
  регіону «Київ»»), or, for a person's name, after a colon («Вилучити зі списку: Олена Коваленко?»).
- **FR-034**: A Ukrainian sentence about another person MUST NOT use any word that agrees with that
  person's gender: no past-tense verb, participle or adjective that changes with it ("X запрошує вас",
  not "X запросив вас"; «Запрошення надіслано», not «Запрошений»). The reader, addressed as «ви», takes
  the plural forms.

#### Times

- **FR-035**: Every time shown to people MUST have one format per language: "14 March 2027, 10:00" and
  «14 березня 2027, 10:00» (the day without a leading zero, the month in full, a 24-hour clock); a date
  alone MUST read "15 October 2026" and «15 жовтня 2026». Ukrainian month names MUST be in the genitive
  case, and month names MUST come from the translations, never from the server's locale.
- **FR-036**: On a page, a time MUST be shown in the browser's time zone when it is known, with no label.
  When it is not known, it MUST be shown in Kyiv time (Europe/Kyiv) and labelled "(Kyiv time)" or
  «(за київським часом)». This replaces milestone 12.1's fallback to UTC.
- **FR-037**: When the browser's zone is not known, a form MUST read the time entered as Kyiv time, and
  its hint MUST say "Time zone: Europe/Kyiv" in the chosen language.
- **FR-038**: The profile's consent records, the invitation page's expiry and the administrator's
  **Teachers** list MUST use the format and zones of FR-035 and FR-036 instead of the milestone 8 format
  ("2026-10-22 14:05 UTC", "2026-10-15").
- **FR-039**: Every time in an email MUST be in Kyiv time, labelled in the email's language.
- **FR-040**: Times MUST still be stored in UTC and converted on the server only for display (Principle
  VII); the machine-readable time of each displayed moment stays in UTC.

#### Emails

- **FR-041**: The sign-in code email and the data-deletion email MUST be written in the language of the
  request that asked for them: subject and text.
- **FR-042**: The invitation email MUST be written in Ukrainian followed by English, whatever language
  the inviter chose: a subject holding both, and a text holding the whole Ukrainian message, then the
  whole English message, each with the role, the details that will be stored, the link and the expiry.
- **FR-043**: Emails MUST keep every rule of milestones 4 and 8: plain text, the code never in the
  subject, no tracking, the link as given, nothing stored.

#### Consent texts

- **FR-044**: Version 1 of the teacher's and of the student's consent text MUST be rewritten in place as
  one bilingual text: the Ukrainian wording first, under the heading «Українською», then the English
  wording, under the heading "English"; each wording MUST include a sentence saying that the Ukrainian
  wording prevails if the two differ.
- **FR-045**: The English wording MUST be the currently published version 1 of that role, word for word,
  with only that sentence added. The Ukrainian wording MUST be its translation, is the binding one, and
  MUST be approved by the product owner before it is published; if the review changes its meaning, the
  English wording MUST be changed to match before publishing.
- **FR-046**: Nothing else about consent MUST change: no new version, no new stored field, no
  re-consent. A role still has one current text; a consent record still points to it; the profile still
  shows the accepted text.
- **FR-047**: The invitation page and the profile MUST show both wordings in that order, whatever the
  chosen language; the page around them follows the chosen language. The English part MUST be marked as
  English for assistive technology, found by its "English" heading line.
- **FR-048**: The check that pins every published consent text MUST accept these two rewrites and keep
  every earlier wording pinned as superseded. Rewrites MUST be numbered (the milestone 11.1 rewrite of
  the student text counts as rewrite 1), the highest number being the published text, and the check
  MUST allow exactly two rewrites of student version 1, one of teacher version 1 and none of any other
  version.
- **FR-049**: Reversing the upgrade MUST restore the earlier wordings: the teacher's original and the
  student's rewrite 1.
- **FR-050**: The review of the Ukrainian wording MUST NOT hold up the rest of the work: the upgrade
  starts with the draft wordings, and the pinned checksums are set last, once the wording is approved;
  the change is merged only after that.
- **FR-051**: This MUST be the last rewrite in place: milestone 12.5 reaches production before the first
  real invitation is accepted, and from then on any change to a consent text is a new version.

#### Names: order and duplicates

- **FR-052**: Every list ordered by a name MUST follow the Ukrainian alphabet, ignoring case, with Ґ
  after Г, Є after Е, and І and Ї after И, in both languages. Latin letters MUST keep their order and
  come before Cyrillic ones; any other letter (such as the Russian Ё, Ъ, Ы and Э) MUST come after the
  Ukrainian letters, in Unicode order. People are ordered by last name, then first name.
- **FR-053**: The order MUST be computed by the application when a list is sorted, the same on SQLite and
  PostgreSQL, and MUST NOT be stored. No sorting library is added.
- **FR-054**: The five apostrophe-like characters `'`, `’`, `ʼ`, `‘` and `` ` `` MUST be ignored when
  sorting, and MUST count as one and the same character when a name is checked for duplicates. Names
  MUST be stored exactly as typed.
- **FR-055**: The stored duplicate-checking keys of subjects, regions, institutions, classes, teams and
  competitions MUST be recomputed by the upgrade with the new apostrophe rule. If two existing names in
  the same scope would then be the same, the upgrade MUST stop before changing anything and name both
  records.
- **FR-056**: Every existing duplicate rule (its scope, case-insensitivity, live-only rules of teams and
  competitions, and its message) MUST otherwise stay as it is.

#### Layout

- **FR-057**: Every page MUST be checked in both languages and both themes, at 375 px and on a desktop:
  nothing scrolls sideways, and no button, tab, badge or table header is cut off.
- **FR-058**: The pinned frame MUST be measured again in Ukrainian at 360 × 640 and 375 × 667, with the
  longest role name, on an administrator page and on a teacher page; the frame clearances MUST be raised
  if the frame outgrew them, the frame MUST stay under a quarter of a 375 × 667 screen, and the new
  measurements MUST be recorded in the UI guidelines.

#### Translations process

- **FR-059**: Messages MUST be collected from the templates and the application code into one Ukrainian
  and one English catalogue, kept in the repository and updated by the documented extraction and merge
  steps.
- **FR-060**: The catalogues MUST be compiled when the application image is built and before the tests
  run; compiled files MUST NOT be committed.
- **FR-061**: The README MUST say how to add or change a message and its translations.

#### Documents and UI guidelines

- **FR-062**: The product requirements MUST gain a **Languages** section: Ukrainian is the default
  language of the interface, the consent texts and every other communication with users; English is the
  alternative, chosen per browser; the consent texts are bilingual and their Ukrainian wording prevails;
  what people enter is never translated; participants come from schools and colleges.
- **FR-063**: The UI guidelines MUST cover localisation: the top bar with the switch (Layout); the
  language switch component (Frame); times in both languages and the Kyiv-time fallback (Local time);
  the Ukrainian form of every wording pattern, the glossary and the writing rules (Wording patterns); the
  switch and the top bar at phone width (Phone behaviour); how a message is written, extracted and
  translated and that every page is checked in both languages (a new Languages section); and the
  translation checks (Checks). The theme switch stays in the user menu and under the sign-in form.
- **FR-064**: The language switch MUST be added to the component library, the component gallery (closed
  and open) and the UI guidelines before any page uses it.
- **FR-065**: The constitution v2.4.0 and the technical requirements already list the Localisation stack
  (gettext catalogues managed with Babel, through the template engine's translation extension). Babel
  MUST be the only new dependency.

#### Verification and scope

- **FR-066**: Automated tests MUST cover the acceptance scenarios of this specification and the
  milestone's _Test_ line: both catalogues translate every message in use outside the component gallery,
  none marked fuzzy, with the same placeholders; Ukrainian plural forms for 1, 2, 5, 11, 21, 22 and 25;
  genitive month names; every page in Ukrainian with `lang="uk"` when no language was chosen; the switch
  on every page, signed in and out, without JavaScript, storing the cookie with its attributes for both
  languages and returning to the page; refused return addresses; unknown cookie values; the default
  setting (unset, invalid); the Ukrainian order and the apostrophe duplicates; the time formats, the Kyiv
  fallback on pages and forms and in emails; the email languages; the bilingual consent texts, their
  pins, the numbered rewrites and the recorded version; and the English marking of the consent's
  English part.
- **FR-067**: The existing tests MUST keep running in English; only the tests of behaviour this
  milestone changes are updated: the invitation email, the format and zone of times on pages and in
  emails, the consent texts, the order of names, and the top bar with its new switch.
- **FR-068**: This milestone MUST NOT add anything listed under **Out of Scope** below.

### Key Entities *(include if feature involves data)*

- **Language choice** (new, browser only): `uk` or `en` in the `sc_lang` cookie of one browser. Not
  personal data, not linked to an account or a session, not in the database. Missing or anything else
  means the default language.
- **Default language** (new, deployment setting): `uk` or `en`; unset means `uk`.
- **Message catalogue** (new, in the repository): every message of the application with its Ukrainian
  and English translation and plural forms, compiled at build and test time.
- **Glossary** (new, in the UI guidelines): the Ukrainian word for every product term, approved by the
  product owner.
- **Consent text** (existing, milestone 8): version 1 of each role is rewritten in place as one bilingual
  text; earlier wordings stay pinned as superseded; rewrites are numbered.
- **Consent record** (existing, milestone 8): unchanged; it points to version 1, now bilingual.
- **Name duplicate key** (existing, milestones 6, 7, 9, 11.1, 12.1): the stored key of subjects, regions,
  institutions, classes, teams and competitions; now also treats the five apostrophes as one character.
- **Name order** (new, never stored): computed when a list is sorted; ignores case and apostrophes and
  follows the Ukrainian alphabet.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With no language chosen, 100% of pages of every role, and every error page, open in
  Ukrainian and declare the Ukrainian language, whatever the browser's language preference.
- **SC-002**: 100% of the messages the application uses outside the component gallery have a Ukrainian
  and an English translation, none uncertain, with the same placeholders.
- **SC-003**: A person changes the language from any page with 2 choices (open the switch, choose a
  language) and lands on the same page in 100% of the tested pages, with and without JavaScript.
- **SC-004**: The choice survives signing in, switching role and signing out in 100% of the tested
  cases, and an unknown stored value means the default in 100% of them.
- **SC-005**: 100% of the tested counts use the right Ukrainian plural form for 1, 2, 5, 11, 21, 22 and
  25, and 100% of Ukrainian dates use genitive month names.
- **SC-006**: 100% of the lists ordered by a name follow the Ukrainian alphabet in both languages, and
  100% of names that differ from an existing one only by an apostrophe variant are refused as
  duplicates.
- **SC-007**: 100% of times shown with no known zone, and 100% of times in emails, are in Kyiv time and
  labelled; 0 user-facing times or dates show UTC or the milestone 8 format.
- **SC-008**: 100% of sign-in and data-deletion emails are in the requesting browser's language, and
  100% of invitations hold both languages, Ukrainian first, in subject and text.
- **SC-009**: 100% of invitation pages and profiles show the consent text in Ukrainian then English,
  with the English part marked as English, and 100% of acceptances record version 1.
- **SC-010**: 0 user-entered texts are changed, translated or declined on any page or email.
- **SC-011**: Every page is usable at 360 px and 375 px width in both languages and both themes with no
  sideways scrolling, and the pinned frame stays under a quarter of a 375 × 667 screen in Ukrainian.
- **SC-012**: The product owner approves the glossary and the Ukrainian consent wordings, and completes
  the milestone's acceptance walk-through as an administrator, a teacher and a student in both languages
  without finding an untranslated text, a wrong term, a declined name or a gendered guess.
- **SC-013**: All tests from milestones 1–12.4 still pass in English, apart from those of the behaviour
  this milestone changes (FR-067).

## Assumptions

- **The role words are decided in the glossary.** The milestone fixes the constraint (FR-031) and the
  approval step, not the words; until approval the drafts «Педагог» and «Здобувач освіти» are used.
- **«Студентські змагання»** is the product owner's chosen name and fits the constraint of FR-031, which
  applies to the role words only.
- **The language switch on pages with no user menu** (signed out, error pages) sits at the end of the top
  bar, where the user menu would be.
- **The switch offers both languages always**, the current one marked; choosing it again is harmless.
- **The language address is public**, like the theme address, since the switch works signed out and for
  every role, and it reads and writes no data apart from the cookie.
- **Characters that are not letters** (spaces, digits, punctuation, other symbols) keep their Unicode
  order and come before all letters, as today; digits are not compared as numbers.
- **Ties after the name key** keep each list's existing tie-break (the record's id, so the earliest
  created comes first).
- **A list ordered by something else first** (competitions by start) uses the Ukrainian order for its
  name tie-break.
- **The duplicate key keeps its existing normalisation** (Unicode normalisation, then case folding) and
  maps the five apostrophes to one character; the sort key ignores them.
- **The Kyiv label** is "(Kyiv time)" in English and «(за київським часом)» in Ukrainian; the exact words
  are confirmed in the glossary.
- **The invitation's two parts** are separated by a clear line, and each part names the language it is
  in, so a reader finds theirs; the exact layout is decided in planning.
- **Emails sent with no browser request behind them** do not exist yet; if one is added later, it uses
  the default language.
- **The status address** (health and version) is a machine interface and is not translated.
- **Hidden fields and values sent by forms** (status filter values, zone names, ids) are not translated;
  only what people read is.
- **Time-zone names** in hints (Europe/Kyiv) are not translated.
- **The theme switch** keeps its place and behaviour; only its texts are translated.
- **Every quoted Ukrainian example** in this specification illustrates a rule; the final wording comes
  from the approved glossary and translations.
- **Production holds no real users** (product requirements, "Production usage"), so the in-place consent
  rewrite and the key recomputation disrupt nobody.

## Dependencies

- **Constitution v2.4.0** (amended on 2026-11-14): the **Localisation** row of the Technology Stack;
  Principle II (component library, gallery and guidelines first; no build step), Principle III (tests,
  fakes for email), Principle IV (unchanged access rules on every page in both languages), Principle V
  (cross-site check, cookie and log rules), Principle VII (UTC storage, both database engines,
  migrations).
- **Product requirements**: "Personal data" (consent), "Production usage" (no real users yet); gains a
  **Languages** section with this milestone.
- **Technical requirements**: the Localisation row.
- **Milestone 3**: the sample questions, which stay untranslated.
- **Milestone 4**: the sign-in code email and its rules.
- **Milestones 6, 7, 9, 11.1, 12.1**: the named records and their duplicate rules.
- **Milestone 8**: consent texts, their pins, invitations, the data-deletion email and the profile.
- **Milestone 10 and 10.1**: the frame, the user menu, the theme switch and its return-address check,
  the component gallery, the UI guidelines, the pinned frame and its clearances.
- **Milestone 11.1**: the precedent of rewriting student consent version 1 in place.
- **Milestone 12.1**: local times, the browser's time-zone cookie and its UTC fallback, replaced here by
  Kyiv time.
- **Later milestones that depend on this one**: every later milestone (13 onward) writes its pages and
  emails in both languages; milestone 14 evaluates mostly Ukrainian answers.

## Out of Scope

- Languages other than Ukrainian and English, and right-to-left scripts.
- Choosing the language from the browser's language preference or from the person's location.
- Storing the language per account, or sending a person's emails in a language stored for them.
- Translating anything people enter, machine translation, or transliteration of names.
- Translating the component gallery's content, the email sender's name, the browser's own validation
  messages, the web framework's own error texts, log lines or the status address's response.
- Inflecting names people entered, or choosing words by a person's gender.
- A new consent version, re-consent, or storing which language a person read the consent in.
- Natural ordering of numbers inside names, or a configurable sort order.
- Searching or filtering by name.
- Localised number formats beyond whole numbers.
- Choosing a time zone in the application, or showing several zones at once.
- Text generated by the LLM evaluation (milestone 14).
- The student's competition pages (milestone 13).
