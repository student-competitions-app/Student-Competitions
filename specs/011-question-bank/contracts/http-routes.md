# Contract: HTTP routes (Milestone 11)

The router is `app/routers/teacher_questions.py`, with `prefix="/teacher/questions"`.

- **Every route** is `@allow_roles(Role.TEACHER)`, acts as `request.state.user`, and renders
  through `render_teacher(..., active_tab="questions")`.
- **Thin handlers**: they parse strings, call `app.services.questions`, map the outcomes and
  redirect with 303 after a change.
- **Logging**: nothing is logged except by the services (ids only).

Decisions: [research.md](../research.md) R5–R9, R11.

## Tabs

`app/routers/teacher.py`:

```python
TEACHER_TABS = (
    TeacherTab("students", "Students", "/teacher/students"),
    TeacherTab("questions", "Questions", "/teacher/questions"),
    TeacherTab("competitions", "Competitions", "/teacher/competitions"),
)
```

`GET /teacher` still answers `303 /teacher/students` (FR-010).

## Order of checks (every route)

1. **Role**: administrator or student gets **403** (milestone 5 page, names the current role).
2. **Setting**, on the routes marked *manage* below: no `can_manage_competitions` gives **403**
   (`AccessDenied(Role.TEACHER)`). This is decided before any query value, form value or database
   id is read, so an unknown or deleted id also gets 403.
3. **Ids**:
   - a `subject` value that is not an ASCII integer ≤ `MAX_ID`, or an unknown or deactivated
     subject, gets **404** "Subject not found" on manage routes, and counts as no selection on the
     list;
   - an unknown question, a deleted question, or a question of a deactivated subject gets **404**
     "Question not found".
4. **Fields**: **400** with the form shown again.
5. **The service write** re-checks steps 2 and 3 under lock. A refusal there maps to the same 403 or
   404.

A path id that is not an integer matches no route and gets the application's 404 for everyone.

## Helper

```python
def list_path(subject_id: int, page: int = 1, anchor: int | None = None) -> str:
    """/teacher/questions?subject=<id>[&page=<n> when n > 1][#question-<anchor>]"""
```

- **Every redirect and every Cancel or back link** to the list is built by this helper, from
  server-side values only (FR-035).
- **`page`**: a value read from the request has already been through `paging.parse_page`.

## Routes

### `GET /teacher/questions`: the tab (all teachers)

**Query**:

- `subject`: optional string;
- `page`: optional string.

Both are read as strings, so no input ever gets a 422.

**Selection** (R11):

- **The subject** is the valid active subject in `subject`. If there is none and exactly one subject
  is active, that one. Otherwise none.
- **The page** is `parse_page(page)`, clamped to `1..last` (R9).

**The page, top to bottom**:

1. **The page heading**: `page_heading("Questions", action=("Add question",
   "/teacher/questions/new?subject=<id>&page=<current page>"))`. The action is shown only with the
   setting and a selected subject; otherwise the heading has no action (FR-021).
2. **The subject list**: `chained_lists` with one level (`subject`), the active subjects, the
   selected one marked, and a `<noscript>` **Show** button.
3. **One of the following**:
   - **No active subject**: `empty_state("No subjects yet", "Ask an administrator to add a
     subject.")`.
   - **No selection**: `empty_state("Select a subject", "Choose a subject in the list above to see
     its questions.")`.
   - **A subject with no listed question**: `empty_state("No questions yet", hint)`. The hint is "Add
     the first question with Add question." with the setting; without it there is no hint.
   - **Otherwise**:
     - `page_navigation(paging, list_path(subject)&page=, "Questions", "Pages, top")`;
     - `<ol class="question-list">`, one `text_card` per question, in the order of the next
       section;
     - `page_navigation(..., "Pages, bottom")`.

**Each question**, in a `text_card("Question <number>", id="question-<number>")`:

- `text_box("Question", text)`;
- `text_box("Reference answer", reference_answer)`;
- with the setting, a `row-actions` row:
  - `link_button("Edit", "/teacher/questions/<id>/edit?page=<p>", kind="secondary", small=True)`;
  - `link_button("Delete", "/teacher/questions/<id>/delete?page=<p>", kind="destructive",
    outline=True, small=True)`.

The texts are escaped, and their line breaks are kept (`.keep-lines`).

**Status**: 200. Opening the page changes nothing.

### `GET /teacher/questions/new`: the add form (*manage*)

**Query**:

- `subject`: required, a valid active subject, otherwise 404 "Subject not found";
- `page`: the return page, parsed;
- `saved`: `"1"` shows the notice.

**The page**:

- the back link `list_path(subject, page)` "Back to the questions";
- the heading "Add question";
- `error_summary`;
- with `saved=1`, `notice("The question was saved.", "success")`;
- "Subject: <name>" as text, not a control (FR-026);
- a form posting to `/teacher/questions`, with:
  - hidden `subject` and `page`;
  - `textarea_field("text", "Question", ...)`;
  - `textarea_field("reference_answer", "Reference answer", ...)`, both with `required` and
    `maxlength="2000"`, and the hint "Up to 2,000 characters.";
  - `form_actions("Save question", cancel_href=list_path(subject, page), name="then",
    value="list", secondary={"label": "Save and add one more question", "name": "then", "value":
    "another"})`.

