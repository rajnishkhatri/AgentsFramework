# V-S — PT2 Science discrepancy report

**Task:** Phase 3 VALIDATE V-S (`docs/plan/exam-module-official-forms.tasks.md`)
**Plan oracle:** §6.4 per-section fidelity table
**Form:** `act-practice-test-2` (Enhanced ACT) · section **science**
**Base:** `.worktrees/exam-official-forms` on `feat/exam-official-forms` @ `8269a1b32ab06bb3bdfe1aeafdef4b01c251ad74`
**Artifacts:** gitignored `frontend/lib/adapters/engine/exam_forms/_generated/act-practice-test-2.{client,keys}.ts`
**Source:** `docs/preact9secure/` (main checkout; ©ACT — not committed)
**Date:** 2026-09-03
**Verdict vs V-S criteria: PASS**

This file is report-only. No exam code or `_generated/` content was edited. Findings (none blocking) would route to sdd-converge, never to hand-edits of generated artifacts.

©ACT stem, choice, and passage text is **not** reproduced here. Comparisons used exact string equality; the table records letters, counts, fidelity, image-use, and PASS/FAIL only.

---

## V-S pass/fail criteria

| Criterion | Result |
|---|---|
| Report exists at `docs/plan/exam-official-forms-validation/science.md` | yes |
| Every item covered (rows = `question_count` = 40) | **40/40** items 1–40 |
| Key match 100% for the scripted answer set | **40/40** `correct=true`; booklet letter = PDF scoring-key page = JSON `answer` |
| Stem/choices (`ok` items) match source | **40/40** exact vs JSON (incl. 4 `math-notation`); after hyphen-join, stem tokens + 4 choice texts found on each item's PDF page |
| Image used iff image-necessary rule | **34** question images (4 lossy + 30 ok-on-figure); **6** text-only (Passage II); **6** passage page-renders |
| Passage block matches `question_numbers` | **7/7** passages I–VII; every item's label is in the owning passage's `question_numbers` |
| Unscored excluded from raw/scale; Science not in composite | field-test **6–11** excluded; scale 34→36 / 0→1; `composite_sections = english, math, reading` |
| Mismatch count | **0** |
| Blockers | **none** |

---

## Method (no column eyeballing)

1. Load generated `CLIENT_EXAM_FORM` + `FORM_KEYS` (TypeScript object literals parsed as JSON).
2. Load official `json/act-practice-test-2.json`.
3. Open `preact/ACT-Test-Prep-ACT-Practice-Test-2-Form.pdf` with **PyMuPDF** via `.venv/bin/python`.
4. Integrity: on-disk PDF SHA-256 `2819aa723f2d205d71f6e897a8fbcce54e3b3975b1598d867a1ea432d052c63d` equals JSON `source.sha256`.
5. Scoring-key oracle: `extract_forms.locate_sections` → first key page = 50 (page after Science END OF TEST, booklet pp. 36–49). `extract_forms.parse_keys(..., key_style="table")` linearizes each key page and regex-parses rows `N LETTER CATEGORY` after the `Reporting Categories` heading — **not** a visual read of columns. Science scoring key + conversion table is on **PDF page 66** of the 70-page booklet. Yields 40 booklet letters, `scored` flags, `raw_max=34`, category totals IOD=13 / SIN=10 / EMI=11, and the conversion table.
6. Image rule (same as `exam_image_rule.needsImage` + converter `isFigurePassage`): image iff `text_fidelity` ∈ {`math-notation`,`low`} **or** the item sits on a Science passage whose intro/text matches `\bfigures?\b|\btables?\b`. Expected lossy = **4**; expected figure passages = **6** (I, III–VII); Passage II is text-only (no figure/table token).
7. Scripted grade: Python port of `scoreExamSection` + exact-letter `Grader`. Chosen letter = generated `answer_letter` (A–D; even items mapped F/G/H/J → A/B/C/D). Unscored exclusion proven with an inverse script (field-test correct, scored wrong → raw 0 / scale 1).
8. PDF text fidelity: `page.get_text` on the item's booklet page; hyphenated line-breaks joined (`neu-` + `tral` → `neutral`) then whitespace-normalized; assert stem tokens and each choice text are contained. Image bytes checked on disk at `docs/preact9secure/json/<AssetRef.key>`.

