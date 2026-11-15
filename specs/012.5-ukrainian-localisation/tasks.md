---

description: "Task list for milestone 12.5: Ukrainian localisation"
---

# Tasks: Ukrainian Localisation (Milestone 12.5)

**Input**: Design documents from `/specs/012.5-ukrainian-localisation/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/i18n.md](./contracts/i18n.md),
[contracts/http-routes.md](./contracts/http-routes.md),
[contracts/components.md](./contracts/components.md), [contracts/services.md](./contracts/services.md),
[quickstart.md](./quickstart.md)

**Tests**: REQUIRED. FR-066 lists what the automated tests must cover, and Constitution Principle III
makes tests non-negotiable. The mapping from scenarios to modules is research R17.

- **Engines**: every database test runs on SQLite, and on PostgreSQL too when `TEST_POSTGRES_URL` is
  set (the `sc-pg` container), through the existing `database_url` / `engine` / `session` / `client`
  fixtures in `tests/conftest.py`.
- **The suite runs in English** (FR-067): `_isolate_environment` sets `DEFAULT_LANGUAGE=en` (T014).
  A test that needs Ukrainian either sends the cookie `sc_lang=uk` or requests the
  `ukrainian_default` fixture (T014) **before** `client` in its signature, so the lifespan reads
  `DEFAULT_LANGUAGE=uk`.
- **Expected Ukrainian texts** in tests come from the catalogue, not from hard-coded copies, wherever
  the exact wording is not itself the point: `with use_language(Language.UK): expected = str(_("Sign in"))`.
  Hard-code the Ukrainian only where the spec fixes it (plural forms, month names, the Kyiv label,
  the application's name, glossary terms).
- **Catalogue edits are serialised**: the area tasks only *mark* texts (different files, so [P]); one
  task per story then runs `scripts/translations.sh update`, translates the new Ukrainian entries and
  compiles. Never edit `app/locale/*/messages.po` from two tasks at once.

**Organization**: tasks are grouped by user story (US1–US12 in spec.md).

- **Phases 1–2** are the tooling and the i18n foundation (Babel, `app/core/i18n.py`, the setting,
  the middleware, the Jinja extension, the Kyiv-time formatter, the migration skeleton). Pages still
  read English afterwards.
- **US11 comes first among the stories** (Phase 3), although it is P3: the constitution puts the
  language switch in the library, the gallery and the guidelines before any page uses it (FR-064),
  and the glossary must be in the guidelines before anyone translates.
- **US1 → US2 → US3** (P1) make every page Ukrainian by default with a working switch; **US4** and
  **US5** (P1) do the emails and the consent texts. **US6–US9** (P2) and **US10**, **US12** (P3) follow.
- **The consent wording review** starts in Phase 1 (T008) and runs alongside everything else
  (FR-050); the final pins are the very last task (T100).

**Reference implementation**: read these before starting, and match their docstring style, naming,
comment density and error handling:

- **Cookie choice and its route**: `app/core/theme.py` (`Theme`, `parse_theme`, `apply_theme`,
  cookie constants), `app/routers/theme.py` (`_has_get_page`, the fallback, `choose_theme`),
  `tests/integration/test_theme.py`, `tests/unit/test_theme.py`, `tests/unit/test_safe_next.py`.
- **Settings**: `app/core/config.py` (`resolve_auth_settings`, the existing `…ConfigError` classes),
  `tests/unit/test_config.py`, `tests/integration/test_startup.py`.
- **Templates**: `app/core/templates.py` (`_theme` context processor, globals, the `utc` filter),
  `app/templates/components/frame.html` (`top_bar`, `user_menu`, `theme_switch`),
  `components/time.html` (`local_time`), the gallery `app/templates/pages/admin/components.html` with
  `app/routers/admin_components.py`, `docs/requirements/ui-guidelines.md` "Adding a pattern".
- **Times**: `app/core/time_zone.py`, `tests/unit/test_time_zone.py`.
- **Consent rewrite in place**: `migrations/versions/2026_10_29_09cbcbe472be_teams.py`
  (`STUDENT_CONSENT_TEXT_V1_REWRITE`, `_STUDENT_CONSENT_TEXT_V1_ORIGINAL`, `_write_student_text_v1`),
  `migrations/versions/2026_10_15_f3bd41a67737_create_consent_and_teachers.py`
  (`TEACHER_CONSENT_TEXT_V1`), `tests/unit/test_consent_texts.py`.
- **Migrations tests**: `tests/integration/test_migrations.py` (stairway, drift, data checks).
- **Screenshots**: headless Playwright via `uv run --with playwright` (not a dependency), against a
  copy of the local database on port 8765.

**Rules for every task** (contracts/i18n.md "Message rules", binding):

1. The message identifier is the English wording exactly as shown today (FR-023), so existing English
   tests keep passing.
2. Whole messages only, never joined from translated pieces (FR-021). A parameter may be a `Text` only
   when it is a self-contained value (a status, a role, an access level).
3. Named placeholders `%(name)s`; counts with `_n` / `ngettext` and `%(num)d`; a literal `%` is `%%`.
   No count ever chooses its form by comparing with 1 (FR-020).
4. User content is a parameter, inserted unchanged, never translated (FR-025). In Ukrainian it stands in
   «…» after a noun in the needed case, or after a colon for a person's name (FR-033).
5. `_p` / `pgettext` contexts where one English wording needs two Ukrainian ones.
6. Developer-only text (component contract errors, log lines, `/healthz`) stays plain English and is
   not marked (FR-024).
7. No Ukrainian word that agrees with another person's gender; the reader is «ви» (FR-034).
8. The gallery's content (`pages/admin/components.html`, `routers/admin_components.py`) is not marked
   (FR-027).
9. Ukrainian uses the glossary (research R14, ui-guidelines §7 after T026), «…» with „…“ inside, and
   the apostrophe ʼ (FR-030–FR-032).
10. In Python, messages are `Text` values from `app.core.i18n` (`_`, `_n`, `_p`), never `str()`-ed
    before the page is rendered or the email is built (FR-022). In templates, `{{ _("…", name=x) }}`
    (new-style gettext).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: the user story the task belongs to (US1–US12)
- Every task names its files

---

## Phase 1: Setup (Tooling and the consent draft)

**Purpose**: Babel, the catalogue files and scripts, the image build, and the Ukrainian consent
draft sent for review on day one (FR-050).

- [ ] T001 Add Babel as a **runtime** dependency (not the dev group): `uv add babel`, updating `pyproject.toml` and `uv.lock`; it is the only new dependency (FR-065)
- [ ] T002 [P] Create `babel.cfg` at the repository root per research R5: first `[ignore: app/templates/pages/admin/components.html]` and `[ignore: app/routers/admin_components.py]`, then `[python: app/**.py]` and `[jinja2: app/templates/**.html]` with `extensions = jinja2.ext.i18n` and `silent = false`
- [ ] T003 [P] Add `app/locale/*/LC_MESSAGES/*.mo` to `.gitignore` (FR-060); check `.dockerignore` keeps `app/locale/**/*.po` in the build context and excludes `*.mo`, so the image always compiles its own
- [ ] T004 [P] Create `scripts/fill_english_catalogue.py` (development only, not in the image): with `babel.messages.pofile.read_po`/`write_po`, for every entry of `app/locale/en/LC_MESSAGES/messages.po` whose translation is empty or marked fuzzy, set the translation to the identifier (plural entries: form 0 = singular identifier, form 1 = plural identifier) and clear the fuzzy flag; keep the header; keep line width as `pybabel update` writes it
- [ ] T005 Create executable `scripts/translations.sh` (`set -euo pipefail`, run from the repo root, everything through `uv run`) with three commands per research R5: `update` (`pybabel extract -F babel.cfg --no-default-keywords -k _ -k _n:1,2 -k _p:1c,2 -k gettext -k ngettext:1,2 -k pgettext:1c,2 -k npgettext:1c,2,3 -o app/locale/messages.pot app`, then `pybabel update -i app/locale/messages.pot -d app/locale -D messages --ignore-obsolete`, then `scripts/fill_english_catalogue.py`), `compile` (`pybabel compile -d app/locale -D messages --statistics`), `check` (`uv run pytest tests/unit/test_catalogues.py`); define the keyword list once at the top of the script with a comment that `tests/unit/test_catalogues.py` mirrors it
- [ ] T006 Create the initial catalogues: run the extract of T005, then `pybabel init` for `uk` and `en` into `app/locale/{uk,en}/LC_MESSAGES/messages.po`; set the headers `Language: uk` / `Language: en` and the plural rules verbatim from data-model §3 — uk: `Plural-Forms: nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);`, en: `nplurals=2; plural=(n != 1);`; commit `app/locale/messages.pot` and both `.po` files (depends on T001, T002, T005)
- [ ] T007 [P] In `Dockerfile`'s runtime stage, after `COPY app ./app` and before `USER appuser`, add `RUN pybabel compile -d app/locale -D messages` with a comment citing milestone 12.5 FR-060 (Babel is in the copied virtualenv, `pybabel` is on `PATH`); if Docker is available, `docker build .` and confirm `app/locale/uk/LC_MESSAGES/messages.mo` exists in the image
- [ ] T008 [P] Draft the bilingual consent texts for review in `specs/012.5-ukrainian-localisation/consent-wording.md`: for the teacher, today's `TEACHER_CONSENT_TEXT_V1` (`migrations/versions/2026_10_15_f3bd41a67737_create_consent_and_teachers.py`); for the student, today's `STUDENT_CONSENT_TEXT_V1_REWRITE` (`migrations/versions/2026_10_29_09cbcbe472be_teams.py`). Each in the exact shape of data-model §4: `Українською`, the Ukrainian paragraphs (a faithful translation using the glossary: Педагог, Студент, заклад освіти, група; «…», ʼ, «ви», no gendered word) ending with «Якщо українська та англійська редакції відрізняються, переважає українська редакція.», then `English`, today's English paragraphs **word for word**, then "If the Ukrainian and English wordings differ, the Ukrainian wording prevails." (FR-044, FR-045). Tell the user the draft is ready for the product owner's review; work continues meanwhile

**Checkpoint**: `scripts/translations.sh update && scripts/translations.sh compile` run cleanly on a
fresh clone; the image builds.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the i18n module, the setting, the middleware, the Jinja extension, the test harness, the
Kyiv-time formatter and the migration skeleton. Pages still read English after this phase.

**⚠️ CRITICAL**: no user story work begins until this phase is complete.

- [ ] T009 [P] Write `tests/unit/test_i18n.py` first (it fails until T010–T011), per research R17: `Text` in English context returns the identifier with parameters; under a Ukrainian `Translations` built in memory (a `babel.messages.Catalog` with the uk `Plural-Forms` header, written with `babel.messages.mofile.write_mo` to a `BytesIO`, monkeypatched into the module's language→translations mapping) it returns the translation; a user parameter equal to some identifier (e.g. "Physics") is inserted unchanged; a `Text` parameter is translated in the same language; `==` against `str` and `Text`, `hash` consistent with `==`; `_n` picks the right uk form for 1, 2, 5, 11, 21, 22, 25 and exposes `%(num)d`; `parse_language`: `"uk"`, `"en"` → the `Language`, `"ua"`, `"UK"`, `"en-GB"`, `""`, `None`, `"x" * 5000` → `None`; `use_language` restores the previous language on exit; `current_language()` is `Language.EN` outside any request; `apply_language` sets `sc_lang` with `Max-Age=31536000`, `Path=/`, `HttpOnly`, `SameSite=lax`, and `Secure` only when `secure=True`, for both `uk` and `en`; `resolve_default_language`: unset and empty → `uk`, `"uk"`/`"en"` → that, `"fr"`, `"UK"`, `"ua"` → `LanguageConfigError` whose message is exactly "DEFAULT_LANGUAGE must be uk or en"
- [ ] T010 Create `app/core/i18n.py` exactly per contracts/i18n.md "Public names", in the style of `app/core/theme.py`: `Language(StrEnum)`, `LANGUAGE_COOKIE_NAME = "sc_lang"`, `LANGUAGE_COOKIE_MAX_AGE = 31_536_000`, `LOCALE_DIR`; `parse_language` (exact match only, never raises); `apply_language` (always sets, never deletes, FR-015); `TranslationsNotCompiled` and `load_translations()` (idempotent; loads `babel.support.Translations.load(LOCALE_DIR, [code], "messages")` per language into a module mapping; a missing `.mo` raises with the message "Translations are not compiled: run scripts/translations.sh compile"); a `ContextVar` whose default is `gettext.NullTranslations()` (English identifiers, English plural rule); `current_language()`, `use_language()`; the frozen `Text` dataclass and `_`, `_n` (adds `num=n`), `_p` (translate on `__str__` in the current language, then `%`-format with the parameters, `str()`-ing `Text` parameters in the same language, other values unchanged; `__eq__`/`__hash__` on the current rendering); the four plain Jinja callables `gettext(msgid)`, `ngettext(singular, plural, n)`, `pgettext(context, msgid)`, `npgettext(context, singular, plural, n)` reading the `ContextVar` (Jinja's new-style wrapper does the `%` formatting and escaping); `LanguageMiddleware`, a pure ASGI class: for `http` scopes only, parse the `cookie` header (Starlette's `cookie_parser`), `language = parse_language(cookie) or scope["app"].state.default_language`, set `scope.setdefault("state", {})["language"] = language`, set the `ContextVar` to that language's translations and reset it after the call; never read `Accept-Language` (FR-003); never log the cookie (FR-016)
- [ ] T011 Update `app/core/config.py` per contracts/services.md: `LanguageConfigError(RuntimeError)` and `resolve_default_language(environ=os.environ) -> Language` (unset/empty → `UK`, `"uk"`/`"en"` → that, anything else → `LanguageConfigError("DEFAULT_LANGUAGE must be uk or en")`, naming the setting, never the value); make `APP_NAME` (identifier "Student Competitions", uk «Студентські змагання»), `APP_TAGLINE` and `APP_DESCRIPTION` `Text` values; where a plain `str` is needed outside a request (FastAPI's `title=`, log lines), pass the English identifier explicitly; grep `APP_NAME|APP_TAGLINE|APP_DESCRIPTION` across `app/` and fix every string operation on them
- [ ] T012 Update `app/core/templates.py` per contracts/services.md: `templates.env.add_extension("jinja2.ext.i18n")`; `templates.env.install_gettext_callables(gettext, ngettext, newstyle=True, pgettext=pgettext, npgettext=npgettext)` with the callables of T010; rename the context processor `_theme` → `_page_context` returning `theme`, `language` (`request.state.language`) and `return_path` (today's `theme_return`, same value); rename `theme_return` → `return_path` in `app/templates/components/frame.html:43` and `app/templates/pages/login.html:23` and in the module docstring; add the global `app_name` (`APP_NAME`); in `app/templates/layouts/base.html` set `<html lang="{{ language }}">` (FR-005), so every page declares the request's language from this phase on (T019 checks it on the gallery); leave the `utc` filter for now (removed in T082); adapt `tests/unit/test_templates.py`
- [ ] T013 Update `app/main.py` in two places. **Inside `lifespan()`**: call `resolve_default_language()` beside `resolve_auth_settings()`, before the database, and store it on `app.state.default_language`; call `load_translations()`. **At module level, right after `app = FastAPI(...)`** (with the exception handlers and routers, never inside `lifespan()`): `app.add_middleware(LanguageMiddleware)` — Starlette builds the middleware chain on the app's first call, which is the startup event itself, so adding middleware from `lifespan()` raises `RuntimeError: Cannot add middleware after an application has started`. Registered there, it sits between `ServerErrorMiddleware` and `ExceptionMiddleware`, so it wraps routing and the exception handlers (the error pages are translated; the plain-text 500 stays outside, FR-026), and it reads `app.state.default_language` per request, after the lifespan has set it. Add to `tests/integration/test_startup.py`: `any(m.cls is LanguageMiddleware for m in app.user_middleware)`; `DEFAULT_LANGUAGE=fr` stops the start with a message naming `DEFAULT_LANGUAGE`; unset starts with `app.state.default_language == Language.UK`; a `LOCALE_DIR` monkeypatched to an empty temporary directory stops the start with "Translations are not compiled: run scripts/translations.sh compile" — `load_translations()` caches what it loaded, so the test also empties that cache (monkeypatch the module's language→translations mapping to `{}`), otherwise an earlier load would hide the missing files
- [ ] T014 Update `tests/conftest.py`: `_isolate_environment` sets `DEFAULT_LANGUAGE=en` (FR-067); `pytest_sessionstart` compiles both catalogues to `app/locale/{uk,en}/LC_MESSAGES/messages.mo` through Babel's Python API (`read_po` + `write_mo`), so `uv run pytest` works on a fresh clone (FR-060); add the fixture `ukrainian_default` (`monkeypatch.setenv("DEFAULT_LANGUAGE", "uk")`, documented as "request before `client`"); run `uv run pytest tests/unit/test_i18n.py tests/integration/test_startup.py` green
- [ ] T015 Update `app/core/time_zone.py` per research R9 and contracts/i18n.md §Times: `KYIV = ZoneInfo("Europe/Kyiv")` (keep `UTC_ZONE`); replace `MONTHS` with twelve `_p("genitive month", "January")` … `"December"`; `format_local_time(moment, zone)` → `_("%(day)d %(month)s %(year)d, %(time)s")` in `zone` with no label when known, and in `KYIV` wrapped in `_("%(moment)s (Kyiv time)")` when `zone is None`; new `format_local_date(moment, zone)` → `_("%(day)d %(month)s %(year)d")` (Kyiv when `None`, no label); `zone_name(None) == "Europe/Kyiv"`; the day without a leading zero, `HH:MM` 24-hour; both return `str`. Register `format_local_date` as a template global in `app/core/templates.py`. Update every test that expects the UTC fallback or the "Time zone: UTC" hint: `tests/unit/test_time_zone.py` (lines 39, 47, 51), `tests/unit/test_templates.py`, `tests/unit/test_competition_schemas.py`, `tests/integration/test_teacher_competitions.py`, `test_teacher_competition_entries.py`, `test_teacher_grades.py`, `test_team_answer_service.py`, `test_student_invitation_refusals.py` (grep `UTC"` and `Time zone: UTC`); `services/email.py`'s `format_utc` stays until T065
- [ ] T016 Run `scripts/translations.sh update`; in `app/locale/uk/LC_MESSAGES/messages.po` translate the time messages: the twelve genitive months «січня», «лютого», «березня», «квітня», «травня», «червня», «липня», «серпня», «вересня», «жовтня», «листопада», «грудня»; `%(day)d %(month)s %(year)d, %(time)s` and `%(day)d %(month)s %(year)d` unchanged; `%(moment)s (за київським часом)`; compile. Add to `tests/unit/test_time_zone.py`, under `use_language(Language.UK)`: «14 березня 2027, 10:00» in Kyiv, «1 березня 2027, 00:05», «14 березня 2027, 10:00 (за київським часом)» for `None`, «15 жовтня 2026» for a date, every month in the genitive; and the English "14 March 2027, 10:00 (Kyiv time)"
- [ ] T017 Create the data-only migration skeleton with `uv run alembic revision -m "bilingual consent and name keys"`, renamed to the project's pattern `migrations/versions/2026_11_<dd>_<rev>_bilingual_consent_and_name_keys.py`, `down_revision = "04d5b638615c"`; module docstring: data only (consent wording rewrite, name keys recomputed), never imports `app`, the last in-place consent rewrite (FR-051); `upgrade()`/`downgrade()` empty for now; `tests/integration/test_migrations.py` stairway and drift pass
- [ ] T018 Checkpoint: `uv run ruff check . && uv run ruff format --check . && uv run pytest` green (both engines when `sc-pg` is running); pages still read English with the suite's `DEFAULT_LANGUAGE=en`

