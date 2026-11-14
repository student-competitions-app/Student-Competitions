# Implementation Plan: Ukrainian Localisation (Milestone 12.5)

**Branch**: `012.5-ukrainian-localisation` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012.5-ukrainian-localisation/spec.md`

## Summary

The whole application becomes bilingual, Ukrainian by default and English on request, before the
student's side is built. Every page and email speaks the browser's chosen language; names sort in
the Ukrainian alphabet; times fall back to Kyiv time; the consent texts become bilingual.

**How a request gets its language** (research R1, R2, R7, [contracts/i18n.md](./contracts/i18n.md)):

- A pure ASGI `LanguageMiddleware` reads the `sc_lang` cookie (`uk`/`en` exactly, else the
  `DEFAULT_LANGUAGE` setting, `uk` when unset) once per request and sets a `ContextVar` holding that
  language's gettext `Translations`.
- Jinja's `jinja2.ext.i18n` gets new-style callables that read the `ContextVar`; `<html lang>`
  follows it.
- **`POST /language`** stores the choice (always, `uk` too) with the theme cookie's attributes and
  returns to the page through the theme switch's return-address check, moved to
  `app/core/return_path.py` and shared.

**How Python code holds text** (R3, R4): a lazy **`Text`** value (`_`, `_n`, `_p`) that translates
itself on `str()`, so module constants, exceptions' messages and enum labels are translated when a
page is rendered or an email written, never at import. The 55 f-string messages and the assembled
ones (form legend + "date", person field names, `role.lower()`, hand-made plurals) become whole
messages with named placeholders.

**Catalogues** (R5): `app/locale/{uk,en}/LC_MESSAGES/messages.po` (+ `.pot`) from `babel.cfg`
(the gallery ignored); `scripts/translations.sh update|compile|check`; compiled in the image's
runtime stage and in `pytest_sessionstart`; an uncompiled catalogue stops the start.

**Times** (R9): `format_local_time` falls back to `Europe/Kyiv`, labelled "(Kyiv time)" / «(за
київським часом)»; month names are `_p("genitive month", …)`; a new `local_date`; the milestone 8
`utc` filter and `format_utc` are retired; emails always use Kyiv time.

**Emails** (R10): the sign-in code and deletion email in the request's language; the invitation
rendered twice under `use_language` and joined, Ukrainian first, subject "uk / en".

**Consent** (R11): one data migration rewrites version 1 of both roles in place as «Українською» +
"English" parts; the pin test moves to numbered rewrites (`student v1: 2`, `teacher v1: 1`); the
invitation page and profile render the parts with `lang` marking. The Ukrainian wording is drafted
first and approved by the product owner; its hashes are pinned last.

**Names** (R12, R13): `name_key` folds the five apostrophes to `ʼ`; a new `name_sort_key` ranks the
Ukrainian alphabet (Latin first, other letters after) and replaces every `.casefold()`/`name_key`
sort; the same migration recomputes the stored keys of six tables after a clash check.

**Interface** (R8, R14, R15, R16): a `language_switch` component (native `<details>` + form, SVG
flags) in the top bar of every page; the glossary and Ukrainian writing rules in the UI guidelines;
the pinned frame measured again; the error pages translated, framework detail texts left as they
come.

**Tests** (R17): new catalogue completeness, template-literal, i18n, name-order, language-route,
localised-email and bilingual-consent tests; the existing suite keeps running in English
(`DEFAULT_LANGUAGE=en`), with the tests of changed behaviour updated.

## Technical Context

**Language/Version**: Python 3.13, unchanged.

**Primary Dependencies**:

- Unchanged: FastAPI, Jinja2 (3.1, `jinja2.ext.i18n`), SQLModel, Alembic, python-multipart, Pico.css
  v2.1.1 (vendored, not edited).
- **New runtime dependency: Babel** (`babel`), the only one (constitution v2.4.0, Localisation row):
  it loads the compiled catalogues at runtime and compiles them in the image.
- New scripts: `scripts/translations.sh`, `scripts/fill_english_catalogue.py` (development only;
  `scripts/` is not in the image).

**Storage**:

- SQLite (local, tests) and PostgreSQL (production), unchanged; no schema change.
- One Alembic revision after `04d5b638615c`: data only — the six tables' `name_key` recomputed (with
  a clash check) and the two consent texts rewritten ([data-model.md](./data-model.md) §4, §5).

**Testing**:

- pytest on both engines; the suite keeps English as its default language.
- New modules: `tests/unit/test_catalogues.py`, `tests/unit/test_template_text.py`,
  `tests/unit/test_i18n.py`, `tests/unit/test_name_order.py`,
  `tests/integration/test_language.py`, `tests/integration/test_localised_emails.py`,
  `tests/integration/test_bilingual_consent.py`.
- Updated modules: `tests/conftest.py`, `test_consent_texts`, `test_migrations`, `test_email`,
  `test_teacher_invitation`, `test_student_invitation`, the time-zone and competition-form tests that
  expect the UTC fallback, the name-order assertions in the listing tests, `test_layout`,
  `test_page_patterns`, `test_component_gallery`, `test_stylesheet`, `test_routes` (the language
  route; a Ukrainian sweep), `test_theme` (shared return path).
- By hand: layout in both languages and themes at 375 px and desktop, the frame measurement, the
  product owner's walk-through ([quickstart.md](./quickstart.md) §4, §6).

**Target Platform**:

- **Server**: the Linux container on Render, unchanged.
- **Browsers**: current Chrome, Edge, Firefox and Safari, desktop and phone, with and without
  JavaScript.

**Project Type**: a server-rendered web application (one FastAPI application).

**Performance Goals**:

- Catalogues are loaded once at startup; a translation is a dictionary lookup.
- The middleware parses one cookie per request.
- Sorting computes a short tuple per name in Python, over lists that are already fetched whole
  (tens to hundreds of rows).
- The migration reads and updates six small tables once.

**Constraints**:

- **No JavaScript**: the switch is a `<details>` with a form.
- **Stylesheet rules**: tokens only; one new length token; the milestone 10 and 10.1 checks stay
  green.
- **Both engines**: the same code and migration on SQLite and PostgreSQL; ordering never delegated
  to the database.
- **Message rules** ([contracts/i18n.md](./contracts/i18n.md)): whole messages, named placeholders,
  user content never translated, no gendered word about another person in Ukrainian.
- **Approval gate**: the Ukrainian consent wording and the glossary are approved before the pins and
  the merge (FR-045, FR-050).

**Scale/Scope**:

- About 90 templates and ~120 message constants plus 55 f-string messages in Python to convert;
  an estimated 700–900 messages in the catalogues.
- New: `app/core/i18n.py`, `app/core/return_path.py`, `app/routers/language.py`,
  `app/static/img/flag-ua.svg`, `flag-gb.svg`, `babel.cfg`, `app/locale/…`, two scripts, one
  migration.
- Changed: `core/config.py`, `core/templates.py`, `core/time_zone.py`, `main.py`,
  `schemas/names.py`, `schemas/people.py`, every router and service that holds a message, the
  sorting sites (R13), `services/email.py`, `services/consent.py`, `services/invitations.py`, every
  template, `app.css`, `Dockerfile`, `.gitignore`, `pyproject.toml`/`uv.lock`.
- Documents: product requirements, UI guidelines, README.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Walking skeleton | Milestone 12.4 is merged (PR #52). 12.5 is one end-to-end slice visible on every page: the switch, the translated pages, emails, consent, names and times. Nothing from milestone 13 or later is built (FR-068). | ✅ |
| II. Server-rendered simplicity | Server-rendered translations; the switch is a form; no new script in the browser, no build step for the browser. One new runtime dependency, Babel, justified here and listed in the constitution v2.4.0 stack. `Text` is the one new abstraction, needed by every message today. | ✅ |
| UI guidelines | The language switch goes into the component library, the gallery and `ui-guidelines.md` before the top bar uses it; the guidelines gain the glossary, the Ukrainian writing rules, the Ukrainian wording patterns, the time formats, the phone rules, a Languages section and the new checks (FR-063, FR-064). Tokens only; one new length token. | ✅ |
| III. Test-backed delivery | Every acceptance scenario and the milestone's _Test:_ line map to pytest cases (R17); the catalogue test and the template-literal test guard every later milestone; the existing suite stays in English and the changed assertions are named (FR-067). The new route has allowed tests for every role and signed out, and the cross-site refusal. Email stays the in-memory fake. | ✅ |
| IV. Role-based access & data scoping | No access rule changes. `POST /language` is public, like `POST /theme`, and reads and writes no data; every other route keeps its role checks, now with translated refusals. | ✅ |
| V. Secure authentication & secrets | `sc_lang` holds only `uk`/`en`, `HttpOnly`, `SameSite=Lax`, `Secure` in production, never logged; the language route passes the cross-site check; return addresses go through the existing safe-path check. The sign-in code stays out of the email subject in both languages. No secret added. | ✅ |
| VI. LLM evaluation | Not involved. | n/a |
| VII. Data integrity & migrations | One Alembic revision, data only, on both engines, covered by the stairway and drift checks: the duplicate keys recomputed after a clash check that stops before any write; the consent rows rewritten with a restoring downgrade. Times stay stored in UTC and are converted only for display. Sorting stays in Python, so both engines agree. | ✅ |
| Stack | Babel and `jinja2.ext.i18n` are the Localisation row of the constitution v2.4.0; nothing else is added. | ✅ |
| Application Layout | `core/` (i18n, return path, settings, time display), `schemas/` (name keys), `services/` (emails, consent parts, sorting), `routers/` (the language route; messages), `templates/components/` (the switch), `static/img/` (flags). Catalogues in `app/locale/`, beside the code they translate. | ✅ |
| Governance and workflow | The constitution amendment (v2.4.0) and the technical requirements are already in `main`. The product requirements, the UI guidelines and the README are updated in this PR; `milestones.md` on delivery. | ✅ |

**Post-design re-check (after Phase 1)**: all ✅.

- **Dependency**: Babel only, used at runtime and at image build; the scripts are development tools
  outside the image.
- **Security**: the new route reuses the theme route's checks unchanged
  ([contracts/http-routes.md](./contracts/http-routes.md) §1); the cookie is not personal data.
- **Data**: no new table or column; the migration changes only derived keys and the two consent
  wordings, both reversible; no consent record is touched.
- **Components**: the switch, the date macro and the changed form field are in
  [contracts/components.md](./contracts/components.md) with their gallery section.

## Project Structure

### Documentation (this feature)

```text
specs/012.5-ukrainian-localisation/
├── plan.md                 # This file
├── research.md             # Phase 0: decisions R1–R18
├── data-model.md           # Phase 1: cookie, setting, catalogues, consent rows, keys, order, times
├── quickstart.md           # Phase 1: how to run and check it
├── contracts/
│   ├── i18n.md             # the i18n module, Text, message rules, time formats, workflow
│   ├── http-routes.md      # POST /language; changed pages and routes
│   ├── components.md       # language_switch, top_bar, local_date, form field, consent parts
│   └── services.md         # config, templates, return path, names, emails, consent, migration
├── checklists/             # from /speckit-specify
└── tasks.md                # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
app/
├── core/
│   ├── i18n.py                  # NEW: Language, cookie, middleware, Text (_, _n, _p), Jinja callables
│   ├── return_path.py           # NEW: resolve_return (moved from routers/theme.py)
│   ├── config.py                # resolve_default_language, LanguageConfigError; APP_* as Text
│   ├── templates.py             # i18n extension, _page_context (language, return_path), no utc filter
│   └── time_zone.py             # Kyiv fallback, genitive months, format_local_date
├── schemas/
│   ├── names.py                 # name_key (apostrophes), name_sort_key, person_sort_key; Text messages
│   ├── people.py                # whole messages per field
│   └── *.py                     # messages → Text
├── services/
│   ├── email.py                 # localised builders; bilingual invitation; Kyiv times
│   ├── consent.py               # consent_parts
│   ├── invitations.py           # Role and Text detail lines to the email
│   ├── teachers.py, students.py, teams.py, classes.py, regions.py, institutions.py,
│   │   subjects.py, competitions.py, competition_entries.py, teacher_access.py   # sort keys; Text
│   └── *.py                     # messages → Text
├── routers/
│   ├── language.py              # NEW: POST /language
│   ├── theme.py                 # uses resolve_return
│   └── *.py                     # f-string and constant messages → Text
├── models/
│   ├── user.py, teacher.py      # labels → Text
├── templates/
│   ├── layouts/base.html        # <html lang>, translated title
│   ├── components/frame.html    # language_switch; top_bar order; texts
│   ├── components/time.html     # local_date
│   ├── components/form.html     # date/time labels as whole messages
│   ├── components/group.html    # plural count
│   ├── components/*.html        # texts
│   ├── pages/**/*.html          # texts; consent parts; dates
│   └── pages/admin/components.html   # language switch section (content stays English)
├── static/
│   ├── img/flag-ua.svg, flag-gb.svg  # NEW
│   └── css/app.css              # .language-switch, .flag, --sc-flag-height
├── locale/
│   ├── messages.pot             # NEW
│   ├── uk/LC_MESSAGES/messages.po   # NEW
│   └── en/LC_MESSAGES/messages.po   # NEW
└── main.py                      # middleware, setting, translations, language router, error texts