Interpreter: worktree `.venv/bin/python` (PyMuPDF 1.28.0).

---

## Section-level checks

| item | check | expected [PDF/JSON] | actual | verdict |
|---|---|---|---|---|
| section | question_count | 40 | 40 | **PASS** |
| section | scored_count | 34 | 34 | **PASS** |
| section | field_test_count | 6 | 6 (items 6–11) | **PASS** |
| section | choice_count | 4 | 4 | **PASS** |
| section | minutes | 40 | 40 | **PASS** |
| section | lossy_items | ~4 (`math-notation`/`low`) | 4 — Q1, Q38, Q39, Q40 all `math-notation` | **PASS** |
| section | figure_passages | ~6 Science figure/table passages | 6 — I, III, IV, V, VI, VII (Passage II text-only) | **PASS** |
| section | question_images | image iff rule (lossy ∪ figure-passage items) | 34 `AssetRef`s; Q6–11 `image=null` | **PASS** |
| section | passage_images | page-render on figure passages | 6 page PNGs (I, III–VII); II has none | **PASS** |
| section | image_assets_on_disk | every referenced key exists under `json/` | 34 question + 6 page PNGs present | **PASS** |
| section | delivery | asset-served | asset-served | **PASS** |
| section | composite_sections | `english, math, reading` (Science out) | `english, math, reading` | **PASS** |
| section | science_composite_flag | False | False | **PASS** |
| section | client_no_answer_fields | no `answer_letter` / rationale keys | none (directions may say “answer”) | **PASS** |
| section | pdf_sha256_vs_json | 2819aa723f2d205d71f6e897a8fbcce54e3b3975b1598d867a1ea432d052c63d | 2819aa723f2d205d71f6e897a8fbcce54e3b3975b1598d867a1ea432d052c63d | **PASS** |
| section | pdf_section_pages | SCIENCE TEST 40 Minutes—40 Questions | booklet pp. 36–49 | **PASS** |
| section | pdf_key_page_count_science | 40 — parse_keys table-style on form PDF page 66 | 40 | **PASS** |
| section | pdf_raw_max | 34 | 34 | **PASS** |
| section | category_totals | IOD=13 SIN=10 EMI=11 | IOD=13 SIN=10 EMI=11 | **PASS** |
| section | scale_table | JSON `scoring.scale_conversion` = PDF Conversion Table | 35 rows 0–34; client == JSON == PDF | **PASS** |
| section | scale_34_to_36 | 36 | 36 | **PASS** |
| section | scale_0_to_1 | 1 | 1 | **PASS** |
| section | passage_count | 7 | 7 | **PASS** |
| section | passages_vs_json | identical label/title/intro/text/qnums | 0 diffs | **PASS** |
| section | scripted_all_correct_key_match | 40/40 correct=true | 40/40 | **PASS** |
| section | scripted_all_correct_raw | 34 | 34 | **PASS** |
| section | scripted_all_correct_scored_total | 34 | 34 | **PASS** |
| section | scripted_all_correct_scale | 36 | 36 | **PASS** |
| section | unscored_excluded_inverse | raw=0 scale=1 (FT correct, scored wrong) | raw=0 scale=1 | **PASS** |
| section | composite_ignores_science | mean(E,M,R) only | Science `composite=false`; not in `composite_sections` | **PASS** |

---

## Per-item discrepancy table

One row per Science item (`question_count` = 40). `check` is the full §6.4 suite for that item (present, scored vs field-test, fidelity, image iff rule, choice_count=4, stem vs JSON, choices vs JSON + letter map, passage label + `question_numbers`, passage figure image when heuristic says so, key booklet vs JSON, key booklet vs PDF parse_keys, A–D normalization, scored vs PDF, stem+choices on PDF page after hyphen-join, asset on disk).

Field-test items (PDF + JSON `Not Scored`): **6, 7, 8, 9, 10, 11** (all Passage II).