**Checkpoint**: the i18n machinery works; any later task can mark a text and see it translated.

---

## Phase 3: User Story 11 - The documents and the gallery come first (Priority: P3, scheduled first)

**Goal**: the language switch is in the component library, the gallery and the UI guidelines, and the
guidelines hold the glossary and the Ukrainian writing rules, before any page uses them (FR-063,
FR-064); the product requirements gain **Languages** (FR-062).

**Independent Test**: read the updated documents; open `/admin/components#language` as an
administrator outside production and see the switch closed and open.

### Tests for User Story 11

- [ ] T019 [P] [US11] In `tests/integration/test_component_gallery.py` assert a `#language` section showing the switch closed and open (`<details open>`) with each language current; the two buttons `name="language"` with values `uk`, `en`, each with `lang` of its own language, the current one `aria-current="true"`; flags `<img alt="">` from `/static/img/flag-ua.svg` and `flag-gb.svg`; with `sc_lang=uk` the page has `lang="uk"` while a known English sample text of the gallery is still English
- [ ] T020 [P] [US11] In `tests/unit/test_stylesheet.py` (and `tests/unit/test_frame_stylesheet.py` if it enumerates frame classes) assert `.language-switch` and `.flag` exist in the Components section, use tokens only, and `--sc-flag-height` is a length token defined once in `:root` (no dark-theme entry needed)

