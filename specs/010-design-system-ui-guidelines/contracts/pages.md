# Contract: Pages, Form Errors and Wording (Milestone 10)

**Feature**: [../spec.md](../spec.md) | **Research**: [../research.md](../research.md) D10, D12, D14, D18 | **Components**: [components.md](./components.md)

Every page delivered in milestones 1–9 is rebuilt from the components (FR-039).

- **What stays** (FR-040): addresses, form field names, statuses, texts and access rules. Texts
  change only as listed in §4.
- **What changes**: the markup and the classes.

---

## 1. Page inventory

**Back link** is the `back_link()` at the top of `<main>` (FR-003). "—" means the page is an area's
main page, a top-level page or a public step page, so it has no back link. Where the current page
already has a "Back to …" link, its text and target are reused, and that link moves to the top.

### 1.1 Public and personal pages

| Template | Address | Components | Back link |
|---|---|---|---|
| `login.html` | `GET/POST /login` | page heading; notice (info: "Your account is ready…"); error summary; field `email`; form actions **Send code**; **theme switch**; the "Delete my data" link | — |
| `login_code.html` | `POST /login` (step two), `POST /login/code` | page heading; info notice (code sent); error summary; field `code`; form actions **Sign in**; secondary `post_button` **Send a new code**; link "Use a different email" | — |
| `role_choice.html` | `GET/POST /role` | page heading; error summary (form error); one secondary `button` per role (equal choices, so no primary: FR-025) | — |
| `home.html` | `GET /` | `h1` greeting; one `card` per area; sample questions list, or the empty state "No questions yet."; info notice "Question data is temporarily unavailable…"; `footer_extra`: database status line | — |
| `profile.html` | `GET /profile` | page heading; `details_list`; status badge for a deactivated link or class; consent records as `card`s; `link_button` **Withdraw consent** (destructive) | `/`: "Back to the home page" |
| `profile_withdraw.html` | `GET/POST /profile/withdraw` | `confirmation` (verb **Withdraw consent**); error summary (form error "There is no data stored…") | `/profile`: "Back to your profile" |
| `invitation.html` | `GET/POST /invitations/{token}` | page heading; `details_list`; consent text in a `card`; error summary; name fields; form actions **I agree** | — |
| `invitation_status.html` | the same, final states | page heading; notice (info or error, as the state requires) | — |
| `data_deletion_request.html` | `GET/POST /data-deletion` | page heading; error summary; field `email`; form actions **Send link** | `/login`: "Back to sign in" |
| `data_deletion_requested.html` | `GET /data-deletion/requested` | page heading; success notice | `/login`: "Back to sign in" |
| `data_deletion_confirm.html` | `GET/POST /data-deletion/confirm/{token}` | `confirmation` (verb **Delete my data**) with a `details_list` of what will be deleted; **Cancel** to `/` (the home page signed in, sign-in signed out) | — |
| `link_status.html` | 400/410 link pages | page heading; error notice | — |
| `data_erased.html` | `GET /data-erased` | page heading; success notice | — |
| `error.html` | every 403/404/5xx handler | page heading; paragraph; link "Back to the home page" (unchanged) | — |
| `area.html` | `GET /student`, `GET /staff` | page heading; empty state "The features of this area will arrive in a later milestone." | — |

### 1.2 Administrator area (`layouts/admin.html`, tabs "Administrator area")