Passage map: I = 1–5 (figure) · II = 6–11 (text-only, field-test) · III = 12–17 (figure) · IV = 18–23 (figure) · V = 24–29 (figure) · VI = 30–35 (figure) · VII = 36–40 (figure).

Lossy (`math-notation`): **1, 38, 39, 40**.

| item | check | expected [PDF/JSON] | actual | verdict |
|---|---|---|---|---|
| 1 | all §6.4 Science checks | JSON+PDF: scored, fidelity=math-notation, image=yes (lossy+fig I), 4 choices, booklet key D (PDF p66), stem+choices on booklet p36 | client+keys match; answer_letter=D; image+passage PNG on disk | **PASS** |
| 2 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig I), 4 choices, booklet key F (PDF p66), stem+choices on booklet p36 | client+keys match; answer_letter=A; image+passage PNG on disk | **PASS** |
| 3 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig I), 4 choices, booklet key B (PDF p66), stem+choices on booklet p37 | client+keys match; answer_letter=B; image+passage PNG on disk | **PASS** |
| 4 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig I), 4 choices, booklet key F (PDF p66), stem+choices on booklet p37 | client+keys match; answer_letter=A; image+passage PNG on disk | **PASS** |
| 5 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig I), 4 choices, booklet key C (PDF p66), stem+choices on booklet p37 | client+keys match; answer_letter=C; image+passage PNG on disk | **PASS** |
| 6 | all §6.4 Science checks | JSON+PDF: field-test, fidelity=ok, image=null (pass II text-only), 4 choices, booklet key G (PDF p66), stem+choices on booklet p38 | client+keys match; answer_letter=B; image=null | **PASS** |
| 7 | all §6.4 Science checks | JSON+PDF: field-test, fidelity=ok, image=null (pass II), 4 choices, booklet key B (PDF p66), stem+choices on booklet p39 | client+keys match; answer_letter=B; image=null | **PASS** |
| 8 | all §6.4 Science checks | JSON+PDF: field-test, fidelity=ok, image=null (pass II), 4 choices, booklet key H (PDF p66), stem+choices on booklet p39 | client+keys match; answer_letter=C; image=null | **PASS** |
| 9 | all §6.4 Science checks | JSON+PDF: field-test, fidelity=ok, image=null (pass II), 4 choices, booklet key C (PDF p66), stem+choices on booklet p39 | client+keys match; answer_letter=C; image=null | **PASS** |
| 10 | all §6.4 Science checks | JSON+PDF: field-test, fidelity=ok, image=null (pass II), 4 choices, booklet key F (PDF p66), stem+choices on booklet p39 | client+keys match; answer_letter=A; image=null | **PASS** |
| 11 | all §6.4 Science checks | JSON+PDF: field-test, fidelity=ok, image=null (pass II), 4 choices, booklet key C (PDF p66), stem+choices on booklet p39 | client+keys match; answer_letter=C; image=null | **PASS** |
| 12 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig III), 4 choices, booklet key F (PDF p66), stem+choices on booklet p41 | client+keys match; answer_letter=A; image+passage PNG on disk | **PASS** |
| 13 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig III), 4 choices, booklet key A (PDF p66), stem+choices on booklet p41 | client+keys match; answer_letter=A; image+passage PNG on disk | **PASS** |
| 14 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig III), 4 choices, booklet key H (PDF p66), stem+choices on booklet p41 | client+keys match; answer_letter=C; image+passage PNG on disk | **PASS** |
| 15 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig III), 4 choices, booklet key C (PDF p66), stem+choices on booklet p41 | client+keys match; answer_letter=C; image+passage PNG on disk | **PASS** |
| 16 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig III), 4 choices, booklet key J (PDF p66), stem+choices on booklet p41 | client+keys match; answer_letter=D; image+passage PNG on disk | **PASS** |
| 17 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig III), 4 choices, booklet key D (PDF p66), stem+choices on booklet p41 | client+keys match; answer_letter=D; image+passage PNG on disk | **PASS** |
| 18 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig IV), 4 choices, booklet key H (PDF p66), stem+choices on booklet p43 | client+keys match; answer_letter=C; image+passage PNG on disk | **PASS** |
| 19 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig IV), 4 choices, booklet key D (PDF p66), stem+choices on booklet p43 | client+keys match; answer_letter=D; image+passage PNG on disk | **PASS** |
| 20 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig IV), 4 choices, booklet key G (PDF p66), stem+choices on booklet p43 | client+keys match; answer_letter=B; image+passage PNG on disk | **PASS** |
| 21 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig IV), 4 choices, booklet key B (PDF p66), stem+choices on booklet p43 | client+keys match; answer_letter=B; image+passage PNG on disk | **PASS** |
| 22 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig IV), 4 choices, booklet key G (PDF p66), stem+choices on booklet p43 | client+keys match; answer_letter=B; image+passage PNG on disk | **PASS** |
| 23 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig IV), 4 choices, booklet key A (PDF p66), stem+choices on booklet p43 | client+keys match; answer_letter=A; image+passage PNG on disk | **PASS** |
| 24 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig V), 4 choices, booklet key H (PDF p66), stem+choices on booklet p44 | client+keys match; answer_letter=C; image+passage PNG on disk | **PASS** |
| 25 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig V), 4 choices, booklet key D (PDF p66), stem+choices on booklet p44 | client+keys match; answer_letter=D; image+passage PNG on disk | **PASS** |
| 26 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig V), 4 choices, booklet key G (PDF p66), stem+choices on booklet p45 | client+keys match; answer_letter=B; image+passage PNG on disk | **PASS** |
| 27 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig V), 4 choices, booklet key D (PDF p66), stem+choices on booklet p45 | client+keys match; answer_letter=D; image+passage PNG on disk | **PASS** |
| 28 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig V), 4 choices, booklet key F (PDF p66), stem+choices on booklet p45 | client+keys match; answer_letter=A; image+passage PNG on disk | **PASS** |
| 29 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig V), 4 choices, booklet key D (PDF p66), stem+choices on booklet p45 | client+keys match; answer_letter=D; image+passage PNG on disk | **PASS** |
| 30 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig VI), 4 choices, booklet key G (PDF p66), stem+choices on booklet p47 | client+keys match; answer_letter=B; image+passage PNG on disk | **PASS** |
| 31 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig VI), 4 choices, booklet key C (PDF p66), stem+choices on booklet p47 | client+keys match; answer_letter=C; image+passage PNG on disk | **PASS** |
| 32 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig VI), 4 choices, booklet key H (PDF p66), stem+choices on booklet p47 | client+keys match; answer_letter=C; image+passage PNG on disk | **PASS** |
| 33 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig VI), 4 choices, booklet key A (PDF p66), stem+choices on booklet p47 | client+keys match; answer_letter=A; image+passage PNG on disk | **PASS** |
| 34 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig VI), 4 choices, booklet key G (PDF p66), stem+choices on booklet p47 | client+keys match; answer_letter=B; image+passage PNG on disk | **PASS** |
| 35 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig VI), 4 choices, booklet key D (PDF p66), stem+choices on booklet p47 | client+keys match; answer_letter=D; image+passage PNG on disk | **PASS** |
| 36 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig VII), 4 choices, booklet key F (PDF p66), stem+choices on booklet p48 | client+keys match; answer_letter=A; image+passage PNG on disk | **PASS** |
| 37 | all §6.4 Science checks | JSON+PDF: scored, fidelity=ok, image=yes (fig VII), 4 choices, booklet key B (PDF p66), stem+choices on booklet p49 | client+keys match; answer_letter=B; image+passage PNG on disk | **PASS** |
| 38 | all §6.4 Science checks | JSON+PDF: scored, fidelity=math-notation, image=yes (lossy+fig VII), 4 choices, booklet key F (PDF p66), stem+choices on booklet p49 | client+keys match; answer_letter=A; image+passage PNG on disk | **PASS** |
| 39 | all §6.4 Science checks | JSON+PDF: scored, fidelity=math-notation, image=yes (lossy+fig VII), 4 choices, booklet key D (PDF p66), stem+choices on booklet p49 | client+keys match; answer_letter=D; image+passage PNG on disk | **PASS** |
| 40 | all §6.4 Science checks | JSON+PDF: scored, fidelity=math-notation, image=yes (lossy+fig VII), 4 choices, booklet key F (PDF p66), stem+choices on booklet p49 | client+keys match; answer_letter=A; image+passage PNG on disk | **PASS** |

