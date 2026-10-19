# Contract: HTTP Routes — Teacher Area, Students, Admin Confirmations (Milestone 9)

**Feature**: [spec.md](../spec.md) | **Research**: [research.md](../research.md) D5–D8, D11, D12, D14–D17

There are two new router modules, `app/routers/teacher.py` and `app/routers/teacher_students.py`.
There are small changes to `admin_institutions.py`, `profile.py`, `areas.py` and two templates.

- **Pages**: plain links and `GET` forms only, with no script and no HTMX (research D7).
- **Changes**: every change is a `POST` through the application-wide cross-site check (FR-055).
- **After success**: every successful `POST` answers `303`: Post/Redirect/Get (FR-056).

## Access summary

| Group | Declared | Anonymous `GET` / `POST` | Wrong current role | Teacher, object out of reach |
|---|---|---|---|---|
| Teacher area (`/teacher…`) | `@allow_roles(Role.TEACHER)` | `303 /login?next=…` / `303 /login` | `403` "Access denied", nothing changes | `403` "Access denied", nothing changes |
| Admin deactivation confirmations | `@allow_roles(Role.ADMIN)` | as above | `403` | n/a |
| Profile (`/profile`) | unchanged (`ALL_ROLES`) | as above | n/a | n/a |
| Invitation pages | unchanged (`PUBLIC_ROUTES`) | served | served | n/a |

**"Out of reach"** (research D5) means any of these:

- an id that is not an ASCII integer, or is unknown;
- an institution the teacher is not linked to, or one that is not available;
- a class that is not in the named institution, or an institution that is not in the named region;
- a student whose class is not available, or who is not enrolled in a reachable institution;
- a management action (any `POST`, and every form or confirmation page) on an institution where
  the teacher has only Read access.

The 403 page is the milestone 5 page (`AccessDenied(Role.TEACHER)`). It names the current role and
nothing about the object.

**`PUBLIC_ROUTES`**: unchanged.

**`test_the_write_routes_are_exact` gains** (8):

```text
POST /teacher/students/institutions/{institution_id:int}/classes
POST /teacher/students/classes/{class_id:int}/edit
POST /teacher/students/classes/{class_id:int}/deactivate
POST /teacher/students/classes/{class_id:int}/activate
POST /teacher/students/classes/{class_id:int}/delete
POST /teacher/students/classes/{class_id:int}/invite
POST /teacher/students/{user_id:int}
POST /teacher/students/{user_id:int}/remove
```

**New `GET` routes** (11):

- 9 in the teacher area: Students, Competitions, the new-class form, the class edit form, the
  class deactivate and delete confirmations, the invite form, the student edit form, and the
  student remove confirmation;
- 2 in the administrator area: the region and institution deactivate confirmations.

`GET /teacher` changes from a placeholder page to a redirect.

---

## 1. The teacher area shell — `app/routers/teacher.py`

| Method | Path | Answer |
|---|---|---|
| GET | `/teacher` | `303 /teacher/students` (FR-047) |
| GET | `/teacher/competitions` | `200`: `pages/teacher/placeholder.html`, with the Competitions tab current: "Competitions will arrive in a later milestone." |

- **Tabs**: `TEACHER_TABS`, rendered by `layouts/teacher.html` through `render_teacher`. They are
  ordinary links, and the current tab has `aria-current="page"`.
- **Home page**: it keeps its "Teacher area" link to `/teacher` (`areas.TEACHER_AREA`).

---

## 2. The Students tab — `app/routers/teacher_students.py`

Every page renders through `render_teacher` with the **Students** tab current. Every route is
`@allow_roles(Role.TEACHER)` and acts as `request.state.user`.

### 2.1 `GET /teacher/students` — choose a class, see its students

Query parameters, read as strings: `region`, `institution`, `class`, `sent`. An empty value counts
as absent.

| Input | Answer |
|---|---|
| no reachable institution at all | `200`, all three lists disabled, "You are not linked to any educational institution" |
| no parameters | `200`, Region enabled, "Select a region to continue" |
| `region` reachable | `200`, Institution enabled, "Select an educational institution to continue" |
| `+ institution` reachable, in the region | `200`, Class enabled, "Select a class to see its students"; Write adds the **+ Add class** entry (`value="new"`) |
| `+ class=new`, Write | `303 /teacher/students/institutions/{i}/classes/new` |
| `+ class=new`, Read | `403` |
| `+ class` of the institution, active | `200`: the class bar, then the student list or "No students in this class yet" |
| `+ class` of the institution, deactivated | `200`: the bar marked "Deactivated", then "This class is deactivated; its students are hidden until it is activated again" |
| any parameter out of reach, or a child without its parent | `403` |

