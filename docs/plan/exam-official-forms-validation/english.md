# V-E — PT2 English discrepancy report

**Task:** Phase 3 VALIDATE V-E (`docs/plan/exam-module-official-forms.tasks.md`)
**Plan oracle:** §6.4 per-section fidelity table
**Form:** `act-practice-test-2` (Enhanced ACT) · section **english**
**Base:** `.worktrees/exam-official-forms` on `feat/exam-official-forms` @ `8269a1b32ab06bb3bdfe1aeafdef4b01c251ad74`
**Artifacts:** gitignored `frontend/lib/adapters/engine/exam_forms/_generated/act-practice-test-2.{client,keys}.ts`
**Source:** `docs/preact9secure/` (main checkout; ©ACT — not committed)
**Date:** 2026-09-03
**Verdict vs V-E criteria: PASS**

This file is report-only. No exam code or `_generated/` content was edited. Findings (none) would route to sdd-converge, never to hand-edits of generated artifacts.

©ACT stem, choice, and passage text is **not** reproduced here. Comparisons used exact string equality and SHA-256; the table records lengths, letters, counts, and PASS/FAIL only.

---

## V-E pass/fail criteria

| Criterion | Result |
|---|---|
| Report exists at `docs/plan/exam-official-forms-validation/english.md` | yes |
| Every item covered (rows = `question_count` = 50) | **50/50** items 1–50 |
| Key match 100% for the scripted answer set | **50/50** `correct=true`; booklet letter = PDF scoring-key page = JSON `answer` |
| Stem/choices (`ok` items) match source | **50/50** exact vs JSON; each stem + 4 choice texts found on the item's PDF page |
| Image used iff image-necessary rule | **0** English images (all `text_fidelity=ok`, non-figure passages) |
| Passage block matches `question_numbers` | **6/6** passages I–VI; every item's label is in the owning passage's `question_numbers` |
| Unscored excluded from raw/scale; composite = E+M+R | field-test **16–25** excluded; scale 40→36 / 0→1; `composite_sections = english, math, reading` |
| Mismatch count | **0** |
| Blockers | **none** |

---

## Method (no column eyeballing)

1. Load generated `CLIENT_EXAM_FORM` + `FORM_KEYS` (TypeScript object literals parsed as JSON).
2. Load official `json/act-practice-test-2.json`.
3. Open `preact/ACT-Test-Prep-ACT-Practice-Test-2-Form.pdf` with **PyMuPDF** via `.venv/bin/python`.
4. Integrity: on-disk PDF SHA-256 `2819aa723f2d205d71f6e897a8fbcce54e3b3975b1598d867a1ea432d052c63d` equals JSON `source.sha256`.
5. Scoring-key oracle: `extract_forms.locate_sections` → first key page = 50 (page after the last test section). `extract_forms.parse_keys(..., key_style="table")` linearizes each key page and regex-parses rows `N LETTER CATEGORY` after the `Reporting Categories` heading — **not** a visual read of columns. English scoring key is on **PDF page 63** of the 70-page booklet. Yields 50 booklet letters, `scored` flags, `raw_max=40`, and the conversion table.
6. Image rule: `needsImage` is true iff `text_fidelity` is `math-notation` or `low`, or the item sits on a figure passage. English is never a figure passage in the converter (`isFigurePassage` is Science-only unless `is_figure` is set). Expected images = 0.
7. Scripted grade: Python port of `scoreExamSection` + exact-letter `Grader`. Chosen letter = generated `answer_letter` (A–D; even items mapped F/G/H/J → A/B/C/D). Unscored exclusion proven with a second script that marks field-test items wrong and a third that marks only field-test items correct.
8. PDF text fidelity: for each item, `page.get_text` on the JSON `bbox` (fallback: full page); assert JSON stem and each choice text are contained after whitespace normalization. No human transcription.

Interpreter: worktree `.venv/bin/python` (PyMuPDF 1.28.0).

---

## Section-level checks