---

## Scripted server-grade

`gradeAssetServedSection` equivalent: inject `FORM_KEYS.answer_letter`, run `scoreExamSection` rules (unscored skipped for raw/scale).

| Script | raw_correct | raw_scored_total | scale_score | key `correct` match |
|---|---|---|---|---|
| All 40 chosen = official key | 34 | 34 | 36 | 40/40 |
| Scored all correct, field-test all wrong | 34 | 34 | 36 | scored 34/34; FT excluded |
| Scored all wrong, field-test all correct | 0 | 34 | 1 | FT excluded (raw stays 0) |
| All chosen = A | 10 | 34 | 14 | 11/40 items have answer_letter A (10 scored + 1 FT) |

Composite (FR-P2-17): form declares `composite_sections = [english, math, reading]`; Science `composite=false` and is **not** in the mean. A finished Science-only run cannot produce a composite. End-to-end composite arithmetic is V-T / V-E / V-M / V-R, not this lane.

---

## Spec FR coverage exercised (Science)

| FR | What was checked |
|---|---|
| FR-P2-1 | PDF SHA-256 matches JSON `source.sha256`; declared 40 = actual 40; all scored items have keys |
| FR-P2-2 / FR-P2-10 | Client stems + choices are the JSON text; `ok` Science items keep that text (Passage II is text-only) |
| FR-P2-3 | Client artifact contains none of `answer_letter` / rationale fields |
| FR-P2-11 / §4.1 | Image-necessary rule → 34 Science question `AssetRef`s (4 lossy + figure-passage items) + 6 passage page-renders |
| FR-P2-12 | Seven passages I–VII; figure `<img>` on I, III–VII; each item's passage label matches `question_numbers` |
| FR-P2-17 | `scale_table` == JSON == PDF conversion; 34→36, 0→1; composite set is E+M+R (Science separate) |
| FR-P2-18 | Items 6–11 answerable + keyed but excluded from raw/scale |