**Lists** (FR-048), sorted ignoring case, ties by id:

- **Region**: active regions holding at least one available, linked institution.
- **Educational institution**: "Name — Read" or "Name — Write".
- **Class**: every class of the institution, "KN-21 · year 2", with "(deactivated)" appended to
  deactivated ones.

**Three `GET` forms** (research D7) target `/teacher/students`, each with a **Show** button:

- **Region** submits `region`;
- **Institution** submits a hidden `region` and `institution`;
- **Class** submits hidden `region` and `institution`, and `class`.

The selected option of each list is the current one. A disabled list's button is disabled too.

**Class bar** (FR-051): the class label, marked if deactivated. With Write access it has these
actions, each with the selection carried in the link's query (`?region=…&institution=…`):

- **Edit**: link to `/teacher/students/classes/{c}/edit`;
- **Deactivate**: link to the confirmation;
- **Activate**: a form button posting directly;
- **Delete**: link to the confirmation;
- **Add student**: link, only while the class is active.

With Read access, the bar has no actions.

**Student list** (FR-054), for an active class only:

- sorted by last name, then first name, ignoring case, ties by id;
- one row per student: "Last First" and the email;
- with Write access, each row has **Edit** (`/teacher/students/{u}`) and **Remove**
  (`/teacher/students/{u}/remove`).

**Banner**: a valid `sent` (purpose `invitation-sent`, 10 minutes) shows "Invitation sent to
<email>". Any other value is ignored.

### 2.2 Classes

Every page in this section requires the institution to be reachable with **Write** access.
Otherwise the answer is `403`. Every redirect target is
`/teacher/students?region=R&institution=I&class=C`, written below as `→ selection(C)`.

| Method | Path | Success | Refused |
|---|---|---|---|
| GET | `/teacher/students/institutions/{institution_id:int}/classes/new` | `200` form: name, year of study; heading "New class in “Name”" | |
| POST | `/teacher/students/institutions/{institution_id:int}/classes` | `303 → selection(new class)` (US1-6) | `400`: form again with errors and values (invalid name or year, "A class named “…” already exists in this institution.") |
| GET | `/teacher/students/classes/{class_id:int}/edit` | `200`: the same form, filled | |
| POST | `/teacher/students/classes/{class_id:int}/edit` | `303 → selection(C)` | `400` as for create |
| GET | `/teacher/students/classes/{class_id:int}/deactivate` | `200` confirmation: "Deactivate class “KN-21”? Its students will be signed out and hidden until the class is activated again." (FR-052) | |
| POST | `/teacher/students/classes/{class_id:int}/deactivate` | `303 → selection(C)`; a no-op if already deactivated | |
| POST | `/teacher/students/classes/{class_id:int}/activate` | `303 → selection(C)`; a no-op if already active | |
| GET | `/teacher/students/classes/{class_id:int}/delete` | `200` confirmation naming the class and its institution (FR-053) | |
| POST | `/teacher/students/classes/{class_id:int}/delete` | `303 → selection(none)`: region and institution kept, no class | `409`: the confirmation page in its refused state, "“KN-21” has students and cannot be deleted." While the class is active it adds "You can deactivate it instead." and a **Deactivate** link (US1-13) |

- Only `name` and `year_of_study` are read from the class form. Any other field, such as an
  institution, is ignored (FR-003).
- The forms' **Cancel** links go back to the selection.

### 2.3 Inviting a student

| Method | Path | Success | Refused |
|---|---|---|---|
| GET | `/teacher/students/classes/{class_id:int}/invite` | `200` form: email, first name, last name. It shows the class and the institution as text. | `409` for a deactivated class: "This class is deactivated. Students cannot be added to it." with no form |
| POST | `/teacher/students/classes/{class_id:int}/invite` | `303 → selection(C)&sent=<sealed>` | see the order below |

**Order of checks** (research D11); the first failure answers:

1. Reach with Write, else `403`.
2. The class is active, else `409`.
3. Email and names are valid, else `400` with every error and value.
4. The limits allow it (`invite_student_inviter` 100/h, `invite_email` 5/h), else `429` "Too many
   invitations. Please try again later."
5. The address is not a student's, else `400` "This email already belongs to a student".
6. Sending:
   - an email delivery failure gives `503` "The invitation email could not be sent. Please try
     again.";
   - a lost race (`InvalidChoice`) gives `403`.