migrations/versions/2026_11_<dd>_<rev>_bilingual_consent_and_name_keys.py   # NEW

babel.cfg                        # NEW
scripts/translations.sh          # NEW
scripts/fill_english_catalogue.py   # NEW
Dockerfile                       # pybabel compile in the runtime stage
.gitignore                       # *.mo
pyproject.toml, uv.lock          # babel

tests/
├── unit/test_catalogues.py, test_template_text.py, test_i18n.py, test_name_order.py   # NEW
├── integration/test_language.py, test_localised_emails.py, test_bilingual_consent.py  # NEW
└── (updated) conftest.py and the modules listed in Technical Context

docs/requirements/product-requirements.md   # Languages section
docs/requirements/ui-guidelines.md          # localisation (FR-063), frame measurements
README.md                                    # Translations
```

**Structure Decision**: the existing single FastAPI application layout. Localisation is a core
concern (`app/core/i18n.py`) consumed by every layer through `Text` and the Jinja extension; the
language route mirrors the theme route and shares its return-address check; catalogues live in
`app/locale/` so they ship inside the `app/` copy of the image.

## Implementation Order

The order the tasks should follow, so the application stays working after each step:

1. **Foundation**: Babel; `i18n.py` (with empty catalogues); middleware; Jinja extension; setting;
   compile in conftest and the image; `test_i18n.py`. Pages still English.
2. **Consent draft first** (FR-050): the Ukrainian consent wordings drafted and sent to the product
   owner, with the glossary draft (R14), so the review runs during the rest of the work.
3. **Switch and route**: `return_path.py`, `POST /language`, the component, flags, CSS, gallery,
   guidelines entry; `test_language.py`.
4. **Messages**: components, then each area (sign-in and public pages, profile and consent, admin,
   teacher), converting templates and Python messages; catalogues updated and translated area by
   area; `test_catalogues.py` and `test_template_text.py` turn on once every area is done.
5. **Times and emails**.
6. **Names**: keys, sort keys, sites, the key part of the migration.
7. **Consent migration and pin test** with the draft wording.
8. **Layout and frame measurement**; documents.
9. **After approval**: final Ukrainian consent wording in the migration, pins updated, merge.

## Complexity Tracking

No constitution violations to justify. Babel is the listed Localisation technology (v2.4.0). The
`Text` value is the single abstraction the milestone's rule ("translated when rendered, never fixed
at import") requires.
