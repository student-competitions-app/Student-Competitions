# Quickstart: Validate User Management with Consent — Teachers (Milestone 8)

**Feature**: [spec.md](./spec.md) | **Routes**: [contracts/http-routes.md](./contracts/http-routes.md) |
**Services**: [contracts/services.md](./contracts/services.md) |
**Configuration**: [contracts/configuration.md](./contracts/configuration.md)

This guide proves the milestone works. It runs the automated suite first, then a manual
walk-through in a browser, then a check after deployment.

## Prerequisites

- The repository set up as in the README ("Getting started"): `uv sync`. This now installs
  `cryptography` (research D1).
- Optional, to run the PostgreSQL half of the suite: a local PostgreSQL server and
  `TEST_POSTGRES_URL` (README, "Test"). The row locks (research D6, D9) and the foreign-key
  backstop matter only on PostgreSQL.

## 1. Automated checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Expected: all green on SQLite, and also on PostgreSQL when `TEST_POSTGRES_URL` is set. The tests
for this milestone, mapped to the milestone 8 _Test:_ list (FR-067):

| Test module | Proves |
|---|---|
| `tests/unit/test_sealing.py` | Round trip; any changed byte, wrong purpose, wrong key or unknown version → `SealInvalid`; age ≥ max → `SealExpired` only for authentic tokens; no plaintext visible in the token |
| `tests/unit/test_person_schemas.py` | Names: 100 accepted, 101 refused, tab/newline refused, trimmed, inner spaces kept; email normalised as at sign-in |
| `tests/unit/test_teacher_schemas.py` | Picker parsing: none, duplicate, non-integer, bad or missing level refused; Read default; kept level for unselectable links |
| `tests/unit/test_log_redaction.py` | Uvicorn-shaped access records lose invitation and deletion tokens and `sent`/`prefill` values; other records untouched |
| `tests/unit/test_auth_config.py` | Role lists no longer read; `PUBLIC_BASE_URL` rules C11–C13; W3 reworded; no value in any message |
| `tests/unit/test_email.py` | Invitation and deletion messages: plain text, every required statement, link and UTC expiry; nothing personal in the subject |
| `tests/integration/test_teacher_invitation.py` | **End to end**: invite with Write + Read and the setting → outbox link → `GET` stores nothing → **I agree** creates user, role, both links, setting and consent record → sign-in page prefilled → the teacher signs in and the profile shows everything (US1) |
| `tests/integration/test_invitation_refusals.py` | Tampered, expired; inviter lost the administrator role; institution deleted, deactivated, or its region deactivated; renamed institution shows its new name and succeeds; extra or changed form fields ignored; consent text changed → page again, nothing stored (US2) |
| `tests/integration/test_invitation_cutoff.py` | An older invitation cannot bring the role back for a deactivated teacher, a teacher whose data was deleted, or an administrator who lost the teacher role but stayed active; a newer invitation can; same-instant removal wins (US2-6 to US2-8) |
| `tests/integration/test_invitation_edge_cases.py` | Already a teacher; double press and two invitations → one role, one record; inactive user reactivated; rate limits per inviter and per address; send failure keeps values and still counts |
| `tests/integration/test_admin_teachers.py` | Tab: "No teachers yet", order by last name, columns; picker offers only active institutions in active regions; edit changes one link's level and the setting, other link unchanged; deactivated link kept on save, removable, not re-addable; invalid edits refused; email read-only; remove (deactivated vs still admin), signed out everywhere; reload safety (US3) |
| `tests/integration/test_institution_service.py` (changed) | A linked institution cannot be deleted (`count_institution_uses` counts teacher links) |
| `tests/integration/test_profile.py` | Profile for each kind of person; read-only; **Withdraw consent** shown only with consent data (also for a removed teacher who is still an administrator); confirmation changes nothing; withdrawal erases names, replaces the email (or keeps it for an administrator), keeps the records, signs out everywhere; sign-in then fails (US4) |
| `tests/integration/test_data_deletion.py` | Known, unknown and erased addresses get the same answer; only the known one gets an email; per-address limit; opening the link changes nothing; the button erases as withdrawal does; used and expired links → "expired"; a removed teacher can delete their data (US5) |
| `tests/integration/test_self_invitation.py` | An administrator invites their own address: both roles, invitation names, own inviter, session kept, role switch offered; after withdrawal keeps admin role and email and leaves the tab (US6) |
| `tests/integration/test_user_reconcile.py` (rewritten) | The reconcile manages only the administrator role; a teacher is never touched; losing admin while a teacher keeps the person active and signs them out (US7) |
| `tests/integration/test_migrations.py` (changed) | Empty → head, stairway, drift with the five new tables; `retire_role_lists` removes list roles, deactivates and replaces emails of people left with no role, signs them out, and keeps administrators |
| `tests/integration/test_routes.py`, `test_access_control.py`, `test_cross_site.py` (changed) | Exact write and public route sets; every teacher-management page and action refuses teacher, student and an administrator using another role, and changes nothing; anonymous → sign in; profile open to every role; cross-site `POST`s refused (US8) |
| `tests/integration/test_consent_privacy.py` | Before acceptance no table holds the invited email or names (all columns of all tables are scanned); logs captured during every flow above contain no email, name or token (SC-002, SC-007) |
| `tests/integration/test_admin_area.py` (changed) | The Teachers placeholder is gone; every page of this feature marks the Teachers tab |