| Template | Address | Components | Back link |
|---|---|---|---|
| `admin/teachers.html` | `GET /admin/teachers` | page heading with **Invite teacher**; success notice "Invitation sent…"; data table (name, email, institutions with access badges, status); row actions; empty state | — |
| `admin/teacher_invite.html` | `GET/POST /admin/teachers/invite` | page heading; error summary; fields `email`, `first_name`, `last_name`; institution picker (`picker`); checkbox; form actions **Send invitation** | `/admin/teachers`: "Back to the teachers" |
| `admin/teacher_form.html` | `GET/POST /admin/teachers/{id}` | page heading; error summary; name fields; picker; checkbox; form actions **Save**; `link_button` **Remove** (destructive) | `/admin/teachers`: "Back to the teachers" |
| `admin/teacher_remove.html` | `GET/POST /admin/teachers/{id}/remove` | `confirmation` (verb **Remove**) | `/admin/teachers/{id}`: "Back to {name}" |
| `admin/teacher_not_found.html` | 404 | page heading | `/admin/teachers`: "Back to the teachers" |
| `admin/institutions.html` | `GET /admin/institutions`, `…/regions/{id}` | page heading; `list_detail`. Left: regions with **Create region** and row actions. Right: data table of institutions with **Create educational institution**, status badges, row actions, and the empty states | — |
| `admin/region_form.html` | `GET/POST …/regions/new`, `…/regions/{id}/rename` | page heading; error summary; field `name`; form actions **Save** | `cancel`: "Back to “{region}”", or "Back to the educational institutions" when no region is selected |
| `admin/region_deactivate.html` | `GET/POST …/regions/{id}/deactivate` | `confirmation` (verb **Deactivate**) | `…/regions/{id}`: "Back to “{region}”" |
| `admin/region_delete.html` | `GET/POST …/regions/{id}/delete` | `confirmation` (verb **Delete**), or `refusal` with the **Deactivate** alternative | `…/regions/{id}`: "Back to “{region}”" |
| `admin/institution_form.html` | `GET/POST …/institutions/new`, `…/{id}/rename` | page heading; error summary; field `name`; form actions **Save**; the deactivated-region refusal as an info notice | `cancel`: "Back to “{region}”" |
| `admin/institution_deactivate.html` | `GET/POST …/institutions/{id}/deactivate` | `confirmation` (verb **Deactivate**) | `region_path`: "Back to “{region}”" |
| `admin/institution_delete.html` | `GET/POST …/institutions/{id}/delete` | `confirmation` (verb **Delete**, with the "classes will be deleted too" consequence), or `refusal` with **Deactivate** | `region_path`: "Back to “{region}”" |
| `admin/institutions_not_found.html` | 404 | page heading | `/admin/institutions`: "Back to the educational institutions" |
| `admin/subjects.html` | `GET /admin/subjects` | page heading with **Create subject**; data table (name, status badge, row actions); empty state | — |
| `admin/subject_form.html` | `GET/POST /admin/subjects/new`, `…/{id}/rename` | page heading; error summary; field `name`; form actions **Save** | `/admin/subjects`: "Back to the subjects" |
| `admin/subject_delete.html` | `GET/POST /admin/subjects/{id}/delete` | `confirmation` (verb **Delete**), or `refusal` with the **Deactivate** `post_button` | `/admin/subjects`: "Back to the subjects" |
| `admin/subject_not_found.html` | 404 | page heading | `/admin/subjects`: "Back to the subjects" |
| `admin/placeholder.html` | later tabs | page heading; empty state | — |
| `admin/components.html` (new) | `GET /admin/components` | every component ([components.md §12](./components.md#12-gallery-coverage-checklist-sc-009)) | — |

### 1.3 Teacher area (`layouts/teacher.html`, tabs "Teacher area")

| Template | Address | Components | Back link |
|---|---|---|---|
| `teacher/students.html` | `GET /teacher/students` | page heading; success notice "Invitation sent…"; `chained_lists`; the selected class's heading with a status badge; row actions (**Edit**, **Deactivate**/**Activate**, **Delete**); `link_button` **Add student** (primary); data table of students; empty states and messages | — |
| `teacher/class_form.html` | `GET/POST …/institutions/{id}/classes/new`, `…/classes/{id}/edit` | page heading; error summary; fields `name`, `year_of_study`; form actions **Save** | `cancel`: "Back to “{class}”" when editing, "Back to Students" when creating |
| `teacher/class_deactivate.html` | `GET/POST …/classes/{id}/deactivate` | `confirmation` (verb **Deactivate**) | `cancel`: "Back to “{class}”" |
| `teacher/class_delete.html` | `GET/POST …/classes/{id}/delete` | `confirmation` (verb **Delete**), or `refusal` | `cancel`: "Back to “{class}”" |
| `teacher/student_invite.html` | `GET/POST …/classes/{id}/invite` | page heading; error summary; fields `email`, `first_name`, `last_name`; form actions **Send invitation**; the deactivated-class refusal as an info notice | `cancel`: "Back to “{class}”" |
| `teacher/student_form.html` | `GET/POST /teacher/students/{id}` | page heading; error summary; name fields; select `class_id`; form actions **Save**; `link_button` **Remove** (destructive) | `cancel`: "Back to “{class}”" |
| `teacher/student_remove.html` | `GET/POST /teacher/students/{id}/remove` | `confirmation` (verb **Remove**) | `cancel`: "Back to “{class}”" |
| `teacher/placeholder.html` | `GET /teacher/competitions` | page heading; empty state | — |

### 1.4 Partials kept as includes

`admin/_person_names.html` and `admin/_institution_picker.html` stay as includes, rebuilt from
`field`, `data_table` and `checkbox_field`. The error ids become `{field}-error`, for example
`first_name-error` instead of `first-name-error`. This is a markup change only.

---

## 2. Page structure rules (every page)

1. **Order inside `<main>`**: back link (if any), page heading, error summary or notice, then the
   content.
2. **One `h1`** per page. Section headings are `h2`.
3. **At most one primary action** per page or section. It is either in the page heading or the
   form's primary button.
4. **Tables and empty states**: every list of records is a data table, or an empty state when it is
   empty. No page has a bare `<ul>` of records, except the regions list inside `list_detail`.
5. **Badges**: every status (Active or Deactivated, Read or Write) is a badge with text. The old
   inline "(deactivated)" `small` text becomes `status_badge(False)`.
6. **Destructive actions**: every destructive action goes through a confirmation page that already
   exists (SC-007), except **Deactivate** on the **Subjects** list. That one is a direct
   `POST /admin/subjects/{id}/deactivate` today, with no confirmation page, and stays direct as a
   destructive `post_button` (spec FR-032a; the confirmation is deferred in
   `docs/issues-to-fix.md`). No new direct destructive `POST` is added. The direct **Activate** forms
   stay direct, because activating is not destructive.

---

## 3. Form error mapping

**The rule**: field errors go to `errors[field_id]`, and messages about the whole submission go to
`form_error` (research D10). The messages, the conditions that produce them and the status codes
are unchanged.

| Form (handler) | Field errors (`errors` keys) | Form error (`form_error`) |
|---|---|---|
| Sign in, step one (`auth`) | `email`: "Enter a valid email address." | "Too many attempts. Please try again later."; "Sign-in is temporarily unavailable. Please try again in a moment." |
| Sign in, step two (`auth`) | `code`: "Invalid or expired code. Request a new code if needed." | the too-many and unavailable messages |
| Role choice (`roles`) | none | "Choose one of your roles."; "Choosing a role is temporarily unavailable…" |
| Subject form (`admin_subjects`) | `name`: today's single `error` | none |
| Region form (`admin_institutions`) | `name`: today's `error` | none |
| Institution form (`admin_institutions`) | `name`: today's `error` | none |
| Invite teacher (`admin_teachers`) | `email`, `first_name`, `last_name`, `picker`: as today | as today (`form_error`) |
| Edit teacher (`admin_teachers`) | `first_name`, `last_name`, `picker`: as today | none |
| Class form (`teacher_students`) | `name`, `year_of_study`: as today | none |
| Invite student (`teacher_students`) | `email`, `first_name`, `last_name`: as today | as today (`form_error`) |
| Edit student (`teacher_students`) | `first_name`, `last_name`, `class_id`: as today | none |
| Invitation acceptance (`invitations`) | the name fields, as today | "The consent text has changed since you opened this page. Please read it again." (today's `notice`) |
| Withdraw consent (`profile`) | none | "There is no data stored on your consent to withdraw." |
| Data deletion request (`data_deletion`) | `email`: the validation message | none |

**Every row** shows the error summary whenever the page has at least one error, and keeps every
entered value (SC-006).

---

## 4. Wording changes (FR-040)

These are the only text changes. Any further change found during implementation is added here,
with its rule, before merge (SC-011).

### 4.1 Changed text

| Page | Before | After | Rule |
|---|---|---|---|
| `admin/subjects.html` | **Create** | **Create subject** | FR-006: a button is a verb that says what it does. The spec's own example is "Create subject" (US3). |
| `admin/institutions.html`, regions | **Create** | **Create region** | FR-006, as above |
| `admin/institutions.html`, institutions | **Create** | **Create educational institution** | FR-006, as above. Abbreviations are spelled out. |
| `admin/subjects.html`, status | "Inactive" | "Deactivated" | FR-028: one word for one status everywhere ("Active" or "Deactivated"), as on the other lists |
| `role_choice.html` | "You can switch at any time from the header." | "You can switch at any time from the menu at the top of the page." | FR-006, FR-019: the role switch is now in the user menu, and "header" is jargon |
| `home.html` | the `APP_DESCRIPTION` paragraph in the body | removed from the body; kept as `<meta name="description">` | FR-035: the start page is a greeting and cards. The cards say what each area is for. |
| `home.html` | `h1` "Student Competitions" | `h1` "Welcome to Student Competitions" | FR-035: the home page opens with a greeting |
| `profile.html`, `admin/teacher_*`, `teacher/students.html` | "(deactivated)" in small text | the **Deactivated** badge | FR-028: a status is a badge with text |

### 4.2 New text

| Where | Text | Requirement |
|---|---|---|
| Error summary heading | "There is a problem" | FR-031 |
| Theme switch | legend "Theme"; buttons **Light**, **Dark**, **Device** | FR-014 |
| User menu summary on a phone (visually hidden) | "Account menu" | FR-019 |
| Skip link | "Skip to main content" | research D7 |
| Home page section heading | "Your areas" (unchanged) and the four area descriptions ([data-model.md §4.1](../data-model.md#41-area-approutersareaspy)) | FR-035 |
| `data_deletion_confirm.html` | a **Cancel** link to `/`, which the page did not have | FR-032 |
| Back links that did not exist | "Back to the home page" (profile); "Back to the teachers", "Back to the subjects" and "Back to the educational institutions" (forms); "Back to Students"; "Back to {name}" | FR-003 |

### 4.3 Empty-state hints

| Empty message (unchanged) | Hint (new) |
|---|---|
| "No subjects yet" | "Create the first subject with Create subject." |
| "No regions yet" | "Create the first region with Create region." |
| "No educational institutions yet" | "Create the first one with Create educational institution." |
| "Select a region" | "Choose a region from the list to see its educational institutions." |
| "No teachers yet" (if present) | "Invite the first teacher with Invite teacher." |
| "No questions yet." | none: a milestone-3 sample, removed in milestone 11 |
| The Students tab messages ("Select a region", "Select an educational institution", "Select a class", "No students in this class yet", the no-links message …) | A one-line next step, for example "Choose a class to see its students." or "Add the first student with Add student." Each one is added to this table during implementation, before merge. |
| The placeholder pages ("… will arrive in a later milestone.") | none |
