# Research: Ukrainian Localisation (Milestone 12.5)

Each decision lists what was chosen, why, and the alternatives rejected. Section numbers (R1–R18)
are referenced from [plan.md](./plan.md), [data-model.md](./data-model.md) and the
[contracts](./contracts/).

## R1. How a request gets its language

**Decision**: A pure ASGI middleware, `LanguageMiddleware` in `app/core/i18n.py`, runs around the
whole application (outside FastAPI's exception middleware). For each HTTP request it reads the
`sc_lang` cookie from the request headers, picks `uk` or `en` (exactly; anything else is the
default, `app.state.default_language`), stores the code in `scope["state"]["language"]` and sets a
`ContextVar` holding that language's loaded `Translations`. Every translation call (templates,
lazy messages, email builders) reads that `ContextVar`.

**Rationale**:

- One decision per request (FR-004): the middleware runs once, before routing, so templates, the
  `resolve_access` dependency, routers, services and the exception handlers all see the same
  language.
- It covers pages no route matched (404, 405) and the exception handlers, which the app-wide
  `resolve_access` dependency does not reach.
- A `ContextVar` set before the endpoint is copied into the thread pool that runs sync endpoints
  (`run_in_threadpool` copies the context), so sync routes and services see it with no argument
  threading.
- `Accept-Language` is never read (FR-003).

**Alternatives considered**:

- A FastAPI dependency: does not run for unmatched routes or exception handlers.
- Passing `language` explicitly through every service and template: hundreds of signatures change
  for no gain.
- `BaseHTTPMiddleware`: works, but adds a task boundary and is discouraged for new code; a pure
  ASGI middleware is twelve lines.

## R2. Translation runtime: gettext catalogues with Babel

**Decision**: GNU gettext catalogues (`.po` sources, compiled `.mo`), loaded at startup with
`babel.support.Translations.load(LOCALE_DIR, [code], domain="messages")`, one object per
language, kept in a module-level mapping. Jinja2's `jinja2.ext.i18n` extension is added to the
shared environment and given **new-style** callables (`install_gettext_callables(gettext,
ngettext, newstyle=True, pgettext=..., npgettext=...)`) that look up the `ContextVar`.

**Rationale**:

- The constitution v2.4.0 Localisation row names exactly this stack; Babel is the only new
  dependency (FR-065).
- New-style gettext in Jinja formats with named `%(name)s` parameters and escapes them under
  autoescape, so a translated message cannot inject markup, and a parameter that is already markup
  (a `local_time(...)` macro call) stays markup.
- Plural rules come from each catalogue's `Plural-Forms` header, so Ukrainian's three forms are
  data, not code (FR-020).
- Contexts (`pgettext`) separate English words with two Ukrainian translations (the access level
  **Read** and other uses of "read"; month names in the genitive).

**Notes**:

- New-style gettext always applies `%` formatting: a literal `%` in a message is written `%%`.
- Babel is a **runtime** dependency, not a development one: the image's runtime stage runs
  `pybabel compile`, and `babel.support.Translations` loads the result.

**Alternatives considered**:

- Python's `gettext` module alone, with no Babel: no extraction from Jinja templates, no catalogue
  tooling; rejected by the milestone.
- Babel's CLDR date formatting (`format_datetime(..., locale="uk")`): gives genitive months but
  adds " р." and follows CLDR's pattern, not the guidelines' "14 березня 2027, 10:00"; the milestone
  puts month names in the catalogue (FR-035).
- Fluent, or a hand-written dictionary: not the approved stack.

## R3. Lazy messages in Python code

**Decision**: Python code never holds a translated string. It holds a **`Text`** value
(`app/core/i18n.py`), created by three functions that are also the extraction keywords:

- `_(msgid, **params)` — a message;
- `_n(singular, plural, n, **params)` — a counted message; `n` is also available as `%(num)d`;
- `_p(context, msgid, **params)` — a message with a context.

A `Text` is immutable and translates itself when it is turned into a string — `str(text)` — in the
language of the current `ContextVar`. Parameters are formatted after translation; a parameter that
is itself a `Text` is translated in the same language; any other parameter (a name people entered)
is inserted unchanged. `Text` supports `==` with a `str` or another `Text` (comparing their
current renderings) and `hash`, so existing tests that compare a message with its English wording
keep passing.

