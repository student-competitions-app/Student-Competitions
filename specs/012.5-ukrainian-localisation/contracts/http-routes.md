# Contract: HTTP routes (Milestone 12.5)

## 1. `POST /language` (new, `app/routers/language.py`)

Public (every role and signed out), like `POST /theme`. Reads and writes no data apart from the
cookie. Passes the application-wide cross-site check (a cross-site submission gets the existing
"Request refused" page, 403, and no cookie).

| Form field | Meaning |
|---|---|
| `language` | `uk` or `en` |
| `next` | the page to return to: the switch's `return_path` |

| Case | Response |
|---|---|
| `language` is `uk` or `en`, `next` accepted | `303` to `next`; `Set-Cookie: sc_lang=<code>; Max-Age=31536000; Path=/; HttpOnly; SameSite=lax` (+ `Secure` in production) |
| `next` refused (not a plain local path, a `POST`-only page, unknown route) | `303` to `/` signed in, `/login` signed out; cookie set as above |
| `language` missing or not exactly `uk`/`en` | `303` as above; **no** `Set-Cookie` |

The return-address check is `app/core/return_path.resolve_return(request, raw)`, shared with
`POST /theme` (moved from `app/routers/theme.py` unchanged).

## 2. Every page (changed)

- `<html lang="uk|en">` from the request's language.
- The top bar holds the language switch (signed in and out, every page including errors).
- Every text the application writes is in the request's language (spec FR-018).

## 3. Unchanged routes, changed behaviour

| Route | Change |
|---|---|
| `POST /theme` | uses `resolve_return`; behaviour unchanged |
| `POST /login` | the sign-in code email in the request's language |
| `POST /data-deletion` | the deletion email in the request's language, expiry in Kyiv time |
| invitation sends (admin teachers, teacher students) | the invitation email bilingual, Ukrainian first |
| `GET /invitations/{token}`, `GET /profile` | the consent text in two marked parts; times in the new format |
| `GET /admin/teachers` | "Date of consent" in the new date format |
| competition forms | with no known zone, the time is read as Kyiv time; hint "Time zone: Europe/Kyiv" |
| `GET /admin/components` | a **Language switch** section; the content stays English |
| error handlers (`app/main.py`) | translated headings and sentences; framework `detail` as it comes |

`/healthz` is unchanged and untranslated.
