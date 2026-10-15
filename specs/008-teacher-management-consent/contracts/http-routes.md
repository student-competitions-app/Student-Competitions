# Contract: HTTP Routes — Teachers, Invitations, Profile, Data Deletion (Milestone 8)

**Feature**: [spec.md](../spec.md) | **Research**: [research.md](../research.md) D4, D10, D11, D13, D14, D17

Four new router modules, plus small changes to the sign-in page and the header. Plain links and
forms only: no HTMX and no script (Principle II). Every change is a `POST` through the
application-wide cross-site check (FR-059). Every successful `POST` answers `303`
(Post/Redirect/Get, FR-060).

## Access summary

| Group | Declared | Anonymous `GET` / `POST` | Wrong current role |
|---|---|---|---|
| Teacher management (`/admin/teachers…`) | `@allow_roles(Role.ADMIN)` | `303 /login?next=…` / `303 /login` | `403` "Access denied", nothing changes |
| Profile (`/profile…`) | `@allow_roles(*ALL_ROLES)` | `303 /login?next=…` / `303 /login` | none: every role is allowed |
| Invitation and data deletion pages | `PUBLIC_ROUTES` | served | served, whatever the role. They act only on the person in the link (FR-055). |

A signed-in person with no current role yet is sent to `/role` for the first two groups, as
everywhere (milestone 5). The public pages serve them directly.

**`PUBLIC_ROUTES` gains exactly**:

```text
GET  /invitations/{token}            POST /invitations/{token}
GET  /data-deletion                  POST /data-deletion
GET  /data-deletion/requested
GET  /data-deletion/confirm/{token}  POST /data-deletion/confirm/{token}
GET  /data-erased
```

**`test_the_write_routes_are_exact` gains**:

```text
POST /admin/teachers/invite
POST /admin/teachers/{user_id:int}
POST /admin/teachers/{user_id:int}/remove
POST /profile/withdraw
POST /invitations/{token}
POST /data-deletion
POST /data-deletion/confirm/{token}
```

**Link pages' response headers** (`/invitations/{token}` and `/data-deletion/confirm/{token}`,
every status): `Referrer-Policy: no-referrer` and `Cache-Control: no-store` (FR-061).

---

## 1. Teacher management — `app/routers/admin_teachers.py`

Every page renders through `render_admin` with the **Teachers** tab current. The placeholder
handler for `/admin/teachers` is removed from `app/routers/admin.py`.

| Method | Path | Purpose | Success | Other outcomes |
|---|---|---|---|---|
| GET | `/admin/teachers` | List of current teachers | `200` | `?sent=<sealed>` valid → banner "Invitation sent to <email>". Invalid or stale → no banner. |
| GET | `/admin/teachers/invite` | Invitation form | `200` | — |
| POST | `/admin/teachers/invite` | Send an invitation | `303` → `/admin/teachers?sent=<sealed>` | `400` form with errors and values. `429` "Too many invitations. Please try again later." with values. `503` "The invitation email could not be sent. Please try again." with values. |
| GET | `/admin/teachers/{user_id:int}` | Teacher page (edit form) | `200` | `404` "Teacher not found" |
| POST | `/admin/teachers/{user_id:int}` | Save the edit | `303` → `/admin/teachers` | `400` form with errors and values. `404` "Teacher not found". |
| GET | `/admin/teachers/{user_id:int}/remove` | Remove confirmation | `200` | `404` "Teacher not found" |
| POST | `/admin/teachers/{user_id:int}/remove` | Remove the teacher | `303` → `/admin/teachers` | `404` "Teacher not found" |

### The list (FR-038)

- **Empty**: "No teachers yet" and an **Invite teacher** link.
- **Otherwise**: a table sorted by `(last_name.casefold(), first_name.casefold(), id)`. The
  columns are:
  - name, which links to the teacher page;
  - email;
  - institutions, as "Name (Region) — Read/Write", with "(deactivated)" when the institution or
    its region is inactive;
  - **Can create competitions**, "Yes" or "No";
  - date of consent, the UTC date (research D19).

