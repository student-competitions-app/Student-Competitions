# Quickstart: Validate Classes and Students (Milestone 9)

**Feature**: [spec.md](./spec.md) | **Routes**: [contracts/http-routes.md](./contracts/http-routes.md) |
**Services**: [contracts/services.md](./contracts/services.md) | **Data**: [data-model.md](./data-model.md)

This guide proves the milestone works. It runs the automated suite first, then a manual
walk-through in a browser, then a check after deployment.

## Prerequisites

- The repository set up as in the README ("Getting started"): `uv sync`. This milestone adds no
  dependency and no configuration variable.
- Optional, to run the PostgreSQL half of the suite: a local PostgreSQL server and
  `TEST_POSTGRES_URL` (README, "Test"). The row locks (research D5, D8, D12) and the foreign-key
  backstops (class deletion, institution deletion) matter only on PostgreSQL.

## 1. Automated checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Expected: all green on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL` is set. The tests
for this milestone, mapped to the spec (FR-058):

| Test module | Proves |
|---|---|
| `tests/unit/test_class_schemas.py` | Year of study: 1 and 12 accepted, `02` → 2; empty, 0, 13, `2.5`, `+2`, text and non-ASCII digits refused |
| `tests/unit/test_consent_texts.py` (changed) | Student consent text v1 pinned by SHA-256; it never names an institution or a class |
| `tests/integration/test_availability.py` | Every level of the chain: deactivating a class, an institution or a region blocks the students below, signs them out, and keeps every status and enrolment. Reactivating restores exactly the objects whose own status is active. An institution reactivated while its class stays deactivated keeps the students blocked (US5, SC-005). |
| `tests/integration/test_teacher_classes.py` | The tab shell (`/teacher` → Students, Competitions placeholder, tab highlighted). The three lists and every message. Region and institution filtering and order. Create, edit (case-only rename), deactivate with confirmation, activate, and delete (empty, in use, the deactivation hint only when active). Every validation error. Selection kept after reload and after each action. Read institution shows no actions (US1). |
| `tests/integration/test_student_invitation.py` | **End to end**: invite into an active class → outbox link → `GET` stores nothing → **I agree** creates the user, the student role, the enrolment and the consent record → sign-in page prefilled → the student signs in and the profile shows the institution, class and year. Email content. The existing-student check, never naming the institution or class. Teacher, administrator and inactive former student can be invited. The 100 per teacher limit and the shared 5 per address limit, counted separately from teacher invitations. A send failure keeps the values and counts (US2). |
| `tests/integration/test_student_invitation_refusals.py` | Tampered, expired. The inviter lost Write, the link, the teacher role, or is inactive. The class was deleted, or its class, institution or region was deactivated. A renamed class or a changed year is shown and accepted. A cut-off after removal or withdrawal. Already a student. The consent text changed. Extra form fields ignored. The teacher-only checks are not applied (US3). |
| `tests/integration/test_teacher_students.py` | The list order and contents. **Edit** names and move to an active class of the same institution: the student stays signed in, no new consent. A move to a deactivated class or to another institution is refused. **Remove** without and with another role: role, enrolment, cut-off, deactivation and sign-out. A removed student is re-invited with a newer link. Student removed while the Edit is open → 403 (US4). |
| `tests/integration/test_names_on_acceptance.py` | A teacher accepting a student invitation and a student accepting a teacher invitation keep their names and gain the role. A new person, an inactive person, and an administrator with neither role get the invited names. The note is on both acceptance pages (US6, SC-007). |
| `tests/integration/test_profile.py` (changed) | Student profile shows the enrolment and the student correction note. A blocked teacher-and-student sees the enrolment marked deactivated and no Student role. Withdrawal and **Delete my data** delete the enrolment, and the student disappears from the teacher's list (US7). |
| `tests/integration/test_login_flow.py` (changed) | A blocked student with no other role: no code is sent and an old code fails, exactly as for an unknown address. With another role: signs in without the student role. After reactivation: signs in as a student (US5-2, US5-3). |
| `tests/integration/test_admin_institutions.py` (changed) | Deactivate confirmations for region and institution. Deleting an institution with empty classes deletes them, with the confirmation saying so. One with an enrolled student, blocked or not, is refused as in use. One with a teacher link is still refused (US8). |
| `tests/integration/test_teacher_access.py` | Every teacher route × {administrator, student, anonymous}. Write, Read and unlinked teachers on every page and action with real ids, built from the route table. Hand-made addresses: a class of another institution, an institution of another region, unknown ids, non-integers, a student of a deactivated class. Access lowered or link removed while a form is open (US9, SC-004). |
| `tests/integration/test_routes.py` (changed) | Exact write set (+8). Unchanged public allowlist. The declared-page sweep skips only the allowed-role check on object-scoped teacher paths (research D17). |
| `tests/integration/test_consent_privacy.py` (changed) | Before a student acceptance, no table holds the invited email, names, or an enrolment. Logs captured during every flow above contain no email, name or link (SC-002, SC-008). |
| `tests/integration/test_migrations.py` (changed) | Empty → head; stairway; drift with `classes` and `enrolments` |
| `tests/integration/test_cross_site.py` (changed) | A cross-site class create and student invite are refused and change nothing |

