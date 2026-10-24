# Contract: HTTP Routes (Milestone 10)

**Feature**: [../spec.md](../spec.md) | **Research**: [../research.md](../research.md) D5, D6, D15

This milestone adds **two routes** and changes **no existing route**:

- **Addresses**: every existing route keeps its address, method, form field names, status codes,
  redirects and `@allow_roles` declaration (FR-040, SC-011).
- **Bodies**: only the HTML they render changes.
- **Every response** gains the theme behaviour described in §3.

---

## 1. `POST /theme`: choose the theme

| | |
|---|---|
| Router | `app/routers/theme.py` (new) |
| Access | `PUBLIC_ROUTES` += `("POST", "/theme")`. Anonymous visitors and every signed-in role, with or without a current role. |
| Cross-site check | Yes, as for every `POST` (`resolve_access` rule 2). A cross-site post gets the 403 "Request refused" page, and nothing is set. |
| Database | Never touched. |
| Form fields | `theme`: `light`, `dark` or `device`. `next`: the return target. |

**Behaviour**:

1. **The choice**: `parse_theme(theme)` gives Light, Dark or Device. An unknown or missing value is
   Device.
2. **The return target**: `target = safe_return_path(next)`. It is refused, and replaced by the
   fallback, when it:
   - is empty or longer than 2,048 characters;
   - does not start with exactly one `/`;
   - contains a backslash, whitespace or a control character;
   - has a scheme or a host;
   - has the path `/login/code`, `/logout` or `/theme`;
   - has a path that matches no `GET` route in the application's route table.
3. **The fallback**: `/` when the request has a signed-in user, `/login` otherwise.
4. **The response**: a 303 to `target`. `apply_theme` sets `sc_theme=light|dark`, or deletes it for
   Device (see [data-model.md §1](../data-model.md#1-theme-choice-cookie-not-stored-on-the-server)).

**Responses**:

| Case | Status | `Location` | Cookie |
|---|---|---|---|
| `theme=dark`, `next=/admin/subjects` | 303 | `/admin/subjects` | `sc_theme=dark` |
| `theme=light`, `next=/login?next=%2Fprofile` | 303 | `/login?next=%2Fprofile` | `sc_theme=light` |
| `theme=device` | 303 | the target | deleted |
| `theme=purple` | 303 | the target | deleted (treated as Device) |
| `next=https://evil.example/` or `//evil.example` | 303 | `/` signed in, `/login` signed out | as chosen |
| `next=/login/code` or `/logout` | 303 | fallback | as chosen |
| `next=/admin/subjects/7/deactivate` (no `GET` route) | 303 | fallback | as chosen |
| Cross-site `POST` | 403 "Request refused" | none | unchanged |

**Route-table tests** (`tests/integration/test_routes.py`):

- `test_the_allowlist_is_exact` gains `("POST", "/theme")`.
- `test_the_write_routes_are_exact` gains `("POST", "/theme")`.
- `test_every_allowlist_entry_exists` covers it automatically.

---

## 2. `GET /admin/components`: the component gallery (development only)

| | |
|---|---|
| Router | `app/routers/admin_components.py` (new), `APIRouter(route_class=DevelopmentOnlyRoute)` |
| Access | `@allow_roles(Role.ADMIN)` |
| Production | The route **does not match** when `app.state.settings.production` is true, or when `settings` is missing. The request is then an unknown address: the friendly 404 page for everyone, anonymous included, decided before `resolve_access` runs (FR-038a). |
| Database | Never touched: no session dependency (FR-037). |
| Tabs | Rendered with `render_admin(…, active_tab=None)`. It is not in `ADMIN_TABS`, and no tab is marked current (FR-038, US7-2). |

**Responses outside production**:

| Who | Status | Page |
|---|---|---|
| Anonymous | 303 | `/login?next=%2Fadmin%2Fcomponents` (the existing rule 4) |
| Administrator, current role administrator | 200 | The gallery: every component and variant, in the current theme |
| Administrator acting as teacher or student | 403 | "Access denied", naming the current role |
| Teacher, student | 403 | "Access denied", naming the current role |

**Responses in production**:

| Who | Status | Page |
|---|---|---|
| Anyone, signed in or not, any role | 404 | The same friendly "not found" page as `GET /no-such-page` |

**Route-table tests**:

- **The access sweep**: `test_every_declared_page_admits_exactly_its_roles` covers the gallery
  automatically, because the tests do not run as production.
- **New production tests** (`tests/integration/test_component_gallery.py`): the tests switch
  production on with `app.state.settings = dataclasses.replace(settings, production=True)`.
  - The 404 for anonymous visitors and for every role is asserted.
  - The 404 body is asserted to equal the body for an unknown address, apart from the requested
    path.

---

## 3. Every page: the theme and the frame

These apply to every HTML response, including error pages rendered by the exception handlers.

| Request | `<html>` | `<meta name="color-scheme">` |
|---|---|---|
| No `sc_theme` cookie, or an empty or unknown value | `<html lang="en">` | `light dark` |
| `sc_theme=light` | `<html lang="en" data-theme="light">` | `light` |
| `sc_theme=dark` | `<html lang="en" data-theme="dark">` | `dark` |

**What every page gains**:

- **Head links**: the page links only `/static/…` resources: `pico.min.css`, `app.css`, the latin
  font preload, the favicons, and `auto-submit.js` where it is used today. Nothing loads from
  another site (FR-048).
- **The top bar** shows the logo mark, "Student Competitions" and, when signed in, the current
  role's label.
- **When signed in**, the user menu holds:
  - the email, linking to `/profile`;
  - the role-switch form (`POST /role`, unchanged), only when the person holds several roles;
  - the theme switch (`POST /theme`);
  - the logout form (`POST /logout`, unchanged).
- **`GET /login`** shows the theme switch, with `next` set to `/login` plus its query string.
- **The footer** shows the version and build. On `GET /` it also shows the database status line.

---

## 4. Unchanged, listed for review

- **Public routes**: `PUBLIC_ROUTES` gains only `("POST", "/theme")`. `ROLE_CHOICE_ROUTES` is
  unchanged.
- **Status codes**: every error page keeps its status code and texts. That covers the 403 "Access
  denied", the 403 "Request refused", the 404 "not found", the 404 "Subject not found" and similar
  pages, the 400 and 410 link-status pages, and the 503 "unavailable" pages.
- **Auto-submit**: `GET /teacher/students` keeps its `?region=&institution=&class=` query and its
  three auto-submitted `GET` forms.
- **Existing confirmations**: every confirmation page keeps its `GET` address, and its action keeps
  its `POST` address.
- **No HTMX** is introduced. No partial is added to `app/templates/partials/`.