Module-level constants (`NAME_REQUIRED = _("Enter a name.")`) are therefore safe: they are
translated when shown, never when the module is imported (FR-022). Exceptions keep their `message`
attribute, now a `Text`. Templates print `{{ error }}`: Jinja calls `str()`, which translates, then
escapes.

**Rationale**:

- Matches the milestone's rule exactly ("message identifiers with named parameters, translated when
  the page is rendered or the email is written").
- No service or router signature changes: a `Text` goes wherever a `str` message went.
- Outside any request (unit tests, scripts), the `ContextVar`'s default is an empty
  `NullTranslations`, which returns the English message identifier, and English plural rules.

**Alternatives considered**:

- Babel's `LazyProxy`: proxies every string method, hides the identifier and parameters, and
  makes equality and debugging opaque.
- Translating eagerly inside services with the request language: works only inside requests and
  fails the "never fixed when imported" rule for constants.
- Message codes mapped to texts in templates: doubles every message and loses the English wording
  as identifier (FR-023).

## R4. Writing messages: whole sentences, named placeholders

**Decision**: Every message is one whole sentence or label with `%(name)s` placeholders. The
existing places that build a message from pieces are rewritten as whole messages (inventory from
the code):

| Where | Today | After |
|---|---|---|
| `components/form.html` date-time field | `legend ~ " date"`, `legend ~ " time"`, `"Time zone: " ~ zone_label` | the caller passes `date_label`, `time_label` as whole messages; the hint is `_("Time zone: %(zone)s", zone=…)` |
| `schemas/people.py` `clean_person_name(raw, "last name")` | messages built with the field name | one message set per field (first name, last name), selected by a field key |
| `services/email.py` invitation | `"as a " + role.lower()` | one subject and one opening sentence per role |
| `routers/invitations.py:89` | `f"You are already a {label.lower()}."` | one message per role |
| `components/group.html` | `"team" if total == 1 else "teams"` | `_n("%(num)d team", "%(num)d teams", total)` |
| `competition_grades.html`, `team_answers_read_only.html` | `"team"/"answer" if … == 1` | `_n(…)` |
| `admin/institution_delete.html` | `{% if classes == 1 %}…{% elif %}` | one `_n` message |
| `routers/teacher_competition_entries.py:368` | `f"Change the {kind} of …"` | one message per kind (questions, teams) |
| `services/teachers.py:103` detail lines | `f"{label} — {level.label}"` | `_("%(institution)s — %(level)s", …)` with `level` a `Text` |
| every `f"…“{name}”…"` in routers (55 sites) | f-strings | `_("…“%(name)s”…", name=…)` |

Ukrainian translations follow FR-033: a name stays in the nominative after a noun in the needed
case. The English identifier keeps today's wording, so `«Видалити предмет «%(name)s»?»` translates
`Delete “%(name)s”?`. Where the English identifier lacks the noun the Ukrainian sentence needs, the
identifier gets a context (`_p("subject", "Delete “%(name)s”?")`), so each kind of record has its
own translation.

**Rationale**: Ukrainian nouns and adjectives change with case, number and gender; only whole
sentences can be translated correctly (FR-021).

**Alternatives considered**: translating fragments and joining them, which is what the milestone
forbids.

## R5. The catalogues and their tooling

**Decision**:

- **Files**: `app/locale/uk/LC_MESSAGES/messages.po` and `app/locale/en/LC_MESSAGES/messages.po`,
  committed; the template `app/locale/messages.pot` is committed too, so a review shows what
  changed. Compiled `messages.mo` files are git-ignored (FR-060).
- **Mapping** `babel.cfg` at the repository root: `[ignore: app/templates/pages/admin/components.html]`
  and `[ignore: app/routers/admin_components.py]` first (the gallery's content stays English,
  FR-027), then `[python: app/**.py]` and `[jinja2: app/templates/**.html]` with
  `extensions=jinja2.ext.i18n` and `silent=false`.
- **Keywords**: `_`, `_n:1,2`, `_p:1c,2` for Python; Jinja's `_`, `gettext`, `ngettext`,
  `pgettext`, `npgettext` for templates.