**Status**: 200.

### `POST /teacher/questions`: add (*manage*)

**Form**: `subject`, `page`, `text`, `reference_answer`, `then`. Any other field is ignored.

**Outcomes**:

| Case | Response |
|---|---|
| No setting | 403 |
| Unknown or deactivated subject, or `subject` not an id | 404 "Subject not found"; nothing stored |
| Field errors | 400, the form again with each error beside its field and in the summary, the values as typed, no notice |
| Saved, `then=another` | 303 → `/teacher/questions/new?subject=<id>&page=<page>&saved=1` |
| Saved, any other `then` | 303 → `list_path(subject)` (the top of page 1; the new question is first) |

### `GET /teacher/questions/{question_id:int}/edit`: the edit form (*manage*)

**Query**: `page`, the return page.

**The question**: an unknown question, a deleted question or a question of a deactivated subject
gets 404 "Question not found".

**The page**:

- the back link `list_path(subject, page, anchor=id)` "Back to the questions";
- the heading "Edit question <number>";
- "Subject: <name>" as text;
- a form posting to `/teacher/questions/<id>/edit`, with:
  - hidden `page`;
  - the two textareas, filled with the stored values;
  - `form_actions("Save question", cancel_href=list_path(subject, page, anchor=id))`, with no
    second button.

**Status**: 200.

### `POST /teacher/questions/{question_id:int}/edit`: edit (*manage*)

**Form**: `page`, `text`, `reference_answer`. A `subject` field or any other field is ignored
(FR-031, US3-5).

**Outcomes**:

| Case | Response |
|---|---|
| No setting, including a setting removed after the form opened | 403; nothing changes (US5-6) |
| Unknown, deleted, or its subject deactivated, including after the form opened | 404 "Question not found"; nothing changes (US5-5) |
| Field errors | 400, the form again with the errors and the values as typed |
| Saved | 303 → `list_path(subject, page, anchor=id)` |

### `GET /teacher/questions/{question_id:int}/delete`: the confirmation (*manage*)

**Query**: `page`, the return page. The question checks are the same as on the edit form.

**The page**:

- the back link `list_path(subject, page, anchor=id)`;
- `confirmation("Delete question <number>?", "The question will be hidden from this list and can no
  longer be added to new competitions. It is not erased, but it cannot be restored.",
  "/teacher/questions/<id>/delete", "Delete", list_path(subject, page, anchor=id))`.

The confirmation names the question by its number and shows nothing else (FR-033).

**Status**: 200.

### `POST /teacher/questions/{question_id:int}/delete`: delete (*manage*)

**Form**: none read.

**Outcomes**:

| Case | Response |
|---|---|
| No setting | 403 |
| Unknown, already deleted, or its subject deactivated | 404 "Question not found" |
| Deleted | 303 → `list_path(subject, landing.page, anchor=landing.question_id)`; with no question left, `list_path(subject)` (R8) |

## The not-found page

`pages/teacher/question_not_found.html`, status 404, in the teacher frame with **Questions** current.

| Heading | Text |
|---|---|
| Subject not found | This subject does not exist or is deactivated. |
| Question not found | This question does not exist, was deleted, or its subject is deactivated. |

Its back link is `/teacher/questions`, "Back to the questions".

## Changed routes and pages (outside the router)

| Where | Change |
|---|---|
| `GET /` (`pages.home`) | No question list. The database line stays, and so does the unavailable notice, unchanged (FR-043). |
| `areas.TEACHER_AREA.description` | "Manage your classes and students, and see the question bank." (FR-044) |
| `GET/POST /admin/teachers/invite`, `GET/POST /admin/teachers/{id}` | The checkbox `name`/`id` becomes `can_manage_competitions`, labelled "Can manage competitions". |
| `GET /admin/teachers` | The column is headed "Can manage competitions". |
| `GET /invitations/{token}` (teacher) | The detail line reads "Can manage competitions: Yes" or "No". The explanation reads "You will be able to manage competitions and change the question bank." or "You will not be able to manage competitions or change the question bank." |
| The invitation email (teacher) | The same lines as the acceptance page. |
| `GET /profile` | The details label reads "Can manage competitions". |
| `GET/POST /admin/subjects/{id}/delete` | Unchanged pages. A subject with any question, deleted ones included, now gets the 409 refusal. |

## Route table changes (tests)

- **Writes added** to `test_the_write_routes_are_exact`:
  - `("POST", "/teacher/questions")`;
  - `("POST", "/teacher/questions/{question_id:int}/edit")`;
  - `("POST", "/teacher/questions/{question_id:int}/delete")`.
- **Pages requiring the setting**: `/teacher/questions/new`,
  `/teacher/questions/{question_id:int}/edit` and `/teacher/questions/{question_id:int}/delete`. The
  generic sweep cannot check them with the cast teacher, who has no profile and therefore gets 403.
  - **In the sweep**: they join the skipped set, with a guard test that names them.
  - **Elsewhere**: `test_teacher_questions.py` checks them with a real teacher who has the setting.
- **`PUBLIC_ROUTES`** is unchanged.
