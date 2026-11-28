# Quickstart: Milestone 12.11

This guide shows how to see and check the milestone once it is implemented. The details are in
[contracts/](./contracts/) and [data-model.md](./data-model.md); this guide only runs them.

## 1. Prerequisites

- `uv sync`. There is no new dependency.
- The catalogues compiled: `scripts/translations.sh compile`. The tests compile them themselves.
- For both engines: the local PostgreSQL container running and `TEST_POSTGRES_URL` set (see the
  README's **Test** section). The PostgreSQL cases include the bank-lock checks (research R6).

## 2. Automated checks

```sh
uv run ruff check && uv run ruff format --check
uv run pytest tests/unit/test_question_csv.py
uv run pytest tests/integration/test_question_bank_files_service.py \
              tests/integration/test_admin_question_files.py \
              tests/integration/test_admin_subjects.py \
              tests/integration/test_routes.py tests/integration/test_access_control.py \
              tests/integration/test_component_gallery.py tests/integration/test_form_contract.py
TEST_POSTGRES_URL=postgresql://postgres@localhost:5432/postgres uv run pytest   # whole suite
```

Expected: all green on both engines, with no PostgreSQL case skipped. Research R13 maps every
item of the milestone's _Test:_ line to these modules.

## 3. Seeing it by hand

```sh
uv run alembic upgrade head
ADMIN_EMAILS=admin@example.com uv run uvicorn app.main:app --reload
```

1. **Prepare.** Sign in as `admin@example.com`, then create the subject "Історія". Invite
   yourself as a teacher with **Can manage competitions**, as the README describes, and add three
   questions to "Історія" on the teacher's **Questions** tab, one of them additional.
2. **Subjects tab.** Switch back to the administrator role. The **Questions** column shows `3`.
   Open **Actions**: the five entries are there in order, three of them in the danger colour.
3. **Export.** Choose **Export questions**. The browser saves "Історія <today> банк питань.csv"
   at once, and the page does not change. Open the file:
   - in LibreOffice, the three questions are in order and the additional one has `1`;
   - in Excel, through **Data → From Text/CSV** and, separately, by double-click (research R4,
     the known risk).
4. **Import.** Add two rows in the spreadsheet and save it as CSV. In Excel with a Ukrainian
   regional setting, it is saved with semicolons. Choose **Import questions**: the page says that
   Історія has 3 questions now and warns you. Choose the file and press **Replace questions**.
   The tab shows `5`. As the teacher, the **Questions** tab lists the five questions under new
   numbers.
5. **Errors.** Empty an answer in row 4, put `так` in `additional` in row 5, and import. The page
   shows "Row 4: Enter the reference answer." and "Row 5: Additional must be 0, 1 or empty.". The
   file field is empty, and the count is still 5.
6. **README example.** Copy the `csv` block of the README section "Question bank CSV files" into
   a `.csv` file and import it. It succeeds, and the additional question is marked on the
   teacher's tab.
7. **Deactivate and activate.** Both entries open their confirmation pages, and **Cancel**
   changes nothing.
8. **Access.** As the teacher, open `/admin/subjects/<id>/questions/export`. The answer is
   "access denied".

## 4. Manual step of the implementation (spec FR-062)

- **Screenshots** with headless Playwright, as described in the project's browser-screenshot
  notes: the **Import questions** page clean and with errors, and the gallery's file field. Each
  is taken in Ukrainian and English, light and dark, at desktop width and at 360 px.
- **The product owner** approves the look of the file field and the import page from these
  screenshots.
- **The Excel check**: the product owner opens an exported file in Excel and records the result
  of the double-click (research R4).
- **The timings**: the import of 1,000 questions and its export, measured once against SC-009
  (research R11).
