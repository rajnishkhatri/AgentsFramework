# V-R — PT2 Reading discrepancy report

| Field | Value |
|---|---|
| Task | Phase 3 VALIDATE **V-R** (`docs/plan/exam-module-official-forms.tasks.md`) |
| Spec / plan | FR-P2-2, FR-P2-10, FR-P2-12, FR-P2-17, FR-P2-18 · plan §6.4 |
| Form | `act-practice-test-2` · Enhanced ACT · `delivery: asset-served` |
| Base | `.worktrees/exam-official-forms` on `feat/exam-official-forms` @ `8269a1b32ab06bb3bdfe1aeafdef4b01c251ad74` |
| Date | 2026-09-03 |
| **Verdict** | **PASS** |
| Mismatch count | **0** (required §6.4 checks) |
| Blockers | **none** |

Every Reading item is covered (36 rows). Scripted key match is 100 % (36/36 booklet letters vs booklet scoring-key page). Findings that are **not** oracle mismatches are in [Observations](#observations) for `sdd-converge` (no hand-edits of `_generated/`).

This pass is **data-path** validation of the generated client form + server keys against official JSON and the booklet PDF. It did **not** sit the section in a browser (that is **V-T**).

---

## Method

Oracle stack (same as A-2 / 805 on 2026-09-03 — PyMuPDF, do not eyeball two-column keys):

| Artifact | Path |
|---|---|
| Official JSON | main checkout `docs/preact9secure/json/act-practice-test-2.json` |
| Booklet PDF | `docs/preact9secure/preact/ACT-Test-Prep-ACT-Practice-Test-2-Form.pdf` |
| Extractor | `docs/preact9secure/tools/extract_forms.py` (`locate_sections` + `parse_keys`, `key_style: table`) |
| Generated client | worktree `frontend/lib/adapters/engine/exam_forms/_generated/act-practice-test-2.client.ts` |
| Generated keys | worktree `frontend/lib/adapters/engine/exam_forms/_generated/act-practice-test-2.keys.ts` |
| Interpreter | `.venv/bin/python` (worktree `.venv` → same 3.13 as main) |

Provenance:

- PDF sha256 `2819aa723f2d205d71f6e897a8fbcce54e3b3975b1598d867a1ea432d052c63d` **==** JSON `source.sha256` (70 pages).
- Reading section pages **28–35** (`READING TEST` · 40 minutes · 36 questions · `END OF TEST` on p35).
- Scoring-key oracle: booklet **page 65** `Reading Scoring Key` (not the separate online key PDF — see observations).

Image-necessary rule (`exam_image_rule.needsImage`): image iff `text_fidelity ∈ {math-notation, low}` **or** passage `is_figure`. Converter treats non-Science passages as not-figure. Spec / A-2: Reading images = **0**.

Scripted grade set = official key for every item. Server path injects `keys.answer_letter` then `scoreExamSection` (unscored excluded from raw/scale). Simulated here from the generated artifacts; no live `finishExamSection` call.

---

## Section-level checks

| Check | Expected [PDF/JSON] | Actual [generated] | Verdict |
|---|---|---|---|
| Item count | JSON `question_count` / `declared_question_count` / `len(questions)` = 36; PDF header 36 | 36 client questions | **PASS** |
| Scored / unscored | JSON + PDF key page: 27 scored, 9 Not Scored (Q19–27) | 27 scored, 9 `scored: false` (Q19–27) | **PASS** |
| `choice_count` | JSON 4; every item 4 choices; even booklet F/G/H/J | section `choice_count: 4`; 36×4 choices; letters normalized A–D | **PASS** |
| Images (text-first) | all `text_fidelity: ok`; Reading images = 0 | 0 question `image`; 0 passage `image` | **PASS** |
| Passages | JSON 4 shared blocks (I–IV) with `question_numbers` 1–9 / 10–18 / 19–27 / 28–36 | 4 passages; labels, intros, texts, `question_numbers` byte-equal to JSON | **PASS** |
| Passage membership | each item `passage` label ∈ block whose `question_numbers` contains N | 36/36 | **PASS** |
| Keys vs scoring-key page | PyMuPDF `parse_keys` booklet p65 | `FORM_KEYS.booklet_letter` == PDF == JSON `answer` for 36/36 | **PASS** |
| Normalized letter | even F/G/H/J → A/B/C/D | `answer_letter` matches for 36/36 | **PASS** |
| Reporting category | PDF + JSON CS/KID/IKI; Not Scored → null | 36/36 match (KID 13 · CS 8 · IKI 6) | **PASS** |
| Scale table | JSON `scoring.scale_conversion` 0–27; PDF `raw_max` 27 | 28 rows, equal; `27 → 36`; `0 → 1` | **PASS** |
| Unscored excluded from raw/scale | FR-P2-18: 9R field-test out of raw; scale keyed on 0–27 | Q19–27 `scored: false`; table max raw 27 | **PASS** |
| Composite membership | Enhanced ACT composite = E+M+R (FR-P2-17) | `composite_sections = [english, math, reading]`; `reading.composite = true` | **PASS** |
| Client leak | FR-P2-3: no answer-bearing fields on client items | no `answer_letter` / rationale / `booklet_letter` on Reading questions | **PASS** |
| Stem + choices vs JSON | FR-P2-10 `ok` items = text from JSON | 36 stems + 144 choice texts equal | **PASS** |
| Stem + choices vs PDF | plan §6.4: PDF page text + JSON | 36 stems + 144 choices found on Reading pages 28–35 (alnum containment) | **PASS** |

E+M+R composite *value* is not computable from Reading alone — left to **V-T**.

---

## Per-item discrepancy table

Rows = `question_count` (36). Each check is PASS unless noted. Stem column is a short identifier only (©ACT stems are not reproduced in full).

| Item | Checks (stem / choices / image / passage / key / scored) | Expected [PDF/JSON] | Actual | Verdict |
|---|---|---|---|---|
| 1 | stem · 4 choices · image · passage · key · scored | I · A · CS · scored | I · A · CS · scored · image null | **PASS** |
| 2 | stem · 4 choices · image · passage · key · scored | I · G→B · KID · scored | I · booklet G / AD B · KID · image null | **PASS** |
| 3 | stem · 4 choices · image · passage · key · scored | I · B · KID · scored | I · B · KID · image null | **PASS** |
| 4 | stem · 4 choices · image · passage · key · scored | I · F→A · KID · scored | I · booklet F / AD A · KID · image null | **PASS** |
| 5 | stem · 4 choices · image · passage · key · scored | I · C · KID · scored | I · C · KID · image null | **PASS** |
| 6 | stem · 4 choices · image · passage · key · scored | I · H→C · IKI · scored | I · booklet H / AD C · IKI · image null | **PASS** |
| 7 | stem · 4 choices · image · passage · key · scored | I · D · IKI · scored | I · D · IKI · image null | **PASS** |
| 8 | stem · 4 choices · image · passage · key · scored | I · F→A · IKI · scored | I · booklet F / AD A · IKI · image null | **PASS** |
| 9 | stem · 4 choices · image · passage · key · scored | I · A · IKI · scored | I · A · IKI · image null | **PASS** |
| 10 | stem · 4 choices · image · passage · key · scored | II · G→B · CS · scored | II · booklet G / AD B · CS · image null | **PASS** |
| 11 | stem · 4 choices · image · passage · key · scored | II · C · CS · scored | II · C · CS · image null | **PASS** |
| 12 | stem · 4 choices · image · passage · key · scored | II · H→C · IKI · scored | II · booklet H / AD C · IKI · image null | **PASS** |
| 13 | stem · 4 choices · image · passage · key · scored | II · A · KID · scored | II · A · KID · image null | **PASS** |
| 14 | stem · 4 choices · image · passage · key · scored | II · J→D · KID · scored | II · booklet J / AD D · KID · image null | **PASS** |
| 15 | stem · 4 choices · image · passage · key · scored | II · A · KID · scored | II · A · KID · image null | **PASS** |
| 16 | stem · 4 choices · image · passage · key · scored | II · H→C · CS · scored | II · booklet H / AD C · CS · image null | **PASS** |
| 17 | stem · 4 choices · image · passage · key · scored | II · B · IKI · scored | II · B · IKI · image null | **PASS** |
| 18 | stem · 4 choices · image · passage · key · scored | II · J→D · KID · scored | II · booklet J / AD D · KID · image null | **PASS** |
| 19 | stem · 4 choices · image · passage · key · scored | III · B · Not Scored | III · B · `scored: false` · image null | **PASS** |
| 20 | stem · 4 choices · image · passage · key · scored | III · J→D · Not Scored | III · booklet J / AD D · `scored: false` · image null | **PASS** |
| 21 | stem · 4 choices · image · passage · key · scored | III · B · Not Scored | III · B · `scored: false` · image null | **PASS** |
| 22 | stem · 4 choices · image · passage · key · scored | III · G→B · Not Scored | III · booklet G / AD B · `scored: false` · image null | **PASS** |
| 23 | stem · 4 choices · image · passage · key · scored | III · A · Not Scored | III · A · `scored: false` · image null | **PASS** |
| 24 | stem · 4 choices · image · passage · key · scored | III · F→A · Not Scored | III · booklet F / AD A · `scored: false` · image null | **PASS** |
| 25 | stem · 4 choices · image · passage · key · scored | III · B · Not Scored | III · B · `scored: false` · image null | **PASS** |
| 26 | stem · 4 choices · image · passage · key · scored | III · F→A · Not Scored | III · booklet F / AD A · `scored: false` · image null | **PASS** |
| 27 | stem · 4 choices · image · passage · key · scored | III · C · Not Scored | III · C · `scored: false` · image null | **PASS** |
| 28 | stem · 4 choices · image · passage · key · scored | IV · J→D · KID · scored | IV · booklet J / AD D · KID · image null | **PASS** |
| 29 | stem · 4 choices · image · passage · key · scored | IV · B · KID · scored | IV · B · KID · image null | **PASS** |
| 30 | stem · 4 choices · image · passage · key · scored | IV · H→C · KID · scored | IV · booklet H / AD C · KID · image null | **PASS** |
| 31 | stem · 4 choices · image · passage · key · scored | IV · D · CS · scored | IV · D · CS · image null | **PASS** |
| 32 | stem · 4 choices · image · passage · key · scored | IV · F→A · KID · scored | IV · booklet F / AD A · KID · image null | **PASS** |
| 33 | stem · 4 choices · image · passage · key · scored | IV · D · CS · scored | IV · D · CS · image null | **PASS** |
| 34 | stem · 4 choices · image · passage · key · scored | IV · F→A · CS · scored | IV · booklet F / AD A · CS · image null | **PASS** |
| 35 | stem · 4 choices · image · passage · key · scored | IV · C · KID · scored | IV · C · KID · image null | **PASS** |
| 36 | stem · 4 choices · image · passage · key · scored | IV · G→B · CS · scored | IV · booklet G / AD B · CS · image null | **PASS** |

Key letters: left of `→` is booklet (PDF p65 / JSON `answer`); right is client `A–D` (`FORM_KEYS.answer_letter`).

---

## Shared passage blocks

| Label | JSON pages | `question_numbers` | intro/text vs JSON | `image` | `lines[]` in JSON | Verdict (mapping) |
|---|---|---|---|---|---|---|
| I | 28–29 | 1–9 | equal (intro 560 chars · text 4469) | null | 85 (not emitted) | **PASS** |
| II | 30 | 10–18 | equal (intro 407 · text 4004) | null | 78 (not emitted) | **PASS** |
| III | 32 | 19–27 | equal (intro 270 · text 4567; table flattened into text) | null | 124 (not emitted) | **PASS** |
| IV | 34 | 28–36 | equal (intro 358 · text 4558) | null | 91 (not emitted) | **PASS** |

Every generated item’s `passage` label resolves to the block whose `question_numbers` contains that item. `ExamPassageBlock` looks up by that label (`title` / `intro` / `text`; figure `<img>` only when `passage.image` is set — never here).

---

## Scoring-key evidence (booklet p65)

PyMuPDF extract of `Reading Scoring Key` (page 65), compared to JSON `answer` and `FORM_KEYS.booklet_letter` — **0 mismatches**.

```
1 A CS · 2 G KID · 3 B KID · 4 F KID · 5 C KID · 6 H IKI · 7 D IKI · 8 F IKI · 9 A IKI
10 G CS · 11 C CS · 12 H IKI · 13 A KID · 14 J KID · 15 A KID · 16 H CS · 17 B IKI · 18 J KID
19 B Not Scored · 20 J Not Scored · 21 B Not Scored · 22 G Not Scored · 23 A Not Scored
24 F Not Scored · 25 B Not Scored · 26 F Not Scored · 27 C Not Scored
28 J KID · 29 B KID · 30 H KID · 31 D CS · 32 F KID · 33 D CS · 34 F CS · 35 C KID · 36 G CS
KID = of 13 · CS = of 8 · IKI = of 6 · Total Reading Raw Score = of 27
```

Scripted all-official-keys: 36/36 `answer_letter` self-match; raw_correct = 27; `raw_scored_total` = 27; scale `27 → 36`. Unscored 9 do not enter raw.

---

## Observations (not counted as mismatches)

These do **not** fail V-R’s required oracles. Route to `sdd-converge` only if product wants them as follow-ups — do not hand-edit `_generated/`.

1. **Line numbers dropped.** Official JSON passages carry `lines[]`. Generated `ExamPassage` / `ExamPassageBlock` emit `text` only (one `whitespace-pre-wrap` paragraph). **17** Reading stems cite line ranges (`lines 26–45`, `line 28`, …). FR-P2-12 requires shared passage *text*, not gutter line numbers. Mapping still PASSes. Live usability is a **V-T** / converge question.

2. **Dual-passage I headings live in the PDF, not in JSON `text`.** Booklet p28 has in-body headings `Passage A by Robert Sullivan` and `Passage B by Elizabeth Gaffney` (A = lines 1–45, B starts line 46). Official JSON concatenates both into one `text` blob; headings appear only in `intro` (source attribution). Converter copies JSON exactly (`text`/`intro` equal). Items 1–9 refer to Passage A / B / both. This is a **source-JSON vs PDF** gap, not converter drift.

3. **Passage III table is text, not an image.** Booklet p32 has a silk-properties table; intro mentions “the graphic.” Items 24–27 ask “based on the table.” Text-first + `exam_image_rule` → Reading `image = null` (A-2 expected 0). Table values (bark-spider MA silk, Kevlar, high-tensile steel, …) are in `passage.text`. Layout is not tabular. Per spec this is **PASS**.

4. **No live render.** Stems/choices/passages were checked on the generated client artifact (what the runner consumes), not a Chromium walk of 36 items. Placeholder / `@container` layout / review badge for the 9 field-test items were not screenshot-verified here.

5. **Do not use `ACT-Nat-Online-Practice-Test-2-Scoring-Key.pdf` as the booklet oracle.** That file is form `QU04003-2.CJ22866` (10 pages). Its Reading key is already A–D (matches our *normalized* `answer_letter`, not booklet F/G/H/J). A-2 / handover pin the oracle to the **booklet** scoring-key page via `parse_keys`.

6. **`context_html` duplicates passage `text` on every item** (HTML-escaped). `ExamPassageBlock` reads `section.passages`, not `context_html`. Redundant, not a §6.4 fail.

---

## Blockers

**None.** V-R required gates are green: report exists, 36 items covered, key match 100 %, counts 36/27, `choice_count` 4, Reading images 0, four shared passages with correct `question_numbers`.

Do not treat observations 1–3 as merge blockers unless V-T shows learners cannot use line refs / A–B / the silk table.