On every `400`, `409`, `429` and `503`, the form is shown again with the values as typed. Nothing is
stored.

### 2.4 A student

Every page here requires the student to be reachable and the access level to be **Write**.
Otherwise the answer is `403`. The query `?region=…&institution=…&class=…` is carried through for
the redirect. If it is missing or out of reach, the redirect uses the student's own class.

| Method | Path | Success | Refused |
|---|---|---|---|
| GET | `/teacher/students/{user_id:int}` | `200` form: first name, last name, and a class select of the **active** classes of the same institution, the current class selected. The email and the institution are shown as text (FR-041, US4-3). | |
| POST | `/teacher/students/{user_id:int}` | `303 → selection(the class the teacher was viewing)` | `400`: form again with errors and values (invalid name; "This class is deactivated."); `403` for a class of another institution or an unknown class (US4-5) |
| GET | `/teacher/students/{user_id:int}/remove` | `200` confirmation naming the student, the class and the institution (FR-043) | |
| POST | `/teacher/students/{user_id:int}/remove` | `303 → selection(C)` | |

- Only `first_name`, `last_name` and `class_id` are read from the edit form. An email or
  institution field is ignored.
- `class_id` is read as a string, so a value that is not an integer gives `403`, never a 422.

---

## 3. Administrator area — `app/routers/admin_institutions.py` (CHANGED)

| Method | Path | Answer |
|---|---|---|
| GET | `/admin/institutions/regions/{region_id:int}/deactivate` | NEW. `200` confirmation: "Deactivate region “Odesa”? Its students will be signed out and hidden until it is activated again." **Deactivate** posts to the existing `POST`; **Cancel** returns to the region. `404` region-not-found page as elsewhere. |
| GET | `/admin/institutions/regions/{region_id:int}/institutions/{institution_id:int}/deactivate` | NEW. The same for an institution, naming it and its region. `404` pages as elsewhere. |
| POST | the same two paths | Unchanged answers. The services now also sign out the students below (research D4). |
| GET | `…/institutions/{institution_id:int}/delete` | CHANGED. When the institution has classes: "Its N classes will be deleted too." (FR-007). In the "in use" state, the **Deactivate** offer is a link to the confirmation. |
| POST | `…/institutions/{institution_id:int}/delete` | CHANGED. The in-use check counts enrolled students, blocked ones included, and the institution's classes are deleted with it (research D14). Refusal stays `409` "in use". |

In `institutions.html`, the **Deactivate** of regions and institutions becomes a link to the
confirmation. **Activate** stays a form button.

---

## 4. Profile — `app/routers/profile.py` (CHANGED)

`GET /profile`, for a person who holds the student role, blocked or not, adds:

- "Educational institution: Name (Region)";
- "Class: KN-21";
- "Year of study: 2";
- " (deactivated)" after the class while it is not available (FR-045).

The correction notes (FR-046):

- for a student: "Corrections to student data are made by a teacher of your educational
  institution.";
- for a teacher: "Corrections to teacher data are made by an administrator." (unchanged).

Withdrawal is unchanged in its routes. The plan page lists "Student" among the roles to remove.

---

## 5. Invitation pages — `app/routers/invitations.py` (template change only)

- `pages/invitation.html` adds "If you are already a teacher or a student, your current names are
  kept." for every role (FR-038).
- A student invitation's detail lines are "Educational institution: Name (Region)" and "Class:
  KN-21 · year 2" (research D9).
- "Already a student" uses the existing `AlreadyHeld` page: "You are already a student." (FR-034).

---

## 6. Sign-in — `app/routers/auth.py` (no route change)

A blocked student with no other role is treated as an unknown address:

- no code is sent, and the response is identical to any other;
- an existing code no longer verifies.

A blocked student with another role signs in without the student role being offered (research
D3).

---

## 7. Status codes used

| Code | Meaning here |
|---|---|
| `200` | A page or form |
| `303` | After every successful `POST`; `/teacher` → `/teacher/students`; `class=new` → the new-class form |
| `400` | A form with invalid values, a duplicate class name, or an address that is already a student's |
| `403` | Wrong role, or a teacher reaching beyond their links or access level (including unknown ids) |
| `404` | Admin pages only: region or institution not found (milestone 7) |
| `409` | A class that holds students cannot be deleted; a deactivated class takes no students; an institution in use |
| `429` | An invitation limit was reached |
| `503` | The invitation email could not be sent |