| item | check | expected [PDF/JSON] | actual | verdict |
|---|---|---|---|---|
| section | question_count | 50 | 50 | **PASS** |
| section | scored_count | 40 | 40 | **PASS** |
| section | field_test_count | 10 | 10 | **PASS** |
| section | choice_count | 4 | 4 | **PASS** |
| section | question_images | 0 — text-first: English ok → image=null | 0 | **PASS** |
| section | passage_images | 0 — English passages are not figure passages | 0 | **PASS** |
| section | delivery | asset-served | asset-served | **PASS** |
| section | composite_sections | `english, math, reading` | `english, math, reading` | **PASS** |
| section | english_composite_flag | True | True | **PASS** |
| section | client_no_answer_fields | `[]` | `[]` | **PASS** |
| section | pdf_sha256_vs_json | 2819aa723f2d205d71f6e897a8fbcce54e3b3975b1598d867a1ea432d052c63d | 2819aa723f2d205d71f6e897a8fbcce54e3b3975b1598d867a1ea432d052c63d | **PASS** |
| section | pdf_key_page_count_english | 50 — parse_keys table-style on form PDF pages [63] (first_key_page=50) | 50 | **PASS** |
| section | pdf_raw_max | 40 | 40 | **PASS** |
| section | scale_table | JSON scoring.scale_conversion | client scale_table | **PASS** |
| section | scale_40_to_36 | 36 | 36 | **PASS** |
| section | scale_0_to_1 | 1 | 1 | **PASS** |
| section | passage_count | 6 | 6 | **PASS** |
| section | passages_vs_json | identical label/title/intro/text/qnums | 0 diffs | **PASS** |
| section | scripted_all_correct_key_match | 50/50 correct=true | 50/50 | **PASS** |
| section | scripted_all_correct_raw | 40 | 40 | **PASS** |
| section | scripted_all_correct_scored_total | 40 | 40 | **PASS** |
| section | scripted_all_correct_scale | 36 | 36 | **PASS** |
| section | unscored_excluded_mixed | raw=40 scale=36 (FT wrong) | raw=40 scale=36 | **PASS** |
| section | unscored_excluded_inverse | raw=0 scale=1 (FT correct, scored wrong) | raw=0 scale=1 | **PASS** |
| section | composite_needs_EMR | null until math+reading finished — V-E does not sit Math/Reading; wiring verified via composite_sections | english-only → composite null (FR-P2-17 / FR-8) | **PASS** |

---

## Per-item discrepancy table

One row per English item (`question_count` = 50). `check` is the full §6.4 suite for that item (present, scored vs field-test, fidelity, image-null, choice_count=4, stem vs JSON, choices vs JSON + letter map, passage label + `question_numbers`, `context_html` = escaped passage text, key booklet vs JSON, key booklet vs PDF parse_keys, A–D normalization, scored vs PDF, stem+choices on PDF page).

Field-test items (PDF + JSON `Not Scored`): **16, 17, 18, 19, 20, 21, 22, 23, 24, 25**.

Passage map: I = 1–10 · II = 11–15 · III = 16–25 (field-test) · IV = 26–35 · V = 36–45 · VI = 46–50.

