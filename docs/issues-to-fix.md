# Issues to fix

Known problems that were found during a milestone but deliberately left out of its scope. Each one
says where it was found, what is wrong today, and what fixing it involves, so a later milestone can
pick it up. Remove an entry when the fix is merged.

---

## 1. Deactivating a subject has no confirmation page

| | |
|---|---|
| Found in | Milestone 10, `/speckit-analyze` of `specs/010-design-system-ui-guidelines/` (finding H1) |
| Area | Administrator area, **Subjects** tab |
| Rule it breaks | Every destructive action asks for confirmation and says what will happen (milestone 10 spec FR-007, FR-032, SC-007; `docs/requirements/ui-guidelines.md`) |
| Exemption | Milestone 10 spec FR-032a |

**Today**: the **Deactivate** button on each row of `/admin/subjects` is a form that posts straight
to `POST /admin/subjects/{id}/deactivate` (`app/routers/admin_subjects.py`). The subject is
deactivated at once, with no question and no consequence shown. Every other **Deactivate** in the
application (regions, educational institutions, classes) first opens a confirmation page.

**Why it was not fixed in milestone 10**: milestone 10 changes only the look and wording. A
confirmation needs a new `GET` page and route, which that milestone's scope rules out (FR-040,
FR-050). The action is reversible with **Activate** on the same row, so the risk is low. Milestone
10 shows the button as destructive but keeps it direct.

**Fix**:

- Add `GET /admin/subjects/{id}/deactivate`, administrator only, rendering a new
  `pages/admin/subject_deactivate.html` built from the `confirmation` component: the question
  "Deactivate “{subject}”?", the consequence (what a deactivated subject can no longer be used for),
  a destructive **Deactivate** button posting to the existing `POST` route, and **Cancel** back to
  `/admin/subjects`. Return 404 with `subject_not_found.html` for an unknown id, as the delete page
  does.
- On the **Subjects** list, turn **Deactivate** into a destructive `link_button` to the new page.
- Leave the **Deactivate** alternative on the delete refusal page (`subject_delete.html`) as a
  direct post: that page already explains the situation.
- Remove any mention of the exemption from `docs/requirements/ui-guidelines.md`, and delete this
  entry.

**Tests**:

- the new page's role access (administrator allowed; teacher, student and anonymous denied as for
  every administrator page) and its entry in the route-table sweep;
- the confirmation pattern (question naming the subject, consequence, destructive **Deactivate**,
  **Cancel**), as for the other confirmations in `tests/integration/test_page_patterns.py`;
- the list's **Deactivate** is a link with `role="button"` to the new page, and no direct
  deactivate form remains on `/admin/subjects`;
- the existing `POST` behaviour and its tests stay unchanged.