- **`scripts/translations.sh`** with three commands:
  - `update` — `pybabel extract` to the `.pot`, `pybabel update` into both `.po` files, then
    `scripts/fill_english_catalogue.py`, which copies each English identifier into an empty English
    translation (and the plural identifier into the second plural form), so English needs no manual
    work unless its wording deliberately differs;
  - `compile` — `pybabel compile` both catalogues;
  - `check` — runs the catalogue test alone.
- **Compiling**: the image's runtime stage runs `pybabel compile -d app/locale -D messages` after
  copying `app/` (Babel is in the virtualenv); `tests/conftest.py` compiles both catalogues into
  `app/locale` in `pytest_sessionstart`, through Babel's Python API, so `uv run pytest` works on a
  fresh clone.
- **Startup**: loading a catalogue that was not compiled stops the application with "Translations
  are not compiled: run scripts/translations.sh compile" (FR-060), never silently showing message
  identifiers.

**Rationale**: the standard gettext workflow, run with the project's own tools (`uv run`), and
reviewable in pull requests.

**Alternatives considered**:

- Committing `.mo` files: binary diffs, and they drift from the `.po`.
- Compiling at application startup from `.po`: works, but the milestone asks for a build-time step
  and it slows every start.
- A Makefile: the project has no make; `scripts/` already holds shell scripts.

## R6. The default-language setting

**Decision**: `app/core/config.py` gains `resolve_default_language(environ) -> Language`, reading
`DEFAULT_LANGUAGE`: unset or empty → `uk`; `uk` or `en` exactly → that language; anything else →
`LanguageConfigError("DEFAULT_LANGUAGE must be uk or en")` (the message names the setting, not the
value). The lifespan resolves it next to the other settings, before the database, and stores it on
`app.state.default_language`. `tests/conftest.py`'s `_isolate_environment` sets
`DEFAULT_LANGUAGE=en`; the tests of the default set `uk` (FR-002).

**Rationale**: production needs no configuration; the existing tests keep reading English
(FR-067); a typo in a deployment refuses to start instead of silently showing English.

**Alternatives considered**: a fixed Ukrainian default with every test client sending
`sc_lang=en` — any test that forgets the cookie would silently run in Ukrainian.

## R7. The language cookie and `POST /language`

**Decision**: `app/core/i18n.py` mirrors `app/core/theme.py`: `Language(StrEnum)` (`uk`, `en`),
`LANGUAGE_COOKIE_NAME = "sc_lang"`, `parse_language(value) -> Language | None` (exact match only),
`apply_language(response, language, *, secure)` setting the cookie with `max_age` one year,
`path="/"`, `httponly=True`, `samesite="lax"`, `secure` = production. The cookie is always set,
never deleted (FR-015).

`app/routers/language.py` serves `POST /language` (form fields `language`, `next`). The return
address logic of `POST /theme` (`safe_return_path`, then the route-table check `_has_get_page`,
then `/` or `/login`) moves to `app/core/return_path.py` as `resolve_return(request, raw)`, and both
routers call it (FR-012). An unknown `language` value stores nothing and still redirects (FR-013).
Both routes stay public and pass the application-wide cross-site check (FR-011).

The template context processor `_theme` becomes `_page_context`, providing `theme`, `language`
(the request's code) and `return_path` (today's `theme_return`), so both switches read the same
return address.

**Rationale**: the theme switch is the proven pattern for a public, script-free, cookie-only
choice; sharing the return-address check keeps both identical (FR-012).

**Alternatives considered**: a `GET /language?set=en` link — a state change on `GET` and outside
the cross-site check.

## R8. The language switch component

**Decision**: a new macro `language_switch(current, return_to)` in `components/frame.html`, called
by `top_bar()` on every page, before `user_menu()` when there is one, at the end of the bar
otherwise (FR-006). Markup ([contracts/components.md](./contracts/components.md)):

- `<details class="language-switch">` whose `<summary>` holds the current flag (`<img alt="">`),
  a visually hidden "Language" label, and the current name in a `<span lang="…">`, hidden visually
  below 768 px but kept for screen readers (FR-010);
