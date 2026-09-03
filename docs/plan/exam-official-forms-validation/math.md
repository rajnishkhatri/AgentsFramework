# V-M — PT2 Math discrepancy report

> Phase 3 VALIDATE · task **V-M** · plan §6.4 · spec FR-P2-2 / P2-10 / P2-11 / P2-12 / P2-17 / P2-18.
> Phase 4 re-verify (CV4-3, 2026-09-03): image-serve gap closed. Do not hand-edit `_generated/`.

| | |
|---|---|
| **Verdict** | **PASS** |
| **Why** | Data + keys + scale stay clean. CV4-1 emits store-relative keys (`questions/math-qNN.png`); CV4-2 encodes the slashy key as one `[key]` segment. Store→VM re-verify: **34/34** Math image items resolve (FR-P2-11 / FR-P2-13 / FR-P2-14 / FR-P2-15). |
| **Key match (scripted set)** | **100 %** (45/45 PDF scoring-key page == JSON `answer` == generated `booklet_letter`; normalized A–D == generated `answer_letter`) |
| **Item coverage** | **45/45** (`question_count`) |
| **Mismatch counts** | keys **0** · stem/choices (`ok`) **0** · image-rule **0** · PNG-on-disk **0** · passages **0** · scale **0** · counts **0** · **store-resolve 0** |
| **Blockers** | none — V-M-B1 / V-M-B2 closed by CV4-1 / CV4-2 |

## 0. Method (oracles)

Compared generated artifacts in the worktree against the official PT2 JSON + PDF. No browser sit (V-T owns that). `.venv/bin/python` + PyMuPDF (`fitz`) + `docs/preact9secure/tools/extract_forms.parse_keys` — same scoring-key extraction used for Form 805 (table-style; do not eyeball two-column keys).

| Input | Path / pin |
|---|---|
| Worktree | `.worktrees/exam-official-forms` · `feat/exam-official-forms` @ `8269a1b32ab06bb3bdfe1aeafdef4b01c251ad74` |
| Generated | `frontend/lib/adapters/engine/exam_forms/_generated/act-practice-test-2.{client,keys}.ts` (gitignored) |
| Official JSON | `docs/preact9secure/json/act-practice-test-2.json` (main checkout) |
| Official PDF | `docs/preact9secure/preact/ACT-Test-Prep-ACT-Practice-Test-2-Form.pdf` |
| `source.sha256` | `2819aa723f2d205d71f6e897a8fbcce54e3b3975b1598d867a1ea432d052c63d` — **PDF bytes == JSON** |
| Math booklet pages | PDF **16–27** (`MATHEMATICS TEST` · 50 minutes · 45 questions) |
| Scoring-key page | PDF **p64** (`Mathematics Scoring Key` + Conversion Table) — PyMuPDF `parse_keys(..., "table")` |
| Live re-extract | `extract_form(..., out_dir=None)` vs stored JSON — answers and `text_fidelity` identical |
| Image rule | `needsImage` = `text_fidelity ∈ {math-notation, low}` (Math has no figure passages) |
| Scripted grade | all official normalized keys → raw 41/41 · `scale_table[41]=36`; all-wrong → `scale_table[0]=1`; unscored excluded |

©ACT stems/choices/keys are **not** reproduced below. Per-item rows carry verdicts only.

## 1. Section-level checks (plan §6.4)

| Check | Expected [PDF/JSON] | Actual (generated) | Verdict |
|---|---|---|---|
| Every item present | `question_count` = 45; numbers 1–45 | 45 items `act-practice-test-2-math-{1..45}` | PASS |
| Scored / field-test | 41 scored · 4 unscored (FR-P2-18) | 41 / 4 · unscored **8, 18, 28, 38** (PDF “Not Scored”) | PASS |
| `choice_count` | 4 (PT2; `SUPPORTED_CHOICE_COUNTS`) | section `4`; every item A–D (booklet F/G/H/J normalized) | PASS |
| Passages | none (Math) | `passages: []`; every `passage` null | PASS |
| Image iff rule (text-first) | ~34 lossy/`math-notation` | **34** image refs (`math-notation` 32 + `low` 2); **11** `ok` → `image: null` | PASS |
| Official PNG on disk | `json/<form>/questions/math-qNN.png` | 45/45 files exist (nonzero) | PASS |
| Image is the *served* PNG | store resolves the official crop | **34/34** — `questions/math-qNN.png` under `baseDir/form_id/` | PASS |
| Server-graded `correct` == official key | scripted set = PDF p64 | 45/45 booklet+normalized match; raw 41 → scale 36 | PASS |
| Unscored excluded + composite E/M/R | JSON `scored` + `scale_table`; `composite_sections` | unscored omitted from raw; Math `composite: true`; form `["english","math","reading"]` | PASS |
| Scale table | PDF Conversion Table · JSON `scoring.scale_conversion` | 42 rows, identical to PDF and JSON; `0→1` … `41→36` | PASS |
| Client leak | no answer-bearing fields (FR-P2-3) | none of `answer_letter` / rationales on client items | PASS |
| Delivery | `asset-served` | `asset-served` | PASS |