### Implementation for User Story 11

- [ ] T021 [P] [US11] Create `app/static/img/flag-ua.svg` (two equal horizontal bands, blue `#0057B7` over yellow `#FFD700`, `viewBox="0 0 3 2"`) and `app/static/img/flag-gb.svg` (a simplified flat Union Flag, `viewBox="0 0 60 30"`): no text, no scripts, a few hundred bytes each (FR-009; named by country code `ua`, `gb`)
- [ ] T022 [US11] Add the macro `language_switch(current, return_to)` to `app/templates/components/frame.html` exactly as contracts/components.md §1 (the `<details class="language-switch">`, the hidden `{{ _("Language") }}` label, the current name in `<span class="language-switch-name" lang="…">`, one `<form method="post" action="/language" class="language-switch-panel">` with hidden `next` and two buttons, Українська first, `aria-current="true"` on the current); the names «Українська» and "English" are literal, not translated (FR-007); `top_bar()` does not call it yet (T043)
- [ ] T023 [US11] Style it in the Components section of `app/static/css/app.css`, tokens only: new `--sc-flag-height` length token; the summary drawn like a select (the existing border token and a chevron from existing tokens); the panel positioned under the switch like the user menu's panel; every button at least `--sc-touch-target` tall and wide (FR-010); below 768 px `.language-switch .language-switch-name` inside the summary is visually hidden with the project's existing visually-hidden technique (still read), while the panel's names stay visible
- [ ] T024 [US11] Add a **Language switch** section `id="language"` to `app/templates/pages/admin/components.html` (and its sample data in `app/routers/admin_components.py` if the gallery passes samples): the switch closed, and open with `<details open>`, once with `uk` and once with `en` current; add it to the gallery's contents list; gallery text stays English and unmarked (FR-027)
- [ ] T025 [P] [US11] Update `docs/requirements/ui-guidelines.md` §4 Layout (top bar order: brand, role label, language switch, user menu; signed out: brand, language switch), §5 Components → Frame (the language switch: markup, no JavaScript, flags as SVG never emoji, current marked, names in their own language) and §5 Local time (formats "14 March 2027, 10:00" / «14 березня 2027, 10:00», a date alone, the Kyiv fallback with its label on pages and always in emails, `local_date`), §8 Phone behaviour (flag only below 768 px, 44 px options; the theme switch stays in the user menu and under the sign-in form)
- [ ] T026 [US11] Update `docs/requirements/ui-guidelines.md` §7 Wording patterns: the glossary table copied verbatim from research R14; the Ukrainian writing rules (FR-032–FR-034 with the spec's examples: «Видалити предмет «Фізика»?», «Назад до регіону «Київ»», «Вилучити зі списку: Олена Коваленко?», "Олена Коваленко запрошує вас"); the Ukrainian form of each existing wording pattern. Add a new **Languages** section: the message rules 1–8 of contracts/i18n.md, the catalogue workflow, user content never translated, the gallery stays English, every page checked in both languages. Add to §10 Checks: `test_catalogues.py`, `test_template_text.py`, `test_ukrainian_wording.py`, the sort-key guard in `test_name_order.py` (depends on T025, same file)
- [ ] T027 [P] [US11] Add a **Languages** section to `docs/requirements/product-requirements.md` (FR-062): Ukrainian is the default language of the interface, the consent texts and every other communication with users; English is the alternative, chosen per browser; the consent texts are bilingual and the Ukrainian wording prevails; what people enter is never translated; participants come from schools and colleges

**Checkpoint**: the gallery shows the switch; the glossary is in the guidelines for every translation
task that follows.

---

## Phase 4: User Story 1 - A first visit opens in Ukrainian (Priority: P1) 🎯 MVP

**Goal**: with no language chosen, whatever the browser prefers, the frame and every signed-out page
(sign-in, code entry, role choice, invitation, data deletion, errors) are Ukrainian and declare
`lang="uk"`.

**Independent Test**: with `DEFAULT_LANGUAGE=uk`, no cookie and `Accept-Language: en`, open `/login`,
`/data-deletion` and an invitation link: each is Ukrainian with `<html lang="uk">`.

### Tests for User Story 1

- [ ] T028 [P] [US1] Create `tests/integration/test_language.py` with a "default" section (requesting `ukrainian_default` before `client`): with header `Accept-Language: en-GB,en;q=0.9`, `GET /login`, `/data-deletion`, a teacher invitation page `/invitations/{token}` (made with the helpers of `tests/integration/test_teacher_invitation.py`) and an unknown path (404) each have `<html lang="uk">`, a Ukrainian heading (expected text from the catalogue) and a `<title>` containing «Студентські змагання»; cookies `sc_lang=ua`, `UK`, `en-GB`, empty and a 4000-character value each give a Ukrainian 200 page; with the suite default (`en`) and `sc_lang=uk` the page is Ukrainian; with `sc_lang=en` it is English with `lang="en"`

### Implementation for User Story 1

- [ ] T029 [US1] In `app/templates/layouts/base.html` (whose `<html lang>` T012 already sets) mark every literal, including the page-title pattern with `app_name`
- [ ] T030 [P] [US1] Mark every text in `app/templates/components/frame.html` (skip link, wordmark via `app_name`, account menu label, "Switch to", "Log out", footer, the theme switch's label and **Light**/**Dark**/**Device**) and `app/templates/components/menu.html`; aria-labels and titles too
- [ ] T031 [P] [US1] Mark every text in `app/templates/components/form.html` (error summary "There is a problem", hints, optional/required markers; **not** the date-time field, T050), `components/feedback.html`, `components/button.html`, `components/card.html`, `components/details.html`, `components/icons.html` (accessible names and `<title>`s)
- [ ] T032 [P] [US1] Mark every text and page title in `app/templates/pages/login.html`, `login_code.html`, `role_choice.html`, `home.html`, `data_deletion_request.html`, `data_deletion_requested.html`, `data_deletion_confirm.html`, `data_erased.html`, `invitation.html` (everything except the consent text, T072, and the expiry line, T083), `invitation_status.html`, `link_status.html`, `error.html`
- [ ] T033 [P] [US1] Convert the person-facing messages of `app/schemas/auth.py`, `app/routers/auth.py`, `app/routers/roles.py`, `app/routers/pages.py`, `app/routers/data_deletion.py`, `app/services/login.py`, `app/services/data_deletion.py`, `app/services/sessions.py` to `Text` (`_` with named parameters); log lines stay plain English
- [ ] T034 [P] [US1] Convert the messages of `app/routers/invitations.py` and `app/services/invitations.py` to `Text`; replace `f"You are already a {label.lower()}."` (`app/routers/invitations.py:89`) with one whole message per role chosen through a `dict[Role, Text]` (`_("You are already a teacher.")`, `_("You are already a student.")`, and the administrator if reachable)
- [ ] T035 [P] [US1] Make `Role.label` in `app/models/user.py` return `Text` ("Administrator", "Teacher", "Student"; glossary: Адміністратор, Педагог, Студент); grep `\.label\.lower\(\)|label\.lower\(\)|role\.lower\(\)` across `app/` and replace every use with a whole message (contracts/services.md "Enums with labels")
- [ ] T036 [US1] Translate the error handling in `app/main.py` per research R16: "Access denied", "Request refused" and the 403 sentences as `Text`; for a plain `HTTPException`, a translated heading by status (`_("Page not found")` for 404, `_("This address does not accept that request")` for 405, one generic `_("Something went wrong")` otherwise) above the framework's `detail` shown as it comes (FR-026); the malformed-request JSON and the plain-text 500 untouched; update tests asserting the old headings (grep `Not Found`, `Access denied` in `tests/`)
- [ ] T037 [US1] `scripts/translations.sh update`; translate every new entry in `app/locale/uk/LC_MESSAGES/messages.po` with the glossary and writing rules (ui-guidelines §7); `scripts/translations.sh compile`; run `tests/integration/test_language.py` and the whole suite (English unchanged)

**Checkpoint**: a first visit is Ukrainian on every signed-out page and in the frame.

---

## Phase 5: User Story 2 - Anyone switches the language on any page (Priority: P1)

**Goal**: the switch is in the top bar of every page; `POST /language` stores the choice and returns
to the same page, without JavaScript; the choice survives signing in, switching role and signing out.

**Independent Test**: with JavaScript off, choose each language on a signed-out page, a page of each
role, an error page and a page shown after a form error; check the landing, the language and the
persistence through sign-in and sign-out.

### Tests for User Story 2

- [ ] T038 [P] [US2] Add a "route" section to `tests/integration/test_language.py` per contracts/http-routes.md §1: `POST /language` with `uk` and with `en` → 303 to `next` and `Set-Cookie: sc_lang=<code>; Max-Age=31536000; Path=/; HttpOnly; SameSite=lax` (+ `Secure` with the production setting, as `test_theme.py` checks it); `uk` is stored although the suite default is `en` (FR-015); `next=/teacher/competitions?subject=<id>&status=…&page=2` returns there with the query; refused `next` values `https://evil.example/`, `//evil.example`, a POST-only sign-in step, `/no-such-page`, empty → `/` signed in and `/login` signed out, with the cookie still set; `language` values `ua`, `EN`, `` and missing → 303, **no** `Set-Cookie`; choosing the current language again stores it and returns; a cross-site submission → the existing 403 "Request refused" and no cookie; English chosen, then sign in, switch role, sign out → every page still English; with `caplog` at DEBUG across these requests, no log record names `sc_lang` (FR-016)
- [ ] T039 [P] [US2] Add a "switch on every page" section to `tests/integration/test_language.py`: the switch (`details.language-switch`) is in the top bar of `/login`, the code-entry page, the role choice, an invitation page, `/data-deletion`, a 404 page, the page shown after `POST /login` with an invalid address, `/admin/teachers`, `/teacher/students` and `/profile`; where a user menu exists the switch comes before it; the open panel lists Українська (flag ua) then English (flag gb), each with its own `lang`, the current with `aria-current="true"`; its hidden `next` equals the page's return path (use the parsers in `tests/html.py`)
- [ ] T040 [P] [US2] Point `tests/integration/test_theme.py` and `tests/unit/test_safe_next.py` (where they reach `_has_get_page`) at `app.core.return_path.resolve_return`; the theme's behaviour is unchanged

### Implementation for User Story 2

- [ ] T041 [US2] Create `app/core/return_path.py` with `resolve_return(request, raw) -> str`: move `_has_get_page` and the `/` / `/login` fallback out of `app/routers/theme.py` unchanged (FR-012); `app/routers/theme.py` calls it
- [ ] T042 [US2] Create `app/routers/language.py` with public `POST /language` (form fields read as plain strings, `language: str = Form("")`, `next: str = Form("")`): `parse_language`; when valid, `apply_language(response, language, secure=…)` with the same production flag `choose_theme` uses; always `RedirectResponse(resolve_return(request, next), status_code=303)`; nothing logged about the value (FR-016); include the router in `app/main.py` next to the theme router
- [ ] T043 [US2] In `app/templates/components/frame.html` make `top_bar()` call `language_switch(language, return_path)` before `user_menu()` when signed in, and at the end of the bar when signed out (contracts/components.md §2); check that `pages/error.html` and every signed-out page render `top_bar()`
- [ ] T044 [P] [US2] Add `("POST", "/language")` beside `("POST", "/theme")` in the public route tables of `tests/integration/test_routes.py` (around lines 110 and 160), so it has allowed tests for every role and signed out
- [ ] T045 [P] [US2] In `tests/integration/test_form_contract.py` leave out the `/language` forms as the `/theme` forms are, and record the change in the module docstring's "Deliberate changes since" list (milestone 12.5); update `tests/integration/test_layout.py` and `tests/integration/test_page_patterns.py` for the top bar order with the switch
- [ ] T046 [US2] `scripts/translations.sh update` (the "Language" label), translate, compile; run `test_language.py`, `test_theme.py`, `test_cross_site.py`, `test_layout.py`, `test_page_patterns.py`, `test_routes.py`, `test_form_contract.py`

**Checkpoint**: US1 + US2 are the MVP: Ukrainian by default, English on request, from any page.

---

## Phase 6: User Story 3 - Every screen of every role speaks the chosen language (Priority: P1)

**Goal**: every text the application writes, on every page of every role, is in the chosen language,
with the glossary's terms and correct plurals; entered content is unchanged.

**Independent Test**: with Ukrainian and then English chosen, render every page and fragment of every
role and every error page; nothing the application writes is left in the other language; entered
names are unchanged.

### Tests for User Story 3

- [ ] T047 [P] [US3] Add a Ukrainian sweep to `tests/integration/test_routes.py`: every GET page of the existing sweep, as the role that opens it, with `sc_lang=uk` → `lang="uk"` and a `<title>` ending with «Студентські змагання»; with `sc_lang=en` → `lang="en"` and "Student Competitions"; `/admin/components` checked for its frame only
- [ ] T048 [P] [US3] Add to `tests/unit/test_i18n.py` real-catalogue checks under `use_language`: `_n("%(num)d team", "%(num)d teams", n)` gives «1 команда», «2 команди», «5 команд», «11 команд», «21 команда», «22 команди», «25 команд» and "1 team" / "2 teams"; every `CompetitionStatus`, `AccessLevel`, `Role` label is the glossary term (Заплановано, Триває, Завершено, Скасовано; Перегляд, Редагування; Адміністратор, Педагог, Студент); `pgettext(kind, "Active")` is «Активний» for `subject`, `region`, `institution` and «Активна» for `class`, and `pgettext(kind, "Deactivated")` is «Деактивовано» for all four
- [ ] T049 [P] [US3] Add an "entered content" section to `tests/integration/test_language.py`: a subject named "Physics" and a question written in English show unchanged with `sc_lang=uk`; a subject «Фізика» shows unchanged with `sc_lang=en`; a form submitted with errors shows the error summary and field errors in the chosen language and keeps the typed values

### Implementation for User Story 3

- [ ] T050 [P] [US3] Mark every text in the remaining components: `components/badge.html` (`access_badge` and `competition_status_badge` as plain messages; `status_badge(is_active)` becomes `status_badge(is_active, kind)` with `kind` one of `subject`, `region`, `institution`, `class`, an unknown kind refused with `template_error`, and the words `pgettext(kind, "Active")` / `pgettext(kind, "Deactivated")`, so Ukrainian agrees with each record's noun: «Активний» for предмет, регіон, заклад освіти, «Активна» for група, «Деактивовано» for all (contracts/components.md §6a); pass the kind at every caller: `components/frame.html:111`, `components/selectors.html:31`, `pages/profile.html:29` (institution) and `:33` (class), `pages/admin/_institution_picker.html:17`, `pages/admin/subjects.html`, `pages/admin/institutions.html` and every other `status_badge(` call (grep), and the gallery's calls in `pages/admin/components.html`), `confirmation.html`, `filter.html`, `group.html` (header count `ngettext("%(num)d team", "%(num)d teams", total)`), `pagination.html` ("Previous", "Next", the range `_("%(noun)s %(first)d–%(last)d of %(total)d")`), `selectors.html`, `table.html` ("Actions", `Actions for “%(item)s”`), `time.html`, `answer_sheet.html`, `grading_sheet.html`, `palette.html`; change the date-time field of `components/form.html` to take `date_label` and `time_label` as whole messages instead of `legend ~ " date"` / `legend ~ " time"`, with the hint `_("Time zone: %(zone)s", zone=zone_label)` (contracts/components.md §5), and update its callers (`pages/teacher/competition_form.html`)
- [ ] T051 [P] [US3] Mark the tabs and headings of `app/templates/layouts/admin.html` and `app/templates/layouts/teacher.html` (glossary: Педагоги, Заклади освіти, Предмети; Учасники, Команди, Питання, Змагання)
- [ ] T052 [US3] Make the labels `Text` (not [P]: it edits `app/services/classes.py` and `app/services/competitions.py`, which T054 also edits; run it before or after T054, never alongside): `AccessLevel.label` in `app/models/teacher.py:31` (`_p("access level", "Read")`, `_p("access level", "Write")`); `CompetitionStatus.label` in `app/services/competitions.py` (the enum at line 62); `ClassView.label` in `app/services/classes.py:69`, today the assembled `f"{self.name} · year {self.year_of_study}"`, becomes the whole message `_("%(name)s · year %(year)d", name=self.name, year=self.year_of_study)` (FR-021); the "Active"/"Deactivated" badge is T050's
- [ ] T053 [P] [US3] Convert the messages of `app/schemas/names.py` (`InvalidName.message`), `subject.py`, `question.py`, `classes.py`, `students.py`, `teachers.py`, `competition.py`, `answer.py`, `grade.py` to `Text`; in `app/schemas/people.py` change `clean_person_name(raw, field)` to take a field key (`"first_name"` / `"last_name"`) and pick whole messages per field instead of inserting the field's name into a sentence; update callers and `tests/unit/test_person_schemas.py`
- [ ] T054 [P] [US3] Convert the messages of `app/services/availability.py`, `classes.py`, `competition_entries.py`, `competitions.py`, `grades.py`, `institutions.py`, `questions.py`, `regions.py`, `students.py`, `subjects.py`, `teacher_access.py`, `teachers.py` (not the detail lines, T066), `team_answers.py`, `teams.py`, `users.py` to `Text`; each `f"…“{name}”…"` (one in each of regions, classes, teams, institutions, subjects, competitions) becomes `_("…“%(name)s”…", name=…)`, with a `_p(<kind>, …)` context where the Ukrainian needs the record's noun
- [ ] T055 [P] [US3] Administrator area: mark every text and title in `app/templates/pages/admin/*.html` **except** `components.html`, plus `pages/area.html`; `admin/institution_delete.html`'s `{% if classes == 1 %}…{% elif %}` becomes one `ngettext` message; convert the messages of `app/routers/admin.py`, `admin_subjects.py`, `admin_institutions.py` (one f-string), `admin_teachers.py`, `areas.py` to `Text`
- [ ] T056 [P] [US3] Teacher students and classes: mark `app/templates/pages/teacher/students.html`, `student_form.html`, `student_invite.html`, `student_remove.html`, `class_form.html`, `class_deactivate.html`, `class_delete.html`; convert `app/routers/teacher.py` and `app/routers/teacher_students.py` (two f-strings) to `Text`
- [ ] T057 [P] [US3] Teacher teams: mark `pages/teacher/teams.html`, `team_form.html`, `team_delete.html`, `team_add_students.html`, `team_member_remove.html`; convert `app/routers/teacher_teams.py` (four f-strings) to `Text`
- [ ] T058 [P] [US3] Teacher questions: mark `pages/teacher/questions.html`, `question_form.html`, `question_delete.html`, `question_not_found.html`; convert `app/routers/teacher_questions.py` to `Text`; the sample questions of milestone 3 stay as they are (FR-025)
- [ ] T059 [P] [US3] Teacher competitions: mark `pages/teacher/competitions.html`, `competition_form.html`, `competition_cancel.html`, `competition_finish.html`, `competition_not_found.html`, `competition_refused.html`, `competition_questions.html`, `competition_questions_add.html`, `competition_teams.html`, `competition_teams_add.html`, `competition_entry_remove.html`; convert `app/routers/teacher_competitions.py` (three f-strings) and `app/routers/teacher_competition_entries.py` (five f-strings; `f"Change the {kind} of …"` at line 368 becomes one whole message per kind, questions and teams) to `Text`
- [ ] T060 [P] [US3] Answers and grades: mark `pages/teacher/competition_answers.html`, `competition_grades.html` (team count with `ngettext`), `team_answer_sheet.html`, `team_answers_read_only.html` (answer count with `ngettext`), `team_grading_sheet.html`; convert `app/routers/teacher_team_answers.py` and `app/routers/teacher_grades.py` (two f-strings each) to `Text`
- [ ] T061 [P] [US3] Profile: mark `pages/profile.html` (all but the consent text, T072, and the "Accepted" line, T083) and `pages/profile_withdraw.html`; convert `app/routers/profile.py` to `Text`
- [ ] T062 [US3] `scripts/translations.sh update`; translate every new entry in `app/locale/uk/LC_MESSAGES/messages.po` (glossary terms; names in «…» after a noun in the needed case; a colon before a person's name; no gendered word; «ви»; ʼ); compile; run the whole suite in English and fix tests that compared strings changed by whole-message rewrites (person-name field errors, counts)

**Checkpoint**: every page of every role is bilingual.

---

## Phase 7: User Story 4 - Emails arrive in the right language (Priority: P1)

**Goal**: the sign-in code and the deletion link in the request's language; the invitation in
Ukrainian then English; every email time in Kyiv time, labelled.

**Independent Test**: send the sign-in code and the deletion link with each language and with none,
and a teacher's and a student's invitation with each language, and read the captured messages.

### Tests for User Story 4

- [ ] T063 [P] [US4] Create `tests/integration/test_localised_emails.py`: `POST /login` with `sc_lang=uk`, `sc_lang=en` and none under `ukrainian_default` → subject and text in that language, the code in the text and never in the subject; the data-deletion email in each language with its expiry "… (Kyiv time)" / «… (за київським часом)»; a teacher invitation sent by an administrator and a student invitation sent by a teacher, each with `sc_lang=uk` and `sc_lang=en` → the same email: subject `"<uk subject> / <en subject>"`, text = whole Ukrainian message, a `———` separator line, whole English message; each part names the role, the details that will be stored, the link and the expiry labelled in its language; institution, class and person names appear exactly as entered in both parts; the Ukrainian part says «… запрошує вас»; the application's name reads «Студентські змагання» in every Ukrainian subject and text and "Student Competitions" in every English one (FR-019); the sender name is the configured one, unchanged
- [ ] T064 [P] [US4] Update `tests/unit/test_email.py` (no `format_utc`; builders checked under `use_language`), and the email assertions of `tests/integration/test_teacher_invitation.py`, `test_student_invitation.py`, `test_data_deletion.py`, `test_login_flow.py` for the new formats (FR-067)

### Implementation for User Story 4

- [ ] T065 [US4] Rewrite `app/services/email.py` per contracts/services.md: `login_code_message` and `deletion_message` build subject and text from `Text` and `str()` them at build time (inside the request); remove `format_utc`, use `format_local_time(moment, None)` (Kyiv, labelled, FR-039); `invitation_message(to, inviter_display, inviter_email, role: Role, detail_lines: Sequence[Text], link, expires_at)` renders the subject and body once under `use_language(Language.UK)` and once under `use_language(Language.EN)`, subject `f"{uk} / {en}"`, text `uk + "\n\n———\n\n" + en`; one whole subject and one opening sentence per role (no `role.lower()`), the inviter in the present tense ("%(inviter)s invites you …"); plain text, no tracking, the link as given (FR-043)
- [ ] T066 [US4] Pass values that render in either language: `app/services/invitations.py` passes `role` (a `Role`) and `Text` detail lines; `app/services/teachers.py:103` builds each detail line as `_("%(institution)s — %(level)s", institution=…, level=access_level.label)`; update the callers in `app/routers/admin_teachers.py` and `app/routers/teacher_students.py`
- [ ] T067 [US4] `scripts/translations.sh update`; translate the email messages (Ukrainian part: «%(inviter)s запрошує вас …», «Запрошення надіслано» style, no gendered word); compile; run T063, T064 and the suite

**Checkpoint**: every email follows the rules of FR-041–FR-043.

---

## Phase 8: User Story 5 - The consent text is bilingual (Priority: P1)

**Goal**: version 1 of each role's consent text is rewritten in place as Ukrainian then English; the
invitation page and the profile show both, marked; acceptance still records version 1.

**Independent Test**: open a teacher's and a student's invitation in each language, accept, open the
profile in each language; check order, headings, `lang` marking and the recorded version.

### Tests for User Story 5

- [ ] T068 [P] [US5] Generalise `tests/unit/test_consent_texts.py` per research R11 and data-model §4: collect `<ROLE>_CONSENT_TEXT_V<n>_REWRITE(_<k>)?` (the unnumbered teams constant is rewrite 1); `published_texts()` takes the highest `k`; `SUPERSEDED` maps each `(role, version)` to the list of every earlier wording's SHA-256 (teacher v1: the original; student v1: the original and rewrite 1); `REWRITES_ALLOWED = {("student", 1): 2, ("teacher", 1): 1}` and none for any other version; the new migration's private downgrade copies hash to the superseded entries; the topic tests check the English part keeps every required topic and both parts carry the "prevails" sentence; set `PUBLISHED` to the **draft** hashes with the comment `# DRAFT: re-pinned after the product owner's approval (T100)`. This draft pin is temporary and only keeps the suite green while the review runs; the pins of FR-050 ("set last, once the wording is approved") are the ones T100 writes, and the pull request is not merged with a DRAFT pin
- [ ] T069 [P] [US5] Create `tests/integration/test_bilingual_consent.py`: a teacher's and a student's invitation page with `sc_lang=uk` and `sc_lang=en` show `<div lang="uk">` with «Українською» before `<div lang="en">` with "English", the rest of the page in the chosen language; accepting in English records the same consent text id and version 1 as accepting in Ukrainian; `/profile` in both languages shows the accepted text in the same order with the same marking; `consent_parts` unit cases: the split, and `None` for a text with no `English` paragraph (rendered whole)

### Implementation for User Story 5

- [ ] T070 [US5] In the migration of T017 add `TEACHER_CONSENT_TEXT_V1_REWRITE_1` and `STUDENT_CONSENT_TEXT_V1_REWRITE_2` (the draft wordings of T008, in the exact data-model §4 shape: paragraphs separated by one blank line, the heading paragraphs `Українською` and `English`), and the private byte-for-byte copies `_TEACHER_CONSENT_TEXT_V1_ORIGINAL` (of `TEACHER_CONSENT_TEXT_V1`, revision `f3bd41a67737`) and `_STUDENT_CONSENT_TEXT_V1_REWRITE_1` (of `STUDENT_CONSENT_TEXT_V1_REWRITE`, revision `09cbcbe472be`); `upgrade` updates the two version-1 rows' `text` in place (keeping `id`, `version`, `published_at`) in the manner of `_write_student_text_v1`; `downgrade` writes back the two copies (FR-049); no consent record is touched (FR-046)
- [ ] T071 [US5] Add `ConsentParts(ukrainian: tuple[str, ...], english: tuple[str, ...])` and `consent_parts(text) -> ConsentParts | None` to `app/services/consent.py`: paragraphs after the paragraph `Українською` and before the paragraph exactly `English`, and after it; `None` when there is no `English` paragraph
- [ ] T072 [US5] Render the parts in `app/templates/pages/invitation.html` and `app/templates/pages/profile.html` exactly as contracts/components.md §7 (headings from the stored text, not the catalogue; a text with no parts rendered whole in the page's language); `app/routers/invitations.py` and `app/routers/profile.py` pass `consent_parts(...)`
- [ ] T073 [US5] Add to `tests/integration/test_migrations.py`: after upgrade both version-1 rows hold the new wordings and `consent_records` is unchanged; after downgrade they hold the teacher original and the student rewrite 1 byte for byte; run T068, T069 and the suite

**Checkpoint**: consent is bilingual with draft wording; final pins wait for approval (T100).

---

## Phase 9: User Story 6 - Ukrainian names sort in alphabetical order (Priority: P2)

**Goal**: every list ordered by a name follows the Ukrainian alphabet in both languages; names that
differ only by an apostrophe variant are duplicates.

**Independent Test**: names covering every Ukrainian letter, Latin names, Russian-only letters, digits
and the five apostrophes, in every list ordered by a name, and duplicate refusals in both languages.

### Tests for User Story 6

- [ ] T074 [P] [US6] Create `tests/unit/test_name_order.py`: `["Яковенко", "Ющенко", "Їжакевич", "Іваненко", "Євтушенко", "Ґудзь", "Гончаренко"]` sorts to Гончаренко, Ґудзь, Євтушенко, Іваненко, Їжакевич, Ющенко, Яковенко; case ignored; Latin names before Cyrillic in their existing order; Ё, Ъ, Ы, Э after я in Unicode order; "5-А" and "«Зоря»" before letters; "Мар'яна", "Мар’яна", "Марʼяна", "Мар‘яна", "Мар`яна" have equal sort keys; `name_key` maps the five apostrophes to ʼ, keeps length, keeps NFC + casefold; `person_sort_key` orders by last then first name; the migration's private `_new_name_key` equals `app.schemas.names.name_key` on these samples; a guard test scanning `app/services/**.py` and `app/routers/**.py` for `.casefold()` or `.name_key` inside a `sorted(`/`.sort(` key (the stored-key assignments aside) (FR-052–FR-054)
- [ ] T075 [P] [US6] Create `tests/integration/test_ukrainian_names.py`: through the services, a second subject, region, institution (same region), class (same institution), live team and live competition (same subject) whose name differs only by an apostrophe variant is refused with the existing duplicate message; the stored name is exactly as typed; the students of a class, the regions, a region's institutions and a competition's teams list in Ukrainian alphabetical order, the same with `sc_lang=uk` and `sc_lang=en` (checked on `/teacher/students` and `/admin/institutions`)

### Implementation for User Story 6

- [ ] T076 [US6] In `app/schemas/names.py` add `APOSTROPHES = frozenset("'’ʼ‘`")`, change `name_key` to NFC → casefold → each apostrophe → `ʼ` (U+02BC), add `name_sort_key(name) -> tuple[tuple[int, int], ...]` exactly per data-model §6 (casefold, apostrophes removed; `(0, code point)` not a letter, `(1, code point)` Latin letter by `unicodedata.name(...).startswith("LATIN")`, `(2, rank)` for the 33 letters «абвгґдеєжзиіїйклмнопрстуфхцчшщьюя», `(3, code point)` any other letter) and `person_sort_key(last, first)`; `subject_name_key` stays an alias; no library (FR-053)
- [ ] T077 [US6] Switch every name sort to the new keys (research R13), with the record id as the last tie-break: `app/services/subjects.py:64,71`; `app/services/competitions.py:224` (`sort_key`'s name tie-break) and `:284`; `app/services/regions.py:65,72`; `app/services/teacher_access.py:132,140`; `app/services/institutions.py:98,149`; `app/routers/admin_teachers.py:141` (by the institution's and region's name keys, not the joined label); `app/services/teachers.py:103` (detail lines by the institution's keys, not the translated text), `:239`, `:265` (`person_sort_key`); `app/services/teams.py:155,237` and `:180` (`person_sort_key`); `app/services/classes.py:89`; `app/services/students.py:174` (`person_sort_key`); `app/services/competition_entries.py:257,424`
- [ ] T078 [US6] In the migration add `_new_name_key` and `_old_name_key` (NFC + casefold) as private copies; `upgrade` (before the consent rows) recomputes `name_key` for `subjects`, `regions`, `institutions`, `classes`, `teams`, `competitions` and updates only the rows whose key changed; `downgrade` (after the consent rows) recomputes the old keys; the clash check comes in T090
- [ ] T079 [US6] Update existing tests that assert the old code-point order (grep the listing tests, e.g. `test_teacher_students.py`, `test_admin_teachers.py`, `test_admin_institutions.py`, `test_teacher_teams.py`, `test_teacher_access_service.py`); add to `tests/integration/test_migrations.py`: on a clean database with a name holding `’`, upgrade recomputes its key and leaves the name unchanged, downgrade restores the old key; run T074, T075 and the suite

**Checkpoint**: names sort in the Ukrainian alphabet and apostrophe duplicates are refused.

---

## Phase 10: User Story 7 - Times read the same way everywhere (Priority: P2)

**Goal**: one format per language on every page; the browser's zone when known, Kyiv time labelled
when not; the milestone 8 formats and the `utc` filter are gone.

**Independent Test**: render every page that shows a time or a date with a known zone, with none, in
each language, and compare.

### Tests for User Story 7

- [ ] T080 [P] [US7] Add to `tests/unit/test_time_zone.py`: both sides of the Kyiv daylight-saving changes (2027-03-28 00:30 UTC → "28 March 2027, 02:30", 01:30 UTC → 04:30; 2027-10-31 00:30 UTC → 03:30, 01:30 UTC → 03:30), "1 March 2027, 00:05", a moment near midnight UTC shown on its Kyiv date by `format_local_date`
- [ ] T081 [P] [US7] Create `tests/integration/test_local_times.py`: with no `sc_time_zone` cookie the competitions list shows "… (Kyiv time)" in English and «… (за київським часом)» with `sc_lang=uk`; with `sc_time_zone=Europe/Kyiv` no label; the competition form's hint reads "Time zone: Europe/Kyiv" (and its Ukrainian translation) and a start posted with no known zone is stored as Kyiv time converted to UTC; the profile's consent record reads "Accepted 22 October 2026, 17:05 …" style, the invitation page's expiry and the administrator's **Teachers** "Date of consent" ("15 October 2026") use the new formats; no page shows "UTC" or a `2026-10-22` style date; every `<time datetime>` stays UTC (`…Z`) (FR-035–FR-040)

### Implementation for User Story 7

- [ ] T082 [US7] Add the macro `local_date(moment, zone=time_zone)` to `app/templates/components/time.html` (`<time datetime="YYYY-MM-DD">` + `format_local_date`, contracts/components.md §4); remove the `utc` filter from `app/core/templates.py`; add a `local_date` sample to the gallery's time section in `app/templates/pages/admin/components.html` (content English)
- [ ] T083 [US7] Replace the three `utc` uses: `app/templates/pages/profile.html:53` → one whole message `_("Accepted %(time)s · %(role)s · version %(version)s", …)` with `local_time(...)`; `app/templates/pages/invitation.html:28` → `_("This invitation expires on %(time)s.", time=local_time(...))`; `app/templates/pages/admin/teachers.html:24` → `local_date(t.consented_at)` with the "Date of consent" label marked; make sure these pages get `time_zone` in their context like the competition pages
- [ ] T084 [US7] Check the competition form (`app/routers/teacher_competitions.py`, `pages/teacher/competition_form.html`): the hidden zone and the hint use `zone_name(time_zone)` (Europe/Kyiv when unknown) and the parsing converts with the submitted zone (FR-037); `scripts/translations.sh update`, translate, compile; run T080, T081 and the suite

**Checkpoint**: no user-facing time shows UTC or the milestone 8 format.

---

## Phase 11: User Story 8 - Ukrainian text is natural and consistent (Priority: P2)

**Goal**: every Ukrainian message uses the glossary, Ukrainian typography, undeclined names and no
gendered guesses.

**Independent Test**: review every Ukrainian message against the glossary and the rules; the automated
wording checks pass.

### Tests for User Story 8

- [ ] T085 [P] [US8] Create `tests/unit/test_ukrainian_wording.py` reading `app/locale/uk/LC_MESSAGES/messages.po` with `read_po`: no Ukrainian translation contains `'`, `’`, `‘` or `` ` `` (only ʼ); none contains `"` or `”`, and every `“` closes a `„` (FR-032); every identifier that holds `“%(x)s”` has a Ukrainian translation holding `«%(x)s»` (or `„%(x)s“` inside «…»); no translation contains a gendered past form about another person from a denylist (запросив, запросила, запрошений, запрошена, додав, додала, створив, створила, видалив, видалила, змінив, змінила, вилучив, вилучила) or the familiar «ти», «твій», «твоя», «твої» (FR-034); every glossary English term used as a whole message identifier ("Teacher", "Student", "Read", "Write", the statuses, the tab names) has the glossary's translation

### Implementation for User Story 8

- [ ] T086 [US8] Review the whole of `app/locale/uk/LC_MESSAGES/messages.po` against the glossary and FR-030–FR-034 and fix it; where one English identifier needs different Ukrainian for different records (e.g. `Delete “%(name)s”?` for a subject, region, institution, class, team, competition, question), give each call site its own `_p(<kind>, …)` / `pgettext` context in the Python or template source, then `scripts/translations.sh update`, translate, compile; run T085 and the suite

**Checkpoint**: the Ukrainian text is ready for the product owner's walk-through.

---

## Phase 12: User Story 9 - The layout holds in Ukrainian (Priority: P2)

**Goal**: no page scrolls sideways or cuts off a control in either language or theme; the pinned frame
stays within its clearances and under a quarter of a 375 × 667 screen in Ukrainian.

**Independent Test**: every page in both languages and themes at 375 px and on a desktop; the frame
measured in Ukrainian at 360 × 640 and 375 × 667.

- [ ] T087 [US9] With headless Playwright (`uv run --with playwright`, a copy of the local database, port 8765), screenshot every page of every role in `uk` and `en`, light and dark, at 375 px and 1280 px; fix any sideways scroll or cut-off button, tab, badge or table header in `app/static/css/app.css` with tokens only (FR-057)
- [ ] T088 [US9] Measure the pinned frame in Ukrainian at 360 × 640 and 375 × 667 on `/admin/teachers` (with the administrator role label shown) and `/teacher/students`; compare with `--sc-frame-clearance` / `--sc-frame-clearance-tabs` and 166.75 px; raise the clearance tokens in `app/static/css/app.css` if outgrown; only if the frame still exceeds a quarter of the screen, apply research R15's fallback (below 768 px the wordmark visually hidden when a role is shown, the logo link keeping `app_name` as its accessible name, `components/frame.html`); update `tests/unit/test_frame_stylesheet.py` for any changed token; record the measurements in `docs/requirements/ui-guidelines.md` §4 (FR-058)

**Checkpoint**: the layout holds in both languages.

---

## Phase 13: User Story 10 - An upgrade stops on names that now clash (Priority: P3)

**Goal**: the upgrade refuses, before any write, when two existing names in one scope become the same
key, and names both records.

**Independent Test**: run the upgrade on a database with two names in one scope that differ only by an
apostrophe, for each kind of named record.

- [ ] T089 [P] [US10] Add to `tests/integration/test_migrations.py`: at revision `04d5b638615c`, seed for each of `subjects`, `regions`, `institutions` (same region), `classes` (same institution), `teams` (both live), `competitions` (both live, same subject) two rows whose names differ only by `'` vs `’` (with distinct old keys); `upgrade` raises `RuntimeError` naming the table, both ids and both names, and no key and no consent text changed; the same pair in different scopes (other region, a deleted team, a cancelled competition) upgrades cleanly
- [ ] T090 [US10] In the migration, before any update, compute the new keys grouped by scope (none; none; `region_id`; `institution_id`; live teams `deleted_at IS NULL`; live competitions per `subject_id`, live = not cancelled and not stopped as in the competitions migration's unique index) and raise `RuntimeError("<table> ids <a> and <b> (“<name a>”, “<name b>”) now have the same name; rename one and upgrade again")` on the first clash (data-model §5, FR-055); run T089

**Checkpoint**: the upgrade is safe on any deployment.

---

## Phase 14: User Story 12 - A developer adds or changes a message (Priority: P3)

**Goal**: the README documents the workflow and the tests fail on any missing, fuzzy or mismatched
translation and any untranslated template literal.

**Independent Test**: follow the README to add a message; remove a translation, mark one fuzzy, change
a placeholder: the suite fails each time.

- [ ] T091 [P] [US12] Create `tests/unit/test_catalogues.py` per research R17: extract with Babel's Python API (`babel.messages.frontend.parse_mapping` on `babel.cfg`, `babel.messages.extract.extract_from_dir`) and the same keyword list as `scripts/translations.sh`; read both `.po` files; assert every extracted message is in both, translated in every plural form, not fuzzy, with the same set of placeholders as its identifier (`%(x)s`, `%(num)d`) in every form; no catalogue entry that is not extracted (no obsolete); no extracted location in `pages/admin/components.html` or `routers/admin_components.py`; the `Plural-Forms` headers exactly as data-model §3
- [ ] T092 [P] [US12] Create `tests/unit/test_template_text.py` per research R17: for every template under `app/templates` except `pages/admin/components.html`, run Jinja's lexer, take the raw `data` tokens, strip tags, comments and entities, and fail on Latin letters left in text content or in `aria-label`, `title`, `alt`, `placeholder` attribute values, reporting file and line; allow-list only `<!doctype html>` and the literal "English" of `language_switch` in `components/frame.html`; fix every literal it finds in the templates and re-run the catalogue update. Add a second test guarding FR-005: no template under `app/templates` contains `lang="ua"`, and no source under `app/` passes `"ua"` as a language (`Language("ua")`, `use_language("ua")`, `sc_lang=ua`); the flag file name `flag-ua.svg` is the only allowed `ua`
- [ ] T093 [US12] Add a **Translations** section to `README.md`: the `DEFAULT_LANGUAGE` setting; how to mark a message in a template (`{{ _("…", name=x) }}`, `ngettext`, `pgettext`) and in Python (`_`, `_n`, `_p` from `app.core.i18n`); `scripts/translations.sh update`, translating the new entries in `app/locale/uk/LC_MESSAGES/messages.po` and clearing "fuzzy", `scripts/translations.sh compile`, `scripts/translations.sh check`; that compiled files are never committed; a link to the message rules in ui-guidelines "Languages" (FR-061)
- [ ] T094 [US12] Verify the guard: delete one Ukrainian translation, mark one entry fuzzy, change a placeholder in one Ukrainian translation, add an unmarked English literal to a template: `uv run pytest tests/unit/test_catalogues.py tests/unit/test_template_text.py` fails each time; restore every file and confirm green

**Checkpoint**: every later milestone is held to both languages.

---

## Phase 15: Polish & Cross-Cutting Concerns

- [ ] T095 [P] `uv run ruff check . && uv run ruff format --check .`; fix
- [ ] T096 Run the whole suite on both engines (`sc-pg` running, `TEST_POSTGRES_URL` set); every milestone 1–12.4 test passes in English apart from the updated ones (SC-013)
- [ ] T097 Walk through [quickstart.md](./quickstart.md) §4 and §5 by hand: the default, the switch with JavaScript off, persistence, every tab of each role in Ukrainian, times with the zone script blocked, emails on the console backend, consent, names, the gallery, and the upgrade stop and downgrade on a database copy; fix what is found
- [ ] T098 Cross-check FR-066 against the tests: every item (catalogues, plurals, genitive months, `lang="uk"` default, the switch on every page without JavaScript, cookie attributes, refused returns, unknown cookie values, the default setting, Ukrainian order and apostrophe duplicates, time formats and Kyiv fallback, email languages, bilingual consent, pins, numbered rewrites, recorded version, English marking) has a named test; `/healthz` is unchanged and untranslated
- [ ] T099 **Product owner acceptance walk-through** (manual, SC-012): on a running instance (quickstart §3), the product owner goes through the milestone's _Acceptance_ list as an administrator, a teacher and a student, in Ukrainian and in English, light and dark, on a phone width and a desktop; every finding (an untranslated text, a wrong term, a declined name, a gendered guess, a layout break) is recorded and fixed in the template, the source or `app/locale/uk/LC_MESSAGES/messages.po`, then `scripts/translations.sh update` and `compile` and the suite; repeat until the product owner reports none
- [ ] T100 **After the product owner approves the Ukrainian consent wordings** (T008; FR-045, FR-050) **and accepts the walk-through** (T099): copy the approved texts into `TEACHER_CONSENT_TEXT_V1_REWRITE_1` and `STUDENT_CONSENT_TEXT_V1_REWRITE_2` in the migration (if the review changed the meaning, change the English wording to match); recompute their SHA-256 and set them in `PUBLISHED` in `tests/unit/test_consent_texts.py`, removing the `DRAFT` comments; delete `specs/012.5-ukrainian-localisation/consent-wording.md` or mark it approved; on delivery, move milestone 12.5 to **Delivered** in `docs/requirements/milestones.md` with a short summary and its spec link, as the other delivered milestones have; run the suite; only then is the pull request merged

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependency. T006 needs T001, T002, T005. T008 can start at once and its
  review runs in the background until T100.
- **Phase 2 (Foundational)**: after Phase 1; blocks every story. T010 → T011 → T012 → T013 → T014
  (T009 first, failing); T015 → T016; T017 any time after T001.
- **US11 (Phase 3)**: after Phase 2; blocks US2 (the switch component) and every translation task
  (the glossary, T026).
- **US1 (Phase 4)**: after US11. **US2 (Phase 5)**: after US1 (the frame's texts) and US11.
- **US3 (Phase 6)**: after US1 (components shared with public pages); independent of US2.
- **US4 (Phase 7)**: after Phase 2 (Kyiv formatter, T015), T052 (`AccessLevel.label`) and T054–T056:
  T066 edits `app/services/teachers.py` (T054), `app/routers/admin_teachers.py` (T055) and
  `app/routers/teacher_students.py` (T056).
- **US5 (Phase 8)**: after T017 and T008's draft; T072 after T032/T061 (same templates).
- **US6 (Phase 9)**: after T017; T077 touches services also edited in T054, so after US3.
- **US7 (Phase 10)**: after US3 (T050's form field) and T072 (same profile/invitation templates).
- **US8 (Phase 11)**: after US3, US4, US7 (all messages exist).
- **US9 (Phase 12)**: after US2 and US3 (every page translated, the switch in place).
- **US10 (Phase 13)**: after T078.
- **US12 (Phase 14)**: after every story that adds messages (US1–US8).
- **Polish (Phase 15)**: after every story; **T100 is last** and gates the merge.

### Within each story

Tests first ([P], seen failing) → model/schema/service → templates and routes → one catalogue task
(update, translate, compile) → run the story's tests and the suite.

### Parallel opportunities

- Phase 1: T002, T003, T004, T007, T008 together.
- Phase 3: T019, T020, T021, T025, T027 together.
- US1: T030–T035 together (different files); T037 after them.
- US3: T050, T051, T053–T061 together (independent file sets); T052 before or after T054, never
  alongside it (both edit `services/classes.py` and `services/competitions.py`); T062 after them.
- US4's tests (T063, T064) can be written alongside US3; its implementation (T065, T066) waits for
  T052 and T054–T056. US5 (T068–T071) and US6's tests and `names.py` (T074–T076) can run alongside
  US3's area tasks. Catalogue tasks (T037, T046, T062, T067, T084, T086) run one at a time.
- US10 and US12 tests (T089, T091, T092) in parallel.

## Parallel Example: User Story 3

```text
Together:  T047 (route sweep), T048 (plural/labels), T049 (entered content)
First:     T052 labels (alone: shares services/classes.py and services/competitions.py with T054)
Together:  T050 components · T051 layouts · T053 schemas · T054 services
           T055 admin · T056 students/classes · T057 teams · T058 questions
           T059 competitions · T060 answers/grades · T061 profile
Then:      T062 catalogue update + Ukrainian translation + compile + suite
```

## Implementation Strategy

### MVP first (Phases 1–5: Setup, Foundational, US11, US1, US2)

1. Tooling and the i18n foundation; the consent draft goes to the product owner.
2. The switch in the library, gallery and guidelines; the glossary written down.
3. US1: signed-out pages and the frame in Ukrainian by default.
4. US2: the switch on every page.
5. **Stop and validate**: quickstart §4 steps 1–3.

### Incremental delivery

1. MVP → demo Ukrainian by default with the switch.
2. US3: every screen of every role.
3. US4, US5: emails and bilingual consent (draft wording).
4. US6, US7, US8, US9: names, times, wording review, layout.
5. US10, US12: upgrade safety and the developer guard.
6. Polish; the product owner's walk-through (T099); after the product owner's approval, T100 pins the
   consent wording and moves the milestone to **Delivered**; then the PR is merged.
