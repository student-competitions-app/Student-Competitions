# Contract: HTTP Routes (Milestone 12.11)

Every route is in `app/routers/admin_subjects.py`, under `/admin/subjects/{subject_id:int}`,
`@allow_roles(Role.ADMIN)`. Routes run the application-wide `resolve_access` first. The checks
run in spec FR-008 order, and the first failing one decides:

1. **Cross-site** (unsafe methods only): refused, as for every form (milestone 5).
2. **Role**: anyone signed in who is not an administrator gets 403 "access denied", before any id
   is read and before any body is read. An anonymous visitor goes to sign-in.
3. **Subject**: an unknown id gives 404 with `pages/admin/subject_not_found.html`.

## 1. The Subjects tab (changed)

`GET /admin/subjects`. It is the same route, with a changed page:

- **Columns**: Name, Status, **Questions** (from `question_counts`; `0` when the subject has
  none), Actions.
- **Actions**: one `actions_menu(subject.name)` per row, in the order **Rename**
  (`/rename`), **Export questions** (`/questions/export`, `download`), **Import questions**
  (`/questions/import`, destructive), **Deactivate** (`/deactivate`, destructive) on an active
  subject or **Activate** (`/activate`) on a deactivated one, then **Delete** (`/delete`,
  destructive).
- **No `<form>`** on the page apart from the frame's own (sign out, language, theme).

## 2. Deactivate and activate confirmations (new GET, POST unchanged)

| Route | 200 page | Button | Back |
|---|---|---|---|
| `GET /deactivate` | `subject_deactivate.html`: h1 "Deactivate “<name>”?", the consequence "Its questions and every one of its competitions that is not finished are hidden from teachers until it is activated again." | **Deactivate**, destructive, `POST /deactivate` | **Cancel** → `/admin/subjects` |
| `GET /activate` | `subject_activate.html`: h1 "Activate “<name>”?", the consequence "Its questions and its competitions that are not finished are shown to teachers again." | **Activate**, primary, `POST /activate` | **Cancel** → `/admin/subjects` |

- The page is shown whatever the subject's current status.
- `POST /deactivate` and `POST /activate` are unchanged from milestone 6: 303 to
  `/admin/subjects`, and a no-op when the subject already has the status.

## 3. Export

`GET /questions/export`:

- **200** with the body `write_question_csv(export_rows(session, id))` and these headers:
  - `Content-Type: text/csv; charset=utf-8`;
  - `Content-Disposition: attachment; filename="<ascii>"; filename*=UTF-8''<name>`, where the
    name is `export_file_name(subject.name, today_in_kyiv)`, for example
    `History 2026-11-28 question bank.csv` or `Історія 2026-11-28 банк питань.csv`;
  - `Cache-Control: no-store`;
  - `X-Content-Type-Options: nosniff`.
- **404** for an unknown subject.
- It changes nothing and logs nothing. It works for an active and a deactivated subject.

## 4. The import page

`GET /questions/import` answers **200** with `subject_import.html`, built from:

- `confirmation(question=_("Import questions: %(subject)s"), consequence=…, action=…/questions/import,
  verb=_("Replace questions"), cancel_href="/admin/subjects", kind="destructive",
  form_content=True, sends_file=True, summary=…)`. On this page the question is the page's title
  (`h1`).
- The consequence: the count (`ngettext`), "%(subject)s has %(num)d question now." / "…
  questions now.", or "%(subject)s has no questions yet." for `0`. Then "Importing deletes all of
  them and replaces them with the questions of the file. This cannot be undone. Export the
  current questions first to keep them."
- The form content: `file_field("file", _("CSV file"), hint=_("A CSV file in the format
  described in the README, at most 2 MB"), accept=".csv,text/csv", error=file_error)`.

## 5. The import

`POST /questions/import` (`multipart/form-data`, one field `file`). The body is read by the
`uploaded_file` dependency only after steps 1 and 2 above (research R7). Then:

1. Unknown subject: **404** "Subject not found". The body is discarded.
2. `check = check_question_file(upload)`. If there are errors: **400**, the import page again,
   with:
   - the summary `error_summary({"file": check.file_error} if any, row_errors=check.row_errors,
     more=check.more)`;
   - the file field's error set to `check.file_error`, and the field empty;
   - the count read again.

   Nothing is written.
3. `replace_questions(session, id, check.rows)`. `SubjectNotFound` (deleted meanwhile) gives
   **404**. Success gives **303** to `/admin/subjects`.

## 6. Unchanged

- The teacher area's **Questions** tab and every teacher route.
- `POST /deactivate`, `POST /activate`, rename, delete and create.
- The component gallery route, which gains sections only.
