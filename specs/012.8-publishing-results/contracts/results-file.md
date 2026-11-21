# Contract: The Results File (Milestone 12.8)

What every stored file holds, whatever the design review settles about its look. Layout and
wording are reviewed with the product owner (FR-038); this contract is the part the tests check.
English texts are shown; the Ukrainian file holds their catalogue translations.

## Content, in order

1. **Logo**: the milestone 12.7 emblem in dark ink, once, on page 1.
2. **Title**: "Results of “<competition name>”".
3. **Subject**: the subject's name.
4. **Times**:
   - "Started: <start>" and "Finished: <finish>": date and time in Kyiv time, labelled ("14
     March 2027, 10:00 (Kyiv time)");
   - "Published: <date>": the date in Kyiv time.
5. **Body**: either
   - for each region, in order: a heading with the region's name, then one line per team, "<institution>, <team>,
     <score>", institutions then teams in order; or
   - "No teams took part in this competition." when the competition has no teams.
6. **Footer on every page**: "Page <n> of <total>".

## Rules

| Rule | Checked by |
|---|---|
| Every team of the competition appears exactly once, deleted teams and teams of deactivated institutions or regions included, with no mark | `test_results_service.py` (snapshot), `test_results_pdf.py` (text) |
| Order: regions, institutions within a region, teams within an institution, by `name_sort_key`, ties by id | snapshot tests |
| Score = sum of the team's grades; 0 with no answers | snapshot tests |
| Names as entered, never translated, Cyrillic extractable as typed | text read back with pypdf |
| No question text, reference answer, answer, grade per question or member name | text read back: none of the seeded strings appear |
| Labels in the file's language | text read back per language |
| Every page numbered, total correct | text read back from a multi-page sample |
| Fonts embedded (subset), logo image present | pypdf: font descriptors carry a font file; one image on page 1 |
| Metadata: title, language `uk-UA` / `en-GB`, creation date = publishing moment, no author | pypdf metadata |
| Stored once; served byte for byte; unchanged after later renames, deactivations, deletions | service and route tests compare bytes |