## 2. Manual walk-through

Start the application locally:

```bash
uv run alembic upgrade head
ADMIN_EMAILS=admin@example.com uv run uvicorn app.main:app --reload
```

Emails go to the log in development (README), and the console sender prints each link.

1. **Set up** as `admin@example.com`:
   - Create the regions "Kyiv" and "Lviv", the institution "Kyiv Polytechnic Institute" in Kyiv,
     and "Lviv Academy" in Lviv.
   - Invite `olena@example.org` with **Write** to the Kyiv institution and **Read** to the Lviv one.
   - Accept the printed link in a private window.
2. **Classes** (US1), signed in as Olena:
   - `/teacher` opens **Students**. Only **Region** is enabled, with "Select a region to continue".
   - Pick Kyiv, then "Kyiv Polytechnic Institute — Write". **Class** offers only **+ Add class**.
   - Add "KN-21", year 2. It is selected, with "No students in this class yet".
   - Try "kn-21" and year 13: both errors are shown, with the values kept.
   - Bookmark the page and reload: the selection is kept.
3. **Invite a student** (US2):
   - **Add student**: `taras@example.org`, Taras Shevchenko. A banner says the invitation was sent.
   - The printed email names Olena, the student role, "Kyiv Polytechnic Institute (Kyiv)" and
     "KN-21 · year 2".
   - Open the link in another private window: the data, the student consent text and the names note
     are shown. Press **I agree** and sign in as Taras.
   - The profile shows the institution, the class, the year and the student correction note.
4. **Manage students** (US4):
   - As Olena, Taras is listed. **Edit**: fix the first name, and move him to a second active class
     "KN-22". Taras's window stays signed in.
   - Invite Taras again: "This email already belongs to a student".
5. **Chain** (US5):
   - As Olena, deactivate "KN-22" and confirm. Taras's next request asks him to sign in, and
     requesting a code sends nothing.
   - Activate it again: Taras signs in.
   - As the administrator, deactivate the Kyiv region: the confirmation mentions students. Olena's
     Kyiv institution disappears from her lists, and opening its old address shows "Access denied".
   - Activate the region again.
6. **Read access** (US9):
   - Administrators have no class pages, so to get a class into "Lviv Academy": as the
     administrator, give Olena Write there; as Olena, add a class; then set her back to Read.
   - Pick "Lviv Academy — Read": the class is listed with no actions. Opening its edit address by
     hand shows "Access denied".
7. **Remove and delete** (US4, US8):
   - Remove Taras: he is signed out, cannot sign in, and **Delete my data** still sends him a link.
   - Delete the now-empty "KN-21".
   - As the administrator, remove Olena's links and delete the institution: the confirmation says
     its classes will be deleted too.

## 3. After deployment

1. The deploy log shows the migration `create_classes_and_enrolments` applied, and no addresses.
2. As an administrator, invite yourself as a teacher with Write to a test institution and accept.
   Then, in the teacher area:
   - create a class;
   - invite a second address of yours as a student, and check that the Resend email arrives with
     the class and institution;
   - accept, and sign in as that student.
3. Remove the student, delete the class, then withdraw your own teacher consent to clean up.