- its panel is one `<form method="post" action="/language">` with a hidden `next` and two
  `<button name="language" value="uk|en" lang="uk|en">` each holding a flag and the name in its own
  language; the current one carries `aria-current="true"` (FR-007).
- Flags are `app/static/img/flag-ua.svg` and `flag-gb.svg` (FR-009): simple flat SVGs (two bands;
  the Union Flag simplified), with `alt=""`, sized by a CSS token, never emoji.
- CSS in the Components section of `app.css`, tokens only: the summary styled like a select (a
  border and a chevron drawn with existing tokens), options as 44 px rows (`--sc-touch-target`),
  the panel positioned under the switch like the user menu's.
- The gallery (`/admin/components#language`) shows it closed and open (FR-064).

**Rationale**: the same native `<details>` + form pattern as the user menu, so it works without
JavaScript (FR-008) and inherits the menu's keyboard and phone behaviour.

**Alternatives considered**: a `<select>` with an auto-submit script — needs JavaScript; two plain
links "UA | EN" — rejected by the milestone's design (flag and name, combobox look).

## R9. Times: one format, Kyiv as the fallback

**Decision**: `app/core/time_zone.py` changes:

- `KYIV = ZoneInfo("Europe/Kyiv")`; `UTC_ZONE` stays for storage helpers.
- `format_local_time(moment, zone)` → in `zone` with no label when it is known; in `KYIV` with the
  label when it is `None`. The pattern and the label are catalogue messages:
  `_("%(day)d %(month)s %(year)d, %(time)s")` and `_("%(moment)s (Kyiv time)")`; the month is
  `_p("genitive month", "March")` etc. (twelve messages; English translations are the plain names,
  Ukrainian the genitive forms «січня» … «грудня»), never `%B` (FR-035).
- `format_local_date(moment, zone)` → `_("%(day)d %(month)s %(year)d")`, no label (a date alone).
- `zone_name(None)` → `"Europe/Kyiv"`; the competition form's hidden zone and its hint use it, so a
  time entered with no known zone is read as Kyiv time (FR-037). The parsing side already converts
  with the submitted zone name.
- The `utc` Jinja filter (milestone 8) is removed; its three uses (profile, invitation page,
  **Teachers** list) use `local_time` and a new `local_date` macro (FR-038).
- `services/email.py`'s `format_utc` is removed; emails call `format_local_time(moment, None)`, so
  every email time is Kyiv time, labelled in the email's language (FR-039).
- The `<time datetime="…Z">` attribute stays UTC (FR-040).

**Rationale**: one formatter for pages and emails; daylight saving is handled by `zoneinfo`; the
browser-zone behaviour of 12.1 is unchanged when the zone is known.

**Alternatives considered**: keeping UTC for emails — rejected by the product owner.

## R10. Emails

**Decision**:

- `login_code_message` and `deletion_message` build their subject and text from `Text` values and
  `str()` them at build time, which happens inside the request, so they come out in the request's
  language (FR-041). Their callers (`services/login.py`, `services/data_deletion.py`) do not change.
- `invitation_message` renders its body twice, under `use_language(Language.UK)` and
  `use_language(Language.EN)` (a context manager that sets the `ContextVar` temporarily), and joins
  them: the Ukrainian text, a separator line (`———`), the English text. The subject is
  `f"{uk_subject} / {en_subject}"` (FR-042). Its inputs become values that render in either
  language: `role` (a `Role`, not a label), and the detail lines as `Text` values.
- The inviter is named in the present tense in both languages ("%(inviter)s запрошує вас …")
  (FR-034).

**Rationale**: the same builders and the same catalogue; no second set of email templates.

**Alternatives considered**: Jinja templates for emails — would be new infrastructure for three
plain-text messages.

## R11. The bilingual consent texts

**Decision**:

- **Migration** `<rev>_bilingual_consent_and_name_keys.py` (one revision with R12) defines
  `TEACHER_CONSENT_TEXT_V1_REWRITE_1` and `STUDENT_CONSENT_TEXT_V1_REWRITE_2`, each:
  `«Українською»`, the Ukrainian paragraphs, `"English"`, the English paragraphs (today's
  published wording plus one sentence), paragraphs separated by blank lines. `upgrade` updates the
  two rows in place (as the teams migration does); `downgrade` writes back the teacher's original
  and the student's rewrite 1, from private copies in the module (FR-049).
