# Contract: HTTP Routes (Milestone 12.8)

All routes are in the teacher area and are `@allow_roles(Role.TEACHER)`. Administrators and
students get the milestone 5 "access denied" page (403) before any id is read. The list context
(`subject`, `status`, `page`) is read and carried as in milestones 12.1–12.4.

## 1. `GET /teacher/competitions/{competition_id}/publish`

The publish confirmation. Router: `teacher_competitions.py`.

| Query | Meaning |
|---|---|
| `subject` | The competition's subject (required, as on every competition route). |
| `status`, `page` | The list the teacher came from; parsed with `parse_status_filter`, `parse_page`. |

| Outcome | Status | Page |
|---|---|---|
| No setting | 403 | access denied (before any id or value is parsed) |
| Unknown subject | 404 | "Subject not found" |
| Unknown, other-subject or invisible competition | 404 | "Competition not found" |
| Not **Finished** | 409 | refusal "Publish the results of “<name>”?" + `PUBLISH_REFUSALS[status]` + **Back to competitions** |
| **Finished**, every team graded | 200 | the confirmation: question, badge, "Graded N of N teams", consequence, **Publish results** (primary), **Keep unpublished** |
| **Finished**, a team ungraded | 200 | the blocked confirmation: question, badge, progress, "Every team must be graded before the results can be published.", **Grade the remaining teams**, **Keep unpublished**, no button |

**Grade the remaining teams** →
`/teacher/competitions/{id}/grades?<list_query(subject, status, page)>&show=ungraded` (page 1). It is
built in `teacher_competitions.py` from `list_query` and the literal `show=ungraded`, never by
importing `teacher_grades`: that module imports `teacher_competition_entries`, which imports
`teacher_competitions`, so the import would be circular. The parameter order is the one
`teacher_competition_entries.address` writes (`subject`, `status`, `page`, then `show`), and a test
asserts that the two agree.

**Keep unpublished** and **Back to competitions** → `list_path(subject, status, page,
anchor=competition_id)`.

## 2. `POST /teacher/competitions/{competition_id}/publish`

Form fields: `subject`, `status`, `page` (strings) and the cross-site token of milestone 4.

| Outcome | Status | Response |
|---|---|---|
| Cross-site check fails | 403 | the existing refusal; nothing changes |
| No setting | 403 | access denied |
| Unknown subject / competition | 404 | as §1 |
| Not **Finished** (before or under the lock) | 409 | the refusal of §1 for the status found |
| A team ungraded (under the lock) | 409 | the blocked confirmation of §1 with the current progress |
| Published | 303 | `list_path(subject, status, landing.page, landing.competition_id, notice)`; the notice token's outcome is `published` → "The results of “<name>” were published" |

**Landing** (FR-010): under **All** and **Published**, the competition itself; under **Finished**,
`competitions.landing` (the row that took its place, the one before it, the previous page, the
empty state). A reload of the result never repeats the publish (Post/Redirect/Get).

`PUBLISH_REFUSALS`:

| Status | Reason |
|---|---|
| Upcoming | "“%(name)s” has not started yet, so it has no results to publish." |
| In progress | "“%(name)s” is still in progress. Finish it and grade its answers before publishing its results." |
| Cancelled | "“%(name)s” has been cancelled, so it has no results to publish." |
| Published | "The results of “%(name)s” are already published." |

## 3. `GET /teacher/competitions/{competition_id}/results`

The download. Router: `teacher_results.py` (new, small). Any teacher; no setting.

| Query | Meaning |
|---|---|
| `subject` | The competition's subject. The list context is not needed: the teacher stays on the list. |

| Outcome | Status | Response |
|---|---|---|
| Not a teacher | 403 | access denied, before any id is read |
| Unknown subject | 404 | "Subject not found" |
| Unknown, other-subject, invisible or not **Published** competition | 404 | "Competition not found" (milestone 12.1) |
| **Published** | 200 | the stored file of `request.state.language`, byte for byte |

Response headers on 200:

```text
Content-Type: application/pdf
Content-Disposition: attachment; filename="<ascii fallback>"; filename*=UTF-8''<percent-encoded name>
Cache-Control: no-store
X-Content-Type-Options: nosniff
```

The name is `results.results_file_name(name, starts_at)` (research R9). Opening the address
changes nothing and logs nothing.

## 4. Changed routes

| Route | Change |
|---|---|
| `GET /teacher/competitions` | `published` is a valid `status` value; **Finished** lists only unpublished finished competitions; the menu entries of research R10. |
| `GET/POST …/{id}/edit`, `…/cancel`, `…/finish` | `PUBLISHED` refused with the `FINISHED` reason of each. |
| `GET …/{id}/questions`, `…/teams` (12.2) | open read-only on **Published** (unchanged code path: the change routes refuse every non-Upcoming status). |
| `GET …/{id}/answers`, `GET …/answers/{team_id}` (12.3, 12.4) | open on **Published** as on **Finished** (`has_finished`); a `POST` gets the finished reason. |
| `GET …/{id}/grades` (12.4) | opens on **Published**. |
| `GET …/{id}/grades/{team_id}` (12.4) | on **Published**: the read-only grading sheet with the note "The results of “%(name)s” are published, so its grades can no longer be changed.", 200. |
| `POST …/{id}/grades/{team_id}` (12.4) | on **Published** (before or under the lock): the same read-only sheet with the note, 409; nothing stored. |

## Order of checks

1. The role (`@allow_roles`): 403 before any id is read.
2. The setting, on publish only (`require_manage`, first line of the handler): 403 before any value
   is parsed.
3. The subject, then the competition: 404. For the download, also any competition that is not
   **Published**.
4. The status (publish): 409 refusal.
5. The grading (publish `POST`): 409 blocked confirmation.
6. The service write repeats 2–5 under lock (contracts/services.md §1).
