# Quickstart: validating Ukrainian Localisation (Milestone 12.5)

How to prove the milestone works, automatically and by hand. Details live in [spec.md](./spec.md),
[data-model.md](./data-model.md) and the [contracts](./contracts/).

## 1. Prerequisites

```sh
uv sync                                   # installs Babel with the other dependencies
scripts/translations.sh compile           # builds app/locale/*/LC_MESSAGES/messages.mo
uv run alembic upgrade head               # applies the 12.5 revision
```

Optional, both engines: start the `sc-pg` container and set `TEST_POSTGRES_URL`.

## 2. Automated checks

```sh
uv run ruff check . && uv run ruff format --check .
uv run pytest                              # compiles the catalogues first, runs in English
uv run pytest tests/unit/test_catalogues.py tests/unit/test_template_text.py \
  tests/unit/test_i18n.py tests/unit/test_name_order.py tests/unit/test_consent_texts.py \
  tests/integration/test_language.py tests/integration/test_localised_emails.py \
  tests/integration/test_bilingual_consent.py tests/integration/test_migrations.py
```

Expected: every test passes; the catalogue test reports no missing, fuzzy, obsolete or mismatched
message.

## 3. Run the application

```sh
uv run uvicorn app.main:app --reload       # DEFAULT_LANGUAGE unset → Ukrainian
```

Sign in with an administrator from `ADMIN_EMAILS`; the code is printed by the console email backend.

## 4. By hand (both languages × both themes × 375 px and desktop)

For browser screenshots use headless Playwright (`uv run --with playwright …`) against a copy of the
local database on port 8765, as in earlier milestones.

1. **Default**: a fresh browser profile with English as its language opens `/login` in Ukrainian;
   the page source has `<html lang="uk">`.
2. **Switch**: on `/login`, the competitions list with a subject, status and page, an error page and
   a form shown after an error, choose **English** and **Українська**; the page and its query stay;
   with JavaScript disabled too. At 375 px the closed switch shows the flag only.
3. **Persistence**: choose English, sign in, switch role, sign out: still English.
4. **Every tab** of the administrator, teacher and student in Ukrainian: no English text other than
   entered data; glossary terms; «…» quotes; no gendered verb about another person; plural forms in
   region headers and progress lines.
5. **Times**: with the time-zone script blocked (DevTools → disable JavaScript, clear
   `sc_time_zone`), competition starts read «… (за київським часом)»; the form hint says
   "Europe/Kyiv"; the profile and **Teachers** list use the new format.
6. **Emails** (console backend): the sign-in code and deletion link in the chosen language, the
   deletion expiry in Kyiv time labelled; an invitation in Ukrainian then English, subject in both.
7. **Consent**: an invitation page in each language shows «Українською» then "English"; accept;
   the profile shows the same.
8. **Names**: create students "Яковенко", "Іваненко", "Ґудзь", "Євтушенко", "Їжакевич", "Ющенко",
   "Гончаренко" in a class: the list follows that alphabetical order. Create a region "Мар'янівка",
   then "Мар’янівка": refused as a duplicate.
9. **Frame**: measure the pinned frame in Ukrainian at 360 × 640 and 375 × 667 on
   `/admin/teachers` and `/teacher/students` with the administrator role shown; compare with
   `--sc-frame-clearance(-tabs)` and 166 px; record the numbers in `ui-guidelines.md` §4.
10. **Gallery**: `/admin/components#language` shows the switch closed and open; the rest of the
    gallery stays English.

## 5. Upgrade safety

On a copy of a database with two regions "Мар'янівка" and "Мар’янівка", `alembic upgrade head`
stops and names both; rename one, upgrade again; `alembic downgrade -1` restores the old keys and the
earlier consent wordings.

## 6. Product owner acceptance

The product owner approves the Ukrainian consent wordings (the glossary, research R14, is approved); the pins
are then set and the walk-through of the milestone's _Acceptance_ list is done in both languages.