## 2. Manual walk-through

Start the application locally with two administrators. Teachers now come only from invitations.

```bash
uv run alembic upgrade head
ADMIN_EMAILS=admin@example.com,both@example.com uv run uvicorn app.main:app --reload
```

Emails, including invitation and deletion links, are printed to this console (`console`
backend). Sign in as `admin@example.com` with the printed code.

1. **Data to pick from.** On **Educational institutions**:
   - create the region "Kyiv" with the institution "Kyiv Polytechnic Institute";
   - create the region "Lviv" with "Lviv Academy" and "Old School";
   - deactivate "Old School";
   - create the region "Closed" with "Hidden School", then deactivate the region.
2. **Invite.**
   - **Teachers** shows "No teachers yet". Click **Invite teacher**.
   - The picker lists exactly "Kyiv Polytechnic Institute (Kyiv)" and "Lviv Academy (Lviv)",
     each defaulting to Read.
   - Enter `olena@example.org`, "Olena", "Kovalenko". Pick Kyiv = Write and Lviv = Read, check
     **Can create competitions**, and press **Send invitation**.
   - Expect "Invitation sent to olena@example.org". The address bar shows only `?sent=` followed
     by an unreadable value.
3. **Nothing stored.** `sqlite3 data/student_competitions.sqlite3 "select * from users"` shows
   no `olena`. The console's uvicorn access lines show `/admin/teachers?sent=***`.
4. **Accept.**
   - Open the printed link in a private window. The page shows the inviter, the role, the data,
     the expiry in UTC, the consent text and **I agree**. Reload: still nothing in `users`.
   - Press **I agree**. You land on **Sign in** with `olena@example.org` filled in and "Your
     account is ready".
   - The access log shows `/invitations/***`.
5. **Profile.** Sign in as Olena. Click the email in the header: the profile shows names, Teacher,
   both institutions with levels, "Can create competitions: Yes", and the consent record with its
   text.
6. **Manage.**
   - As the administrator, open Olena on **Teachers**. Change Kyiv to Read, uncheck the setting,
     and save. Lviv is unchanged.
   - Deactivate "Lviv Academy". Olena's page shows it as deactivated, and saving keeps it.
     Uncheck it and save: it is gone, and it is not offered again.
   - Try to delete "Kyiv Polytechnic Institute": it is refused as in use.
7. **Cut-off.**
   - Invite Olena again (link A). Remove Olena (confirm). She disappears and is signed out.
   - Open link A and press **I agree**: the neutral refusal.
   - Invite her again (link B) and accept B: she is a teacher again.
8. **Withdraw.** As Olena: profile → **Withdraw consent** → confirm. You land on "Your data has
   been erased". Signing in as `olena@example.org` sends no code.
9. **Self-invitation.**
   - As `both@example.com`, invite `both@example.com` and accept in the same browser. You stay
     signed in, and the header now offers **Switch to Teacher**.
   - Withdraw: you are signed out, and signing in again works as an administrator only.
10. **Delete my data.**
    - Invite `petro@example.org`, accept, then remove Petro as the administrator.
    - On the sign-in page, click **Delete my data** and enter `petro@example.org`. You see "If
      this email is registered, we have sent you a link."
    - Open the printed link: it lists the data, and nothing changed. Press **Delete my data**: you
      see the confirmation. Open the link again: "This link has expired; request a new one."
    - Request for `nobody@example.org`: the same answer, and nothing is printed.

## 3. After deployment

1. Before merging, check that the Render service has `PUBLIC_BASE_URL` from `render.yaml`
   (`https://brainring.org.ua`). Without it the release refuses to start (C11).
2. After the deploy:
   - The deploy log shows `Users reconciled: …` with no addresses.
   - `TEACHER_EMAILS` and `STUDENT_EMAILS` can be deleted from the Render dashboard (they are
     ignored).
3. As an administrator, invite yourself to one institution and check:
   - the email arrives from Resend;
   - the link is `https://brainring.org.ua/invitations/…`;
   - acceptance works;
   - Render's application log shows `/invitations/***`.

   Then withdraw to clean up.
4. Former list teachers and students can no longer sign in, and administrators still can.