- **Pin test** (`tests/unit/test_consent_texts.py`) generalises to numbered rewrites: the pattern
  `<ROLE>_CONSENT_TEXT_V<n>_REWRITE(_<k>)?`, where the teams migration's unnumbered constant is
  rewrite 1; `published_texts()` takes the highest number; `SUPERSEDED` maps each version to the list
  of every earlier wording's hash; `REWRITES_ALLOWED = {("student", 1): 2, ("teacher", 1): 1}`
  (FR-048). The downgrade copies are checked against the superseded hashes, as today.
- **The English sentence** added to each wording: "If the Ukrainian and English wordings differ, the
  Ukrainian wording prevails." and its Ukrainian translation in the Ukrainian part.
- **Rendering**: `services/consent.py` gains `consent_parts(text) -> ConsentParts(ukrainian,
  english)`: the paragraphs before and after the paragraph that is exactly `English`, dropping the
  two heading paragraphs. The invitation page and the profile render each part under its heading
  (`h3`), the English part inside `<div lang="en">` and the Ukrainian inside `<div lang="uk">`
  (FR-047). A text with no `English` paragraph (impossible once migrated) renders whole, in the
  page's language.
- **Approval** (FR-050): the Ukrainian wording is drafted in the first implementation task and sent
  to the product owner; the migration carries the draft; the two `PUBLISHED` hashes are updated in
  the last task, after approval; the pull request is merged only then.

**Rationale**: no schema change (FR-046); the same in-place precedent as milestone 11.1; the pins
keep every wording that ever existed unchangeable.

**Alternatives considered**: two columns or two rows per version — the milestone forbids new
columns and versions.

## R12. Names: duplicate keys and the Ukrainian order

**Decision**:

- **Duplicate key** (`app/schemas/names.py`): `name_key(name) = fold_apostrophes(NFC(name).casefold())`,
  where `fold_apostrophes` maps `'` (U+0027), `’` (U+2019), `ʼ` (U+02BC), `‘` (U+2018) and `` ` ``
  (U+0060) to `ʼ` (FR-054). Everything else is unchanged (scopes, live-only indexes, messages;
  FR-056). `subject_name_key` stays an alias.
- **Sort key** (`app/schemas/names.py`): `name_sort_key(name) -> tuple[tuple[int, int], ...]`, over
  `NFC(name).casefold()` with the five apostrophes removed; each character becomes:
  - `(0, code point)` — not a letter (spaces, digits, punctuation, symbols);
  - `(1, code point)` — a Latin letter (`unicodedata.name` starts with `LATIN`);
  - `(2, rank)` — a letter of the Ukrainian alphabet, ranked а б в г ґ д е є ж з и і ї й к л м н о п
    р с т у ф х ц ч ш щ ь ю я (33 letters);
  - `(3, code point)` — any other letter (Ё, Ъ, Ы, Э, Greek…).
  
  So Latin names come first in their existing order, Ukrainian names follow the alphabet, other
  letters come after (FR-052). Not stored (FR-053); no library.
- **People**: `person_sort_key(last, first) = (name_sort_key(last), name_sort_key(first))`.
- **Sites** (R13) use `(name_sort_key(name), id)` instead of `(name_key, id)` or `.casefold()`.

**Migration** (same revision as R11): for subjects, regions, institutions, classes, teams and
competitions, read `(id, scope, name, live)`, compute the new key with a **private copy** of
`name_key` in the migration module (migrations never import `app`), and group by scope
(none; none; `region_id`; `institution_id`; live teams; live competitions per `subject_id`). If a
group holds two rows with the same new key, raise `RuntimeError` naming the table, both ids and both
names, before any update (FR-055). Otherwise update every changed key. `downgrade` recomputes the
old key (`NFC + casefold`) with its own private copy; it cannot clash, since the old key is finer.
A unit test asserts the migration's copy equals `app.schemas.names.name_key` on a set of samples,
like the consent downgrade test.

**Rationale**: the uniqueness constraints are enforced by the database on stored keys, so the keys
must be recomputed; checking clashes first gives the administrator a readable message instead of an
integrity error halfway through.

**Alternatives considered**:

- Storing a sort key column: no list is paged by the database (R13), so YAGNI.
- PyICU or `locale.strxfrm` with `uk_UA`: a second dependency, or a process locale that differs
  between the image and developers' machines.

## R13. Every list ordered by a name

**Decision**: the sorting sites found in the code switch to `name_sort_key` / `person_sort_key`:

| Module | List |
|---|---|
| `services/subjects.py:64,71`; `services/competitions.py:284` | subjects; deactivated subjects |
| `services/regions.py:65,72`; `services/teacher_access.py:140` | regions; a teacher's regions |
| `services/institutions.py:110,149`; `routers/admin_teachers.py:141`; `services/teachers.py:239` | institutions, "Name (Region)" choices, a teacher's institution links: by `(name, region)` keys, not the joined label |
| `services/teacher_access.py:132` | institutions within regions |
| `services/classes.py:89` | classes |
| `services/teachers.py:263` | teachers |
| `services/students.py:173` | students of a class |
| `services/teams.py:155,179,237` | teams; team members |
| `services/competition_entries.py:255,424` | region boxes and teams of a competition |
| `services/competitions.py:224` (`sort_key`) | the name tie-break after the start |
| `services/teachers.py:103` | the teacher's detail lines: by the institution's keys, not the translated text |

`tests/unit/test_name_order.py` sorts a fixed list through each service's public listing (or its
key) and asserts the order; a grep-style test asserts no `.casefold()` sort key remains in
`app/services` and `app/routers` (the stored duplicate key aside).

**Rationale**: "every list ordered by a name" (FR-052) needs an inventory, and a guard so a later
milestone does not reintroduce code-point order.

## R14. The glossary (draft for the product owner)

**Decision**: the UI guidelines get a glossary table, drafted as below and approved by the product
owner before acceptance (FR-030, FR-031). Drafts, to be confirmed:

| English | Ukrainian |
|---|---|
| Student Competitions | Студентські змагання |
| Administrator | Адміністратор |
| Teacher (role) | Педагог |
| Student (role) | Здобувач освіти |
| educational institution | заклад освіти |
| region | регіон |
| subject | предмет |
| class | клас / група — **to decide**: «клас» for schools, «група» for colleges; draft «клас» |
| team | команда |
| question bank | банк питань |
| reference answer | еталонна відповідь |
| competition | змагання |
| Upcoming / In progress / Finished / Cancelled | Заплановано / Триває / Завершено / Скасовано |
| Active / Deactivated | Активний / Деактивовано |
| Read / Write (access) | Перегляд / Редагування |
| Can manage competitions | Може керувати змаганнями |
| Students / Teams / Questions / Competitions (tabs) | Учасники / Команди / Питання / Змагання |
| Teachers / Educational institutions / Subjects (tabs) | Педагоги / Заклади освіти / Предмети |
| Grades, Score | Оцінки, Бал |
| Sign in / Log out | Увійти / Вийти |
| Profile | Профіль |
| Withdraw consent / Delete my data | Відкликати згоду / Видалити мої дані |
| Kyiv time | за київським часом |

The tab "Students" uses «Учасники» (participants) on purpose: it fits school and college and is
short. Status words are chosen to avoid gender agreement where possible (impersonal forms).

**Rationale**: terms fixed once are used everywhere; impersonal forms satisfy FR-034.

## R15. Layout and the pinned frame

**Decision**: the top bar keeps one row on a desktop. Below 768 px the switch folds to its flag
(R8). The longest strings to check: «Студентські змагання», «Адміністратор», the teacher tabs
«Учасники · Команди · Питання · Змагання», the administrator tabs «Педагоги · Заклади освіти ·
Предмети». If the frame at 360 × 640 or 375 × 667 exceeds `--sc-frame-clearance` /
`--sc-frame-clearance-tabs` or a quarter of 667 px (166.75 px), the clearance tokens are raised
first; if the frame still passes a quarter of the screen, the wordmark gives way: below 768 px it is
visually hidden when a role is shown, and the logo link keeps the application's name as its
accessible name. The measurement is recorded in `ui-guidelines.md` §4 (FR-058).

**Rationale**: the frame rules of milestone 10.1 already require re-measuring after a longer tab or
a taller top bar; the wordmark is the only part that repeats information (the logo links home).

## R16. Error pages and framework texts

**Decision**: the application's own error texts (`Access denied`, `Request refused`, the 403
sentences in `app/main.py`, `pages/error.html`, the not-found pages) become messages. For a plain
`HTTPException`, the page shows a translated heading by status code (`_("Page not found")` for
404, `_("This address does not accept that request")` for 405, a generic heading otherwise) and the
framework's `detail` text as it comes (FR-026). The JSON response to a malformed request and the
plain-text server error are untouched.

## R17. Tests

**Decision**:

- **`tests/unit/test_catalogues.py`** (new): extracts messages with Babel's Python API and the
  project's `babel.cfg` and keywords; reads both `.po` files; asserts every extracted message is in
  both catalogues, translated (every plural form), not fuzzy, and with the same set of placeholders
  as its identifier (named `%(x)s`, `%(num)d`); asserts no catalogue message is obsolete; asserts the
  gallery's files are not in the extraction.
- **`tests/unit/test_template_text.py`** (new): parses every template except the gallery with Jinja's
  lexer; in each raw-text token, strips HTML tags, and fails on Latin letters left in text content or
  in the `aria-label`, `title`, `alt` and `placeholder` attribute values — so untranslated literals in
  templates are caught. Allow-list: none expected beyond `<!doctype html>`.
- **`tests/unit/test_i18n.py`** (new): `Text` translation, equality, nested parameters, user values
  untouched; Ukrainian plural forms for 1, 2, 5, 11, 21, 22, 25; genitive months; `parse_language`;
  `resolve_default_language` (unset, `uk`, `en`, invalid).
- **`tests/unit/test_name_order.py`** (new): the alphabet order example, Latin first, Russian letters
  after, digits and punctuation first, apostrophes ignored; `name_key` folding; the guard of R13.
- **`tests/integration/test_language.py`** (new): `POST /language` (each language, query kept,
  refused targets, unknown value, cross-site refusal, cookie attributes incl. `uk` stored), the
  switch on every kind of page signed in and out, `lang="uk"` by default with the setting `uk` over
  the route sweep of `test_routes.py`, the choice kept through sign-in, role switch and sign-out.
- **`tests/integration/test_localised_emails.py`** (new): sign-in code and deletion in each language;
  invitation bilingual subject and body for both roles; Kyiv time labelled.
- **`tests/integration/test_bilingual_consent.py`** (new): both wordings in order with `lang`
  marking on the invitation page and the profile in either language; acceptance records version 1.
- **Updated**: `test_consent_texts.py` (numbered rewrites, R11), `test_migrations.py` (the new
  revision: keys recomputed, clash stops, downgrade restores), `test_email.py`,
  `test_teacher_invitation.py`, `test_student_invitation.py` (bilingual email, times),
  `test_time_zone*.py` and competitions tests that expect the UTC fallback, tests of name order,
  `test_layout.py` and `test_page_patterns.py` (the switch in the top bar), `test_component_gallery.py`
  (the switch section), `test_stylesheet.py` (new classes), `tests/conftest.py`
  (`DEFAULT_LANGUAGE=en`, compiling catalogues at session start).
- **By hand** ([quickstart.md](./quickstart.md)): the layout in both languages and themes, the frame
  measurement, the product owner's walk-through.

## R18. Documents

**Decision**: in this pull request, `docs/requirements/product-requirements.md` gains **Languages**
(FR-062); `docs/requirements/ui-guidelines.md` changes §4 Layout, §5 Frame and Local time, §7
Wording patterns (Ukrainian forms, glossary, writing rules), §8 Phone behaviour, a new **Languages**
section and §10 Checks (FR-063); the README gains "Translations" (FR-061); `.gitignore` gains
`app/locale/*/LC_MESSAGES/*.mo`. The constitution (v2.4.0) and the technical requirements already
list the stack. `milestones.md` is compacted into **Delivered** on delivery.