| item | check | expected [PDF/JSON] | actual | verdict |
|---|---|---|---|---|
| 1 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage I, booklet key D (PDF p63), stem+choices on booklet p4 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 2 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage I, booklet key H (PDF p63), stem+choices on booklet p4 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 3 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage I, booklet key D (PDF p63), stem+choices on booklet p4 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 4 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage I, booklet key J (PDF p63), stem+choices on booklet p5 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 5 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage I, booklet key D (PDF p63), stem+choices on booklet p5 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 6 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage I, booklet key H (PDF p63), stem+choices on booklet p5 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 7 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage I, booklet key C (PDF p63), stem+choices on booklet p5 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 8 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage I, booklet key H (PDF p63), stem+choices on booklet p5 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 9 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage I, booklet key B (PDF p63), stem+choices on booklet p6 | client+keys match; answer_letter=B; image=null; choice_n=4 | **PASS** |
| 10 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage I, booklet key F (PDF p63), stem+choices on booklet p6 | client+keys match; answer_letter=A; image=null; choice_n=4 | **PASS** |
| 11 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage II, booklet key A (PDF p63), stem+choices on booklet p6 | client+keys match; answer_letter=A; image=null; choice_n=4 | **PASS** |
| 12 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage II, booklet key G (PDF p63), stem+choices on booklet p6 | client+keys match; answer_letter=B; image=null; choice_n=4 | **PASS** |
| 13 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage II, booklet key C (PDF p63), stem+choices on booklet p6 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 14 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage II, booklet key H (PDF p63), stem+choices on booklet p7 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 15 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage II, booklet key B (PDF p63), stem+choices on booklet p7 | client+keys match; answer_letter=B; image=null; choice_n=4 | **PASS** |
| 16 | all §6.4 English checks | JSON+PDF: field-test, fidelity=ok, image=null, 4 choices, passage III, booklet key H (PDF p63), stem+choices on booklet p7 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 17 | all §6.4 English checks | JSON+PDF: field-test, fidelity=ok, image=null, 4 choices, passage III, booklet key B (PDF p63), stem+choices on booklet p8 | client+keys match; answer_letter=B; image=null; choice_n=4 | **PASS** |
| 18 | all §6.4 English checks | JSON+PDF: field-test, fidelity=ok, image=null, 4 choices, passage III, booklet key J (PDF p63), stem+choices on booklet p8 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 19 | all §6.4 English checks | JSON+PDF: field-test, fidelity=ok, image=null, 4 choices, passage III, booklet key D (PDF p63), stem+choices on booklet p8 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 20 | all §6.4 English checks | JSON+PDF: field-test, fidelity=ok, image=null, 4 choices, passage III, booklet key F (PDF p63), stem+choices on booklet p8 | client+keys match; answer_letter=A; image=null; choice_n=4 | **PASS** |
| 21 | all §6.4 English checks | JSON+PDF: field-test, fidelity=ok, image=null, 4 choices, passage III, booklet key C (PDF p63), stem+choices on booklet p8 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 22 | all §6.4 English checks | JSON+PDF: field-test, fidelity=ok, image=null, 4 choices, passage III, booklet key G (PDF p63), stem+choices on booklet p9 | client+keys match; answer_letter=B; image=null; choice_n=4 | **PASS** |
| 23 | all §6.4 English checks | JSON+PDF: field-test, fidelity=ok, image=null, 4 choices, passage III, booklet key B (PDF p63), stem+choices on booklet p9 | client+keys match; answer_letter=B; image=null; choice_n=4 | **PASS** |
| 24 | all §6.4 English checks | JSON+PDF: field-test, fidelity=ok, image=null, 4 choices, passage III, booklet key G (PDF p63), stem+choices on booklet p9 | client+keys match; answer_letter=B; image=null; choice_n=4 | **PASS** |
| 25 | all §6.4 English checks | JSON+PDF: field-test, fidelity=ok, image=null, 4 choices, passage III, booklet key A (PDF p63), stem+choices on booklet p9 | client+keys match; answer_letter=A; image=null; choice_n=4 | **PASS** |
| 26 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage IV, booklet key J (PDF p63), stem+choices on booklet p10 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 27 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage IV, booklet key B (PDF p63), stem+choices on booklet p10 | client+keys match; answer_letter=B; image=null; choice_n=4 | **PASS** |
| 28 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage IV, booklet key J (PDF p63), stem+choices on booklet p10 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 29 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage IV, booklet key C (PDF p63), stem+choices on booklet p10 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 30 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage IV, booklet key F (PDF p63), stem+choices on booklet p11 | client+keys match; answer_letter=A; image=null; choice_n=4 | **PASS** |
| 31 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage IV, booklet key D (PDF p63), stem+choices on booklet p11 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 32 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage IV, booklet key H (PDF p63), stem+choices on booklet p11 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 33 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage IV, booklet key D (PDF p63), stem+choices on booklet p11 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 34 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage IV, booklet key F (PDF p63), stem+choices on booklet p11 | client+keys match; answer_letter=A; image=null; choice_n=4 | **PASS** |
| 35 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage IV, booklet key C (PDF p63), stem+choices on booklet p11 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 36 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage V, booklet key F (PDF p63), stem+choices on booklet p12 | client+keys match; answer_letter=A; image=null; choice_n=4 | **PASS** |
| 37 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage V, booklet key C (PDF p63), stem+choices on booklet p12 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 38 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage V, booklet key J (PDF p63), stem+choices on booklet p12 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 39 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage V, booklet key D (PDF p63), stem+choices on booklet p12 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 40 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage V, booklet key J (PDF p63), stem+choices on booklet p13 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 41 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage V, booklet key B (PDF p63), stem+choices on booklet p13 | client+keys match; answer_letter=B; image=null; choice_n=4 | **PASS** |
| 42 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage V, booklet key F (PDF p63), stem+choices on booklet p13 | client+keys match; answer_letter=A; image=null; choice_n=4 | **PASS** |
| 43 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage V, booklet key A (PDF p63), stem+choices on booklet p13 | client+keys match; answer_letter=A; image=null; choice_n=4 | **PASS** |
| 44 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage V, booklet key J (PDF p63), stem+choices on booklet p13 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 45 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage V, booklet key B (PDF p63), stem+choices on booklet p14 | client+keys match; answer_letter=B; image=null; choice_n=4 | **PASS** |
| 46 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage VI, booklet key J (PDF p63), stem+choices on booklet p14 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 47 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage VI, booklet key C (PDF p63), stem+choices on booklet p14 | client+keys match; answer_letter=C; image=null; choice_n=4 | **PASS** |
| 48 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage VI, booklet key J (PDF p63), stem+choices on booklet p15 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |
| 49 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage VI, booklet key A (PDF p63), stem+choices on booklet p15 | client+keys match; answer_letter=A; image=null; choice_n=4 | **PASS** |
| 50 | all §6.4 English checks | JSON+PDF: scored, fidelity=ok, image=null, 4 choices, passage VI, booklet key J (PDF p63), stem+choices on booklet p15 | client+keys match; answer_letter=D; image=null; choice_n=4 | **PASS** |