---

## Mismatch counts

| Check family | Failures |
|---|---|
| Counts / choice_count / scale | 0 |
| Stem / choices vs JSON | 0 |
| Stem / choices vs PDF page text (hyphen-joined) | 0 |
| Passages / `question_numbers` / figure heuristic | 0 |
| Image rule (used iff necessary) | 0 |
| Image / page assets missing | 0 |
| Keys vs JSON | 0 |
| Keys vs PDF scoring-key page (parse_keys p66) | 0 |
| Scripted grade `correct` | 0 |
| Unscored exclusion / scale / composite wiring | 0 |
| **Total** | **0** |

---

## Notes (not mismatches)

- Spec §2 estimated “Science ~10 items sit on data/figure passages.” The converter heuristic (`figures?`/`tables?` in intro+text) marks **6 of 7** passages as figure, so **34/40** items get a question image. That matches the written image-necessary rule and the handover inventory (“~4 lossy + ~6 figure passages”), not a converter defect. FR-P2-10’s “most Science” as text is the weaker wording; §4.1 + `needsImage` win. No fix task unless product wants fewer question-level crops (passage page-render only).
- Q20 PDF text hyphenates a stem word across a line break; after join it matches JSON. Not a fidelity fail.

---

## Blockers

None. V-S is green. No sdd-converge fix tasks from this lane.

Out of scope for V-S (owned by sibling lanes / V-T): English/Math/Reading fidelity, a human sitting the full PT2 run, live browser render of every Science item (this pass compared generated client+keys+assets to JSON/PDF, which is what the renderer consumes).