`text_fidelity` (JSON == live PDF extract): `ok` = 11 · `math-notation` = 32 · `low` = 2 (Q6, Q45). Image-necessary = 34. Matches spec “Math **34/45** stems are `math-notation`/`low`”.

`ok` items (text-first, no image): **1, 5, 11, 12, 14, 18, 20, 21, 25, 31, 38**. Stem + choice *text* match stored JSON and the live PDF extract; each choice string appears on that item’s PDF page.

## 2. Scale table (PDF p64 == JSON == generated)

42 raw→scale rows, `raw_max` 41, category totals `PHM=33` / `IES=8` (PDF + JSON). Generated `scale_table` is the same map.

| raw | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8–11 | 12–13 | 14–16 | 17–19 | 20–21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31 | 32 | 33 | 34 | 35 | 36 | 37 | 38 | 39 | 40 | 41 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scale | 1 | 4 | 7 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 25 | 26 | 27 | 27 | 28 | 29 | 30 | 31 | 33 | 34 | 35 | 36 | 36 |

Scripted: all official keys on scored items → `raw_correct=41`, `raw_scored_total=41`, `scale_score=36`. All wrong → scale 1. Answering only the four field-test items correctly still yields raw 0.

## 3. Per-item discrepancy table

One row per item (`rows = question_count`). Columns are the §6.4 checks. `stem/choices` is the JSON+PDF text compare for `ok` items (`n/a` PASS for image-necessary stems — renderer replaces stem with PNG; choice labels still present and match JSON). `store` is whether `LocalFileAssetStore` (`baseDir/form_id/key` with composition default `docs/preact9secure/json`) would find the PNG.

| item | fidelity | render | scored | stem | choices | image iff rule | PNG on disk | store resolve | passage | key vs PDF p64 | scored vs PDF | rollup |
|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ok | text | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 2 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 3 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 4 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 5 | ok | text | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 6 | low | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 7 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 8 | math-notation | image | unscored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 9 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 10 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 11 | ok | text | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 12 | ok | text | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 13 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 14 | ok | text | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 15 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 16 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 17 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 18 | ok | text | unscored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 19 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 20 | ok | text | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 21 | ok | text | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 22 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 23 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 24 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 25 | ok | text | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 26 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 27 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 28 | math-notation | image | unscored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 29 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 30 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 31 | ok | text | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 32 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 33 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 34 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 35 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 36 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 37 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 38 | ok | text | unscored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 39 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 40 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 41 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 42 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 43 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 44 | math-notation | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 45 | low | image | scored | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

Image-necessary rollup FAIL set: **none** (0). Phase-3 FAIL set (34 items) closed by CV4-1 / CV4-2.

## 4. Discrepancy detail (closed)

| item | check | expected [PDF/JSON] | actual | verdict |
|---|---|---|---|---|
| SECTION | `LocalFileAssetStore` resolve | PNG at composition default | 34/34 at `json/<form_id>/questions/math-qNN.png` after store-relative keys | PASS |
| 2–4, 6–10, 13, 15–17, 19, 22–24, 26–30, 32–37, 39–45 | `image_store_resolve` | official crop served | `AssetRef.key` is `questions/math-qNN.png`; store joins `baseDir/form_id/key` | PASS |

Phase-3 root cause (closed): converter copied JSON `image` (`<form_id>/questions/math-qNN.png`) into `AssetRef.key`, so the store looked under `json/<form_id>/<form_id>/questions/…`. CV4-1 strips the leading `form_id/`.

Phase-3 second break (closed): VM built `/api/engine/asset/${form_id}/${key}` without encoding. CV4-2 uses `encodeURIComponent(ref.key)` so `[key]` binds one segment; the route already `decodeURIComponent`s.

Worktree note (environment, not a form mismatch): `docs/preact9secure/` is not in the worktree. Local sit still needs `EXAM_ASSET_DIR` → main checkout `docs/preact9secure/json`.

## 5. Blockers (closed)

| ID | Gap | Class | Status |
|---|---|---|---|
| **V-M-B1** | `AssetRef.key` doubled `form_id/` | `partial` (FR-P2-11/14) | **closed** — CV4-1 store-relative keys |
| **V-M-B2** | Slashy key did not bind `[key]` | `partial` (FR-P2-11/15) | **closed** — CV4-2 `encodeURIComponent` |

No key, count, scale, passage, or `ok`-item text blockers.

## 6. sdd-converge classification

| Finding | gap-type | Route |
|---|---|---|
| Image serve-path (B1+B2) | — (closed) | CV4-1 / CV4-2 landed; re-verify 34/34 |
| Counts 45/41, keys 45/45, scale, passages, text-first 11/34 | — | none |

**V-M is not a data-conversion miss.** The generated Math form is faithful to the official JSON/PDF. Image items are sit-ready on the store→VM path after CV4-1 / CV4-2.