---

## Scripted server-grade

`gradeAssetServedSection` equivalent: inject `FORM_KEYS.answer_letter`, run `scoreExamSection` rules (unscored skipped for raw/scale).

| Script | raw_correct | raw_scored_total | scale_score | key `correct` match |
|---|---|---|---|---|
| All 50 chosen = official key | 40 | 40 | 36 | 50/50 |
| Scored all correct, field-test all wrong | 40 | 40 | 36 | scored 40/40; FT excluded |
| Scored all wrong, field-test all correct | 0 | 40 | 1 | FT excluded (raw stays 0) |

Composite (FR-P2-17): form declares `composite_sections = [english, math, reading]`; English `composite=true`; Science is not in the mean. A finished English-only run leaves composite **null** until Math and Reading are also finished (phase-1 FR-8). End-to-end composite arithmetic is V-T / V-M / V-R, not this lane.

---

## Spec FR coverage exercised (English)

| FR | What was checked |
|---|---|
| FR-P2-1 | PDF SHA-256 matches JSON `source.sha256`; declared 50 = actual 50; all scored items have keys |
| FR-P2-2 / FR-P2-10 | Client stems + choices are the JSON text; English images absent |
| FR-P2-3 | Client artifact contains none of `answer_letter` / rationale fields |
| FR-P2-11 / §4.1 | Image-necessary rule → 0 English `AssetRef`s |
| FR-P2-12 (English analog) | Six passages I–VI; each item's passage label matches `question_numbers` (English uses `context_html`, not the Reading/Science passage block) |
| FR-P2-17 | `scale_table` == JSON conversion; 40→36, 0→1; composite set is E+M+R |
| FR-P2-18 | Items 16–25 answerable + keyed but excluded from raw/scale |

---

## Mismatch counts

| Check family | Failures |
|---|---|
| Counts / choice_count / images | 0 |
| Stem / choices vs JSON | 0 |
| Stem / choices vs PDF page text | 0 |
| Passages / `question_numbers` / context | 0 |
| Keys vs JSON | 0 |
| Keys vs PDF scoring-key page (parse_keys) | 0 |
| Scripted grade `correct` | 0 |
| Unscored exclusion / scale | 0 |
| **Total** | **0** |

---

## Blockers

None. V-E is green. No sdd-converge fix tasks from this lane.

Out of scope for V-E (owned by sibling lanes / V-T): Math/Reading/Science fidelity, a human sitting the full PT2 run, live browser render of every English item (this pass compared generated client+keys to JSON/PDF, which is what the renderer consumes).