### The invitation form (FR-014–FR-018)

Fields:

- `email`;
- `first_name`, `last_name`;
- the picker (research D11): `institution` (repeated) and `access` (repeated, `<id>:read` /
  `<id>:write`, Read preselected);
- `can_create_competitions` (checkbox, unchecked by default).

**Send invitation** posts to `/admin/teachers/invite`.

- **Picker rows**: only selectable institutions (active institution and active region), shown as
  "Name (Region)" (FR-009).
- **Validation order**:
  1. email;
  2. names;
  3. picker (none picked, duplicate id, bad level, not selectable or unknown id).

  Every error is collected and shown, and every value is kept.
- **Then**:
  1. rate limits (research D12);
  2. seal and send (`issue_invitation`).

  A delivery failure still counts against the limit, and nothing from the form is stored
  (FR-017).

### The teacher page (FR-039–FR-041)

- **Shown**: the email, read-only (FR-039), and the names as inputs.
- **Picker**: every selectable institution, with the teacher's links checked at their levels.
  Linked institutions that are no longer selectable are added as checked rows, marked
  "deactivated", with the level as text (FR-011).
- **Also shown**: the **Can create competitions** checkbox, a **Save** button, and a **Remove
  teacher** link to the confirmation.
- **Saving**:
  - An unchanged link stays exactly as it was (FR-040).
  - Adding an unselectable or unknown institution is refused with `400` and the message "This
    educational institution cannot be selected.", and nothing changes.
  - Editing never ends the teacher's sessions (FR-041).

### Remove (FR-042)

- **Confirmation**: "Remove <name> as a teacher? They lose the teacher role, their institutions
  and the competitions setting. If they have no other role, they can no longer sign in. Their
  email, names and consent records stay until they delete their data."
- **Effect**: the role, links and profile are deleted, the cut-off is set, the person is
  deactivated if no role is left, and all their sessions are deleted.

---

## 2. Invitations — `app/routers/invitations.py` (public)

| Method | Path | Outcome → response |
|---|---|---|
| GET | `/invitations/{token}` | `Acceptable` → `200` acceptance page. `AlreadyHeld` → `200` "You are already a teacher." with a **Sign in** link. `Expired` → `410` "This invitation has expired; ask for a new one." `Invalid` or `Refused` → `400` neutral message. **Never writes.** |
| POST | `/invitations/{token}` | Form field `consent_text_id` only. Any other field is ignored (FR-029). Success → `303` → `/login?prefill=<sealed>`. `AlreadyHeld` → `303` → `/invitations/{token}`. `ConsentChanged` → `409` acceptance page with the new text and "The consent text has changed since you opened this page. Please read it again." `Expired` → `410`. `Invalid` or `Refused` → `400` neutral message. |

The neutral message, one text for every non-expiry failure (FR-033): "This invitation cannot be
accepted. Ask the person who invited you to send a new one."

### The acceptance page (FR-024)

- **Heading**: "Invitation to Student Competitions".
- **Who invites**: "<inviter display name> (<inviter email>) invites you to join as a teacher."
- **What will be stored**, read-only, as a definition list:
  - email;
  - first name, last name;
  - each institution "Name (Region)" by its **current** names, with Read or Write;
  - Can create competitions, Yes or No.
- **Expiry**: "This invitation expires on 2026-10-22 14:05 UTC."
- **The current consent text** for the role (paragraphs).
- **The form**: `method=post`, a hidden `consent_text_id`, and the **I agree** button.
- **Under the button**: "If any detail is wrong, ask the person who invited you for a new
  invitation, or accept and ask them to correct it."

Nothing on the page is editable, and the page shows nothing about the signed-in session.

---

## 3. Sign-in page — `app/routers/auth.py` (CHANGED)

`GET /login` gains:

- **An optional `prefill` query parameter.** When it unseals (purpose `login-prefill`, 10
  minutes), the email input is filled and the page says "Your account is ready. Send yourself a
  sign-in code to continue." Otherwise the parameter is ignored.
- **The existing redirect for a signed-in visitor**, which is unchanged, so a self-invited
  administrator (US6) keeps their session.
- **A link "Delete my data"** to `/data-deletion`, shown to everyone (FR-049).

`POST /login` and `POST /login/code` are unchanged.

---

## 4. Profile — `app/routers/profile.py`

| Method | Path | Purpose | Success | Other |
|---|---|---|---|---|
| GET | `/profile` | Own read-only profile | `200` | — |
| GET | `/profile/withdraw` | Confirmation step | `200` | `409` "There is no data stored on your consent to withdraw." when `has_consent_data` is false |
| POST | `/profile/withdraw` | Withdraw consent | `303` → `/data-erased`, session cookie cleared | `409` as above |

### The profile (FR-043, FR-044)

- **Data**: email, first and last name (when stored), and roles (labels in the fixed order).
- **For a teacher**: institutions "Name (Region) — Read/Write" (deactivated ones marked) and **Can
  create competitions**.
- **Consent records**, newest first: accepted time (UTC), role, version, and the full text.
- **The note**: "Corrections to teacher data are made by an administrator."
- **Withdraw consent** links to `/profile/withdraw`, only when `has_consent_data` (FR-045).
- **The header**: the signed-in email becomes a link to `/profile`, on every page.

### The confirmation (FR-046)

- **What will be erased**: the first and last name, and the email unless the person holds the
  administrator role, in which case "Your administrator role and email stay: they come from the
  deployment configuration."
- **Roles removed**: every invitable role held, here Teacher.
- **Consequences**: "You will be signed out everywhere." With no role left: "You will no longer
  be able to sign in."
- **Buttons**: **Withdraw consent** (POST) and **Cancel** (link to `/profile`).

---

## 5. Data deletion — `app/routers/data_deletion.py` (public)

| Method | Path | Outcome → response |
|---|---|---|
| GET | `/data-deletion` | `200` form: one `email` field and **Send link**. It explains that the link erases data stored on consent. |
| POST | `/data-deletion` | Malformed address → `400` form "Enter a valid email address." Otherwise, within limits or not → `303` → `/data-deletion/requested`. The background task runs only when within limits (research D10, D12). |
| GET | `/data-deletion/requested` | `200` "If this email is registered, we have sent you a link." (FR-050) |
| GET | `/data-deletion/confirm/{token}` | Usable → `200` confirmation page. Expired or used → `410` "This link has expired; request a new one." with a link to `/data-deletion`. Invalid → `400` neutral "This link cannot be used. Request a new one." **Never writes.** |
| POST | `/data-deletion/confirm/{token}` | Usable → erase → `303` → `/data-erased`. The cookie is cleared when this browser's session belongs to the erased user. `410` and `400` as for `GET`. |
| GET | `/data-erased` | `200` "Your data has been erased." It says that consent records are kept as proof, and that any session was ended. |

### The confirmation page (FR-053)

- **What will be erased**: the email address and names (shown), the roles that will be removed,
  and, for a holder of the administrator role, "Your administrator role and email stay."
- **Button**: **Delete my data** (POST).

---

## 6. Status codes used

| Status | Meaning here |
|---|---|
| `200` | page |
| `303` | after every successful `POST`; sign-in and role-choice redirects |
| `400` | invalid form; invalid or refused link (neutral) |
| `403` | access denied (wrong current role), or cross-site request refused |
| `404` | teacher not found (unknown id, or not a current teacher) |
| `409` | consent text changed; nothing to withdraw |
| `410` | invitation expired; deletion link expired or used |
| `429` | invitation rate limit |
| `503` | invitation email could not be sent; database unavailable |

Every error page is the friendly layout, and no stack trace is shown (constitution, Operational
Constraints).
