# HTTP Routes Contract: role choice, role switch, role pages, access denied

**Feature**: `005-roles-authorization` | **Date**: 2026-10-01 | **Plan**: [plan.md](../plan.md)

Server-rendered HTML (Jinja2 + Pico.css). Forms are plain `application/x-www-form-urlencoded`
posts answered with full-page responses or 303 redirects. There is no HTMX and no JavaScript
(FR-033). Milestone 4's routes (`/login`, `/login/code`, `/logout`, `/healthz`) are unchanged
except where noted
([specs/004-email-otp-auth/contracts/http-routes.md](../../004-email-otp-auth/contracts/http-routes.md)).
Rationale: [research D4–D7, D10](../research.md).

---

## Access rule (applies to every route)

Decided by the application-wide dependency `resolve_access` (`app/core/auth.py`), first match
wins:

| # | Request | Result |
|---|---|---|
| 1 | `GET`/`HEAD /healthz` | served; no session lookup |
| 2 | method other than `GET`/`HEAD`/`OPTIONS`, judged cross-site ([§ Cross-site rule](#cross-site-rule)) | **403** error page "This request was refused because it did not come from this site."; no session lookup, no write |
| 3 | no valid session, route in `PUBLIC_ROUTES` | served |
| 4 | no valid session, any other route | **303** `/login?next=<path?query>` for `GET`/`HEAD`, `/login` otherwise (unchanged) |
| 5 | valid session, route in `PUBLIC_ROUTES` or `ROLE_CHOICE_ROUTES` | served |
| 6 | valid session, no current role | **303** `/role?next=<percent-encoded path?query>` for `GET`/`HEAD`, `/role` otherwise |
| 7 | valid session, current role ∈ the route's `allowed_roles` | served |
| 8 | valid session, anything else (role not allowed, or the route declares no roles) | **403** access denied page ([below](#access-denied-page)) |
| — | no route matches | friendly **404**, for everyone (unchanged); the dependency does not run |
| — | `/static/…` | served by the mount (unchanged) |

"Valid session" is milestone 4's rule (signed cookie, known token, unexpired, active user) plus:
the person holds at least one role, and the session's current role, if set, is one of them. If the
current role is set but not held, **the session row is deleted** and the request continues as
anonymous (FR-017). If the current role is unset and exactly one role is held, it is set to that
role first (pre-milestone sessions).

**`PUBLIC_ROUTES`** (unchanged, five entries): `GET /login`, `POST /login`, `POST /login/code`,
`POST /logout`, `GET /healthz`.

**`ROLE_CHOICE_ROUTES`** (new, `app/core/auth.py`): `GET /role`, `POST /role`. These are open to
any signed-in person, with or without a current role. They need no role declaration (FR-022).

**Every other route** must carry `@allow_roles(...)` with a non-empty set. The access table for
this milestone (the contract the tests copy literally):

| Method | Path | Page | `allowed_roles` |
|---|---|---|---|
| `GET` | `/` | Home page | administrator, teacher, student |
| `GET` | `/admin` | Administrator area | administrator |
| `GET` | `/teacher` | Teacher area | teacher |
| `GET` | `/student` | Student area | student |
| `GET` | `/staff` | Staff area | administrator, teacher |

`HEAD` is accepted wherever `GET` is.

## Cross-site rule

Applied to every request whose method is not `GET`, `HEAD` or `OPTIONS`, before the session is
read ([research D7](../research.md#d7--cross-site-forgery-an-application-wide-fetch-metadata-and-origin-check)):

| `Sec-Fetch-Site` | `Origin` | Result |
|---|---|---|
| `same-origin` or `none` | any | allowed |
| `same-site`, `cross-site`, or any other value | any | **refused** |
| absent | host[:port] equals the `Host` header | allowed |
| absent | different host, or `null` | **refused** |
| absent | absent | allowed (non-browser client; `SameSite=Lax` still applies) |

This covers `POST /login`, `/login/code`, `/logout` and `/role`, and every later write route
(including HTMX requests), with no per-form token.

## Layout header (every page)

| State | Left | Right |
|---|---|---|
| anonymous | `Student Competitions` | nothing (unchanged) |
| signed in, no current role (role choice page only) | `Student Competitions` | email · **Log out** (FR-032) |
| signed in, current role, one role held | `Student Competitions · <Role>` | email · **Log out** (FR-031, US4-2) |
| signed in, current role, several roles held | `Student Competitions · <Role>` | email · switch form · **Log out** (FR-018) |

Role labels: `Administrator`, `Teacher`, `Student`. The role is rendered in an element with class
`site-role`, so tests can find it.

**Switch form**:
`<form method="post" action="/role" class="role-switch">`, a visible label "Switch to", and one
`<button type="submit" name="role" value="<value>">` per role held **other than** the current one,
in the fixed order. It has no `next` field, so a switch always lands on `/`.

The 404 page is rendered without the resolver, so it shows the anonymous header (unchanged).

---

## `GET /role` — the role choice

| Case | Response |
|---|---|
| anonymous | 303 `/login?next=%2Frole` (rule 4) |
| one role held | **303** `/` (FR-016) |
| several roles held, with or without a current role | **200** role choice page |

**Page** (`pages/role_choice.html`): `<h1>Choose a role</h1>`, then one sentence: "You have more
than one role. Choose the one to use now. You can switch at any time from the header." Then one
form:

```html
<form method="post" action="/role">
  <input type="hidden" name="next" value="<safe next>">   <!-- only if ?next= was given -->
  <button type="submit" name="role" value="admin">Administrator</button>
  <button type="submit" name="role" value="teacher">Teacher</button>
  …only the roles held, in the fixed order (US3-1)…
</form>
```

The `next` query parameter goes through `safe_next_path`, so `/role`, `/login`, `/login/code`,
`/logout`, absolute and protocol-relative URLs all become `/`. The **Log out** button in the
header works as usual (US3-4).

## `POST /role` — choose or switch

Form fields: `role` (required), `next` (optional).

| Case | Response | State |
|---|---|---|
| anonymous (including a cross-site post, whose cookie the browser drops) | 303 `/login` | unchanged |
| refused by the cross-site rule | 403 | unchanged (FR-021) |
| `role` is a role the person holds | **303** `safe_next_path(next)`: the requested page after the role choice (FR-015), `/` after a header switch (FR-019) | `sessions.current_role = role` for **this** session only; same session row and cookie (US4-3, US4-5) |
| `role` is the current role already | 303 as above | unchanged (edge case: harmless) |
| `role` missing, unknown, or not held (tampered form) | **400** role choice page with the message "Choose one of your roles." | unchanged (US3-5, US4-6) |

`GET /role?role=student` is just the role choice page and changes nothing (FR-020).

The return address is never adjusted to the new role. If the chosen role may not open it, the
person lands there and gets the 403 page (edge case).

## `POST /login/code` — changed only on success

A correct code now starts the session according to the roles held:

| Roles held | Session starts with | Redirect |
|---|---|---|
| exactly one | `current_role` = that role | **303** `next` (unchanged, FR-012, SC-003) |
| two or three | `current_role` = `NULL` | **303** `/role?next=<percent-encoded next>` (FR-013, SC-004) |

Every failure response is unchanged.

## `GET /login` — unchanged

A signed-in visitor is still redirected to `next`. Without a current role, the next request then
redirects to the role choice (rule 6).

## `GET /` — the home page

Open to all three roles. The body is milestone 4's, unchanged, plus a section placed after the
introduction:

```html
<section id="areas" aria-labelledby="areas-heading">
  <h2 id="areas-heading">Your areas</h2>
  <ul>
    <li><a href="/teacher">Teacher area</a></li>
    <li><a href="/staff">Staff area</a></li>
  </ul>
</section>
```

The list holds exactly the area pages whose `allowed_roles` contain the current role, in the order
administrator, teacher, student, staff (FR-027):

| Current role | Links |
|---|---|
| Administrator | Administrator area, Staff area |
| Teacher | Teacher area, Staff area |
| Student | Student area |

## `GET /admin`, `/teacher`, `/student`, `/staff` — placeholders

Each one is **200** for its allowed roles and **403** for the others, per the access table. The
shared template is `pages/area.html`: `<h1>` = the area title ("Administrator area", "Teacher
area", "Student area", "Staff area"), then one paragraph: "The features of this area will arrive
in a later milestone." There is nothing else and no personal data beyond the header (FR-030).

## Access denied page

`pages/error.html` with status **403**:

- heading: `Access denied`;
- message: `Your current role, <Role>, cannot open this page.`;
- the existing link: `Back to the home page`;
- the full header, including the switch form for multi-role people.

It never says which roles could open the page, never switches role (FR-026), and never reveals any
of the denied page's content (FR-025). The log line is `Access denied: role=<value> route=<path
template>`, with no email and no user id (SC-008).

## Write routes (complete list after this milestone)

`POST /login`, `POST /login/code`, `POST /logout`, `POST /role`. `tests/integration/test_routes.py`
pins this set.
