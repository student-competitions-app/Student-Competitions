# Data Model: Creating, Editing and Cancelling Competitions (Teacher) (Milestone 12.1)

Phase 1 of [plan.md](./plan.md). One new table; one changed rule on `subjects`; one browser
cookie that is never stored on the server. Decisions are in [research.md](./research.md).

## 1. Competition: table `competitions` (new)

Model `Competition` in `app/models/competition.py`, exported from `app/models/__init__.py`.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | integer, primary key | no | Used in addresses; never shown as a number. |
| `subject_id` | integer, FK `subjects.id`, indexed | no | Set at creation, never written again (FR-001). No `ON DELETE`: a subject with a competition cannot be deleted (FR-039). |
| `name` | `String(200)` | no | As entered after `clean_name`: trimmed, 1–200 code points, no control characters (FR-002). |
| `name_key` | `String(600)` | no | `name_key(name)`: NFC, then case-folded. Never shown. |
| `starts_at` | `UTCDateTime` | no | The start, UTC, always a whole minute (seconds and microseconds 0) (FR-004, FR-019). |
| `cancelled_at` | `UTCDateTime` | yes | Set once by cancelling; never cleared (FR-007). |
| `stopped_at` | `UTCDateTime` | yes | Set once by stopping, a later 12.x milestone; tests set it directly in this one (FR-008). |
| `created_at` | `UTCDateTime` | no | Set once at creation. |
| `updated_at` | `UTCDateTime` | no | Reset by an edit that changes the name or the start; cancelling leaves it alone. |

**Constraints and indexes**

| Name | Definition | Why |
|---|---|---|
| `ix_competitions_subject_id` | index on `subject_id` | Every list, offer and use count reads by subject. |
| `uq_competitions_subject_name_live` | unique index on `(subject_id, name_key)` `WHERE cancelled_at IS NULL AND stopped_at IS NULL`, declared with both `sqlite_where` and `postgresql_where` | Names unique ignoring case among upcoming and in-progress competitions of a subject, under concurrency (FR-003, R3). |
| `ck_competitions_one_end` | `CHECK (cancelled_at IS NULL OR stopped_at IS NULL)` | Never both cancelled and finished (R1). |

**Not stored**: who created or changed it (FR-001), a status (R1, R2), a duration (FR-004).
**Not personal data**: no column names a person, so data erasure is unaffected.

## 2. Status (derived, never stored)

`CompetitionStatus` in `app/services/competitions.py`, derived by `status_of(row, now)` with one
`now` per service call (R2):

| Order | Condition | Status | Badge |
|---|---|---|---|
| 1 | `cancelled_at IS NOT NULL` | **Cancelled** | `muted` |
| 2 | `stopped_at IS NOT NULL` | **Finished** | `neutral` |
| 3 | `starts_at > now` | **Upcoming** | `info` |
| 4 | otherwise | **In progress** | `success` |

**State transitions**

```text
             start passes (derived, nobody acts)
  Upcoming ─────────────────────────────────────▶ In progress
     │                                               │      │
     │ cancel                              cancel    │      │ stop (later 12.x)
     ▼                                               ▼      ▼
  Cancelled ◀──────────────────────────────────────────    Finished
  (final: never changes again)                      (final: cannot be cancelled)
```

| Action | Allowed from | Writes | Refused with |
|---|---|---|---|
| Edit | Upcoming | `name`, `name_key`, `starts_at`, `updated_at` | "has already started", "has been cancelled", "has finished … can no longer be edited" |
| Cancel | Upcoming, In progress | `cancelled_at` | "is already cancelled", "has finished and cannot be cancelled" |
| Stop | In progress (later 12.x) | `stopped_at` | — |

## 3. Visibility and the live name (derived)

| Term | Definition | Used by |
|---|---|---|
| **live** | `cancelled_at IS NULL AND stopped_at IS NULL` (Upcoming or In progress) | Name uniqueness (the partial index). |
| **visible** | the subject is active, or `stopped_at IS NOT NULL` | Every page and action: an invisible competition is "not found" (FR-037). |
| **offered subject** | active, or deactivated with at least one competition with `stopped_at IS NOT NULL` | The subject list and the subject check (FR-010, FR-012). |

## 4. Subject: table `subjects` (unchanged schema; one rule changed)

- `count_subject_uses` adds the number of competitions of the subject, in any status, so a
  subject used by any competition cannot be deleted (FR-039). The milestone 11 count of questions
  stays.
- Deactivating a subject writes nothing to its competitions; their visibility is derived (§3).

## 5. Time-zone preference: cookie `sc_time_zone` (browser only)

| Property | Value |
|---|---|
| Name | `sc_time_zone` |
| Value | An IANA time-zone name, such as `Europe/Kyiv`; at most 64 characters. |
| Written by | `app/static/js/time-zone.js` only; `Path=/`, `Max-Age=31536000`, `SameSite=Lax`, `Secure` over HTTPS; not `HttpOnly`. |
| Read by | `app.core.time_zone.read_time_zone` on every request. |
| Accepted | Only a name in `zoneinfo.available_timezones()`; anything else means "no zone known" (UTC, labelled "UTC"). |
| Stored on the server | Never; never logged. |

## 6. Validation rules (from the spec)

| Field | Rule | Message |
|---|---|---|
| `name` | control characters refused | "The name cannot contain tabs, line breaks or other control characters." |
| `name` | trimmed, not empty | "Enter a name." |
| `name` | at most 200 code points | "The name can be at most 200 characters." |
| `name` | unique ignoring case among live competitions of the subject, excluding itself | "A competition named “<entered name>” already exists in this subject." |
| `start_date` | present | "Enter the start date." |
| `start_date` | `YYYY-MM-DD`, a calendar date, convertible to UTC | "Enter a real start date." |
| `start_time` | present | "Enter the start time." |
| `start_time` | `H:MM`, `HH:MM` or `HH:MM:SS`, real values; seconds dropped | "Enter a real start time." |
| `start_time` | exists in the form's zone | "There is no <HH:MM> on <d Month yyyy> in <zone> because the clocks go forward. Enter another time." |
| `start_date` | the start in UTC is later than the moment of saving | "The start must be in the future." |
| `time_zone` (hidden) | a known IANA name, else UTC | — (never an error) |

The name messages are the existing ones of `app.schemas.names`, shared with subjects, regions,
institutions, classes and teams.

## 7. Migration `competitions` (revision after `09cbcbe472be`)

File `migrations/versions/2026_11_02_<rev>_competitions.py`:

- **upgrade**: create `competitions` with its columns, the foreign key to `subjects.id`, the check
  constraint `ck_competitions_one_end`, the index `ix_competitions_subject_id` and the partial
  unique index `uq_competitions_subject_name_live` (with `sqlite_where` and `postgresql_where`).
- **downgrade**: drop the indexes and the table. No other table changes, so the downgrade loses
  only competitions.
- Covered by the existing stairway (upgrade, downgrade, upgrade) and model-drift checks on both
  engines.
