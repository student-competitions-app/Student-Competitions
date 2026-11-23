# Data Model: A Competition's Questions Only After It Starts, and Study Materials (Milestone 12.10)

**No schema change and no migration.** The milestone reads tables that already exist and keeps
one kind of value in the process's memory. Sections 1–2 are the reads, 3–4 the values the files
are made from, and 5 the kept files.

## 1. Read: a competition's questions file

| From | What | Rule |
|---|---|---|
| `competitions` | `name`, `starts_at`, status (derived) | The status must be **In progress**, **Finished** or **Published**. A deactivated subject's **In progress** competition is not found (12.1 visibility). |
| `subjects` | `name` | Read at the download, so a rename shows (FR-018). |
| `competition_questions` | `text`, ordered by `id` | Every copy, additional and deleted-in-the-bank included (FR-014, FR-016). `reference_answer` and `question_id` are **not** read into the sheet. |

`questions.is_additional` is not joined. The questions file never reads the mark (FR-015).

## 2. Read: a subject's study materials

| From | What | Rule |
|---|---|---|
| `subjects` | `name`, `is_active` | The subject must exist and be active (FR-023). |
| `questions` | `text`, `reference_answer`, ordered by `id` ascending | `subject_id = s AND deleted_at IS NULL AND is_additional = FALSE` (FR-027, FR-028). `id` is not selected. |

It is served by the existing index `ix_questions_subject_id`. At about 150 rows of at most the
column limit each, the read is the cheap part of a download. Rendering is the slow part
(research R6).

## 3. `QuestionsSheet` (value, not stored)

A frozen dataclass in `app/services/question_files.py`; the only input of `render_questions_pdf`.

| Field | Type | Source |
|---|---|---|
| `competition_name` | `str` | `competitions.name`, as entered |
| `subject_name` | `str` | `subjects.name` at the download |
| `starts_at` | aware `datetime` (UTC) | `competitions.starts_at`; shown in Kyiv time, labelled; also the PDF creation date |
| `texts` | `tuple[str, ...]` | the copies' texts in the competition's order; may be empty |

It has no field for a bank number, a mark or a reference answer, so none can reach the file.

## 4. `StudyMaterials` (value, not stored in the database)

A frozen dataclass in `app/services/question_files.py`. It is the only input of
`render_study_materials_pdf`, and it is what a kept file is compared with (§5).

| Field | Type | Source |
|---|---|---|
| `subject_name` | `str` | `subjects.name` at the download |
| `downloaded_on` | `date` | today in Kyiv (`competitions.utc_now()` in `KYIV`); shown as "Downloaded: …"; its Kyiv midnight is the PDF creation date |
| `entries` | `tuple[tuple[str, str], ...]` | `(text, reference_answer)` per question of §2, oldest first; may be empty |

Two values are equal exactly when the file they make would show the same things: name, date,
every text and answer, and their order. The language is not a field. It is part of the key (§5)
and an argument of the renderer.

## 5. `StudyMaterialsCache` (in process memory)

One instance per running application, created in `lifespan` as `app.state.study_materials`, so
it starts empty on every restart, deployment and wake (FR-037).

| Part | Type | Meaning |
|---|---|---|
| `_kept` | `dict[tuple[int, Language], Kept]` | the newest file per (subject id, language) |
| `Kept.materials` | `StudyMaterials` | exactly what the kept file was made from |
| `Kept.content` | `bytes` | the PDF |
| `_locks` | `dict[tuple[int, Language], threading.Lock]` | one per key, for single-flight |
| `_guard` | `threading.Lock` | guards the creation of entries in `_locks` |

**Life of an entry**:

```text
(absent) ──first download──▶ Kept(m₁, file(m₁))
Kept(m₁) ──download reads m₁──▶ Kept(m₁)          (bytes given, nothing made)
Kept(m₁) ──download reads m₂ ≠ m₁──▶ Kept(m₂, file(m₂))   (made, replaces)
(any) ──application starts──▶ (absent)
```

**Invariants**:

- `Kept.content == render_study_materials_pdf(Kept.materials, language)`, always.
- A request returns `Kept.content` only if `Kept.materials` equals the materials that request has
  just read (FR-033, FR-035).
- At most one entry per (subject, language) (FR-032). The size is bounded by the active subjects
  × 2 languages.
- No other module reads or writes it, and nothing removes an entry on a change (FR-034).
- A deactivated subject's entry may stay in memory, but it is never given: the route refuses the
  subject before the cache is asked (FR-033).

## 6. Not personal data

Neither file nor the cache holds anything about a person: question texts, reference answers,
competition and subject names, dates. Nothing is logged on a download.
