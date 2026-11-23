# HTTP Routes: Milestone 12.10

Every route is `@allow_roles(Role.TEACHER)`. An administrator, a student or an anonymous visitor
gets the milestone 5 refusal before any id or parameter is read (403 page, or the sign-in
redirect for anonymous visitors, as every teacher route does).

## 1. A competition's Questions subtree (changed)

| Route | Before | Now |
|---|---|---|
| `GET /teacher/competitions/{id}/questions` | every teacher | **teachers with Can manage competitions only** |
| `GET /teacher/competitions/{id}/questions/add` | managers | unchanged |
| `POST /teacher/competitions/{id}/questions` | managers | unchanged |
| `GET /teacher/competitions/{id}/questions/{qid}/remove` | managers | unchanged |
| `POST /teacher/competitions/{id}/questions/{qid}/remove` | managers | unchanged |

**Order of checks** for every route in the table:

1. the role (403);
2. the setting, `require_manage`, first thing in the handler, before any value is parsed
   (403, the same page for every id, a missing competition and an unknown subject included);
3. then everything else as milestones 12.2 and 12.9 specify (subject 404, competition 404, status
   refusal 409, entry 404, write under lock).

For a manager, `GET …/questions` is unchanged: the 12.2 page with the 12.9 badge and bank numbers,
in every status. The `/teams` routes are unchanged: every teacher reads, managers change.

## 2. Download questions (new)

`GET /teacher/competitions/{competition_id:int}/questions-file?subject=<subject id>`

| Step | Check | Failure |
|---|---|---|
| 1 | role is teacher | 403 (milestone 5) |
| 2 | `subject` names an offered subject: active, or deactivated with a finished or published competition (12.1 `offered_subjects`) | 404, the Competitions tab's not-found page, "Subject not found" (12.1 text) |
| 3 | the competition exists, belongs to that subject and is visible in it (12.1 `find_competition`: a deactivated subject shows only finished and published ones) | 404, "Competition not found" |
| 4 | its status is **In progress**, **Finished** or **Published** | 404, "Competition not found" (**Upcoming**, **Cancelled**) |

**Success**: `200`, the questions file of the current site language (`request.state.language`),
made now.

```text
Content-Type: application/pdf
Content-Disposition: attachment; filename="<ASCII fallback>"; filename*=UTF-8''<percent-encoded name>
Cache-Control: no-store
X-Content-Type-Options: nosniff
```

The name is `<name> <YYYY-MM-DD> questions.pdf` in English and `<name> <YYYY-MM-DD> питання.pdf`
in Ukrainian: the competition's name (cleaned, 12.8 rule) and its start date in Kyiv time.

The setting is never read. Nothing is written and nothing is logged. A `HEAD` or any other method
is not offered (405), as for **Download results**.

## 3. Download study materials (new)

`GET /teacher/competitions/study-materials?subject=<subject id>`

| Step | Check | Failure |
|---|---|---|
| 1 | role is teacher | 403 |
| 2 | `subject` parses as an id and names an **active** subject (`questions.get_active_subject`) | 404, the Competitions tab's not-found page, with the Questions tab's text: "Subject not found" / "This subject does not exist or is deactivated." |

A missing or malformed `subject` is the same 404. A deactivated subject is 404 whatever the
memory holds.

**Success**: `200`, the study materials of the current site language, given from memory when
nothing they show has changed and made otherwise ([services.md](./services.md) §3). The headers
are those of §2. The name is `<subject> <YYYY-MM-DD> study materials.pdf` in English and
`<subject> <YYYY-MM-DD> навчальні матеріали.pdf` in Ukrainian: the subject's name (cleaned) and
the Kyiv date of the download.

The setting is never read: a manager gets exactly the file every teacher gets. Nothing is written
and nothing is logged.

## 4. The Competitions tab `GET /teacher/competitions` (changed)

**The actions menu** of each row lists, in this order, each only where available:

| Entry | Shown when |
|---|---|
| Edit | setting, active subject, **Upcoming** (unchanged) |
| Questions | **setting** (any status) — *was: every teacher* |
| Teams | every teacher (unchanged) |
| Answers | **In progress**, **Finished**, **Published** (unchanged) |
| **Download questions** | **In progress**, **Finished**, **Published**; every teacher; `menu_link(..., download=True)` to §2 with `subject=<selected id>` |
| Grades | setting, **Finished**, **Published** (unchanged) |
| Publish results | setting, **Finished** (unchanged) |
| Download results | **Published** (unchanged) |
| Finish competition | setting, **In progress** (unchanged) |
| Cancel competition | setting, active subject, **Upcoming** or **In progress** (unchanged) |

**The study materials link**: when a subject is chosen and it is active, `chained_lists` gets the
aside `link_button("Download study materials", "/teacher/competitions/study-materials?subject=<id>",
kind="secondary", outline=True, small=True, download=True)`. It is shown to every teacher, and
not shown before a subject is chosen, with no subjects, or for a subject of the **Deactivated
subjects** group.

## 5. Unchanged

The Answers pages and sheets, the Grades pages and grading sheets, the Teams pages, the question
bank's Questions tab, the results download, every administrator and student page.
