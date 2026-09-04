# Tasks — Exam module phase 2 (real official forms: asset-served, server-graded, all four sections)

> **Status:** ✅ Approved 2026-09-03 (spec gate ✓ · plan gate "ok" ✓ · tasks gate "approving" ✓).
> **sdd-implement NOT started** by explicit instruction — handed over via
> [exam-module-official-forms.handover.md](exam-module-official-forms.handover.md) for a new
> session, which creates `feat/exam-official-forms` (off `main`) + the WT-A/WT-B/WT-C
> worktrees per plan §6 and executes the lanes.
>
> SDD Stage 3 · derived from [spec](exam-module-official-forms.spec.md) FR-P2-1…19 +
> [plan §6](exam-module-official-forms.plan.md) parallel-worktree strategy.
> **Base branch:** `feat/exam-official-forms` off `main` (created at implement time).
> **Legend:** lane ∈ {BASE, WT-A, WT-B, WT-C, SERIAL, VALIDATE}; `∥` = runs concurrently with
> the sibling lanes; **RED-FIRST** = author the failing test before impl (watch it fail).
> Every task's pass/fail is a named test mapped to an EARS FR. Paths verified by the
> 2026-09-03 grounding pass (21 OK) unless marked *(new)*. All lanes + CI test against the
> **synthetic fixture** (B0-6) — the real ©ACT JSON is a **local-only** test tier.

## Phase 0 · BASE — land FIRST on `feat/exam-official-forms` (base stays releasable)

| ID | Task (files) | Deps | Pass/fail (test → FR) |
|---|---|---|---|
| **B0-1** | `lib/wire/exam_entities.ts` — +`AssetRef {store:"form-image", form_id, key}`, `ExamQuestion.image: AssetRef\|null`, `ExamPassage`, `ExamSection.passages: ExamPassage[]` (default `[]`), `ExamForm.delivery: "client-bundled"\|"asset-served"` (default client-bundled); **`ClientExamForm`** = `.strict()` schema **omitting** the 4 answer-bearing fields; zod snapshot updated | — | `exam_entities.test` round-trip + snapshot; **Test-01 still parses unchanged** (back-compat) → **§4.1** |
| **B0-2** | `lib/ports/engine/form_asset_store.ts` *(new, ONE interface — P1)* — `getImage(ref): Promise<Uint8Array\|null>`, `has(ref)`; JSDoc contract: null on missing, never throws for unknown key | B0-1 | `tsc`; registered in `test_port_conformance` → **FR-P2-14** (contract) |
| **B0-3** | `lib/adapters/engine/exam_forms/exam_image_rule.ts` *(new, pure)* — `needsImage(q, passage)` = `text_fidelity ∈ {math-notation, low} \|\| passage?.is_figure` | — | `exam_image_rule.test` table: `ok`⇒null; notation/low⇒image; figure passage⇒image; English/Reading `ok`⇒null → **§4.1 rule** (decisions.md) |
| **B0-4** | `components/exam/exam_key_posture.ts` — per-form `examKeyPosture(delivery)`: `"server"` for asset-served, `"client"` for client-bundled (Test-01 exemption retained, ADR-0041) — still a code switch, not env-overridable | B0-1 | `exam_key_posture.test` → **FR-P2-5** (flag) |
| **B0-5** | **RED-FIRST** HARDEN `frontend/tests/architecture/test_exam_no_client_served_keys.test.ts` — **retire** the textual `/\bdb-served\b/` heuristic; assert (1) **resolved module graph**: no client-reachable module (`app/**`, `components/**`, `composition_engine_browser.ts`) imports `exam_forms/_generated/*.keys.ts`; (2) **payload schema**: `ClientExamForm` is `.strict()` and lacks `answer_letter`/`per_choice_rationale`/`why_correct_md`/`why_tempted_md`; (3) **planted red fixtures** — a fake client module importing a keys file, and a schema leaking `answer_letter` — both must FAIL | B0-1 | guard green **vacuously** (no asset-served form yet) **and** both red fixtures fail → **FR-P2-8** (explore caveat closed) |
| **B0-6** | `lib/adapters/engine/exam_forms/fixtures/fake_official_form.ts` *(new)* — **synthetic, non-©ACT** 4-section `asset-served` form (2–3 Q/section; one `math-notation` item w/ `image`; one figure passage w/ `image`; one `scored:false` item; a `scale_table`; `composite_sections` E/M/R) **+** `lib/adapters/engine/assets/fake_asset_store.ts` *(new)* in-memory `FormAssetStore` | B0-1/2/3 | fixture passes `assertExamFormLoadable`; fake store round-trips known/unknown keys → **CI substrate for every lane** |
| **B0-7** | `lib/adapters/engine/exam_forms/index.ts` — registry accepts `delivery:"asset-served"` entries whose form comes from a **server-side loader** `loadAssetServedForm(formId) → ExamForm\|null` (null when `_generated/` absent); `listExamForms` **excludes** unloadable asset-served forms; `SUPPORTED_CHOICE_COUNTS` unchanged | B0-1/6 | `exam_forms.test`: asset-served entry registers; absent `_generated` ⇒ **not listed** (spec §6 edge) → **FR-P2-19** prereq |
| **B0-8** | `.gitignore` — `frontend/lib/adapters/engine/exam_forms/_generated/`; confirm `docs/preact9secure/` already ignored | — | `git check-ignore` both paths ⇒ ignored → **FR-P2-4** |

*Freeze after Phase 0:* `exam_entities.ts`, `form_asset_store.ts`, `exam_image_rule.ts`, the fixture,
`exam_key_posture.ts`, the hardened guard — lane changes to them route back to base.

## Phase 1 · WT-A Converter — `feat/exam-wt-converter` (∥ WT-B, WT-C) — owns `frontend/scripts/**` ONLY

| ID | Task (files) | Deps | Pass/fail (test → FR) |
|---|---|---|---|
| **A-1** | **RED-FIRST** `scripts/convert_official_form.test.ts` *(new)* — integrity failures: recorded `source.sha256` ≠ on-disk PDF (when present) / tampered value; `declared_question_count` ≠ actual; a **scored** item with no `answer` ⇒ **throws, emits nothing** | B0-* | three failure cases fail-then-pass → **FR-P2-1** |
| **A-2** | `scripts/convert_official_form.ts` *(new)* — pure `parseOfficialForm(json) → { clientForm: ExamForm, keys: KeyMap }`: 4 sections; **text** stems/choices from JSON; `reporting_category`, `scored`, `passage` label; `passages[]` (label/title/intro/text/`question_numbers`; `image` = page-render ref for figure passages); `image` via `exam_image_rule`; `scale_table` from the conversion tables; `composite_sections` = E/M/R for `act-enhanced` (all four for `preact-secure-legacy`); `delivery:"asset-served"`; booklet letters (F/G/H/J) normalized to A–D with the original preserved | A-1 | on the fixture-shaped input + **local-only tier on real PT2**: counts 50/45/36/40; scored 40/41/27/34; images = **34 Math** + Science lossy/figure, **0** English/Reading; `keys` == the PT2 PDF's official scoring-key page, diffed exactly as done for 805 on 2026-09-03 (**PT2's full key diff is still PENDING — this task closes it**; only its sha256 provenance was verified) → **FR-P2-2, FR-P2-17** |
| **A-3** | emit `_generated/<form_id>.client.ts` (parsed under `ClientExamForm.strict()` — **zero** answer-bearing fields) + `_generated/<form_id>.keys.ts` (server-only); `package.json` script `convert:official` = `tsx scripts/convert_official_form.ts` (script only, **no dep**) | A-2, B0-8 | client artifact strict-parses; `git check-ignore` on both artifacts; keys artifact never in the client graph (B0-5 guard) → **FR-P2-3, FR-P2-4** |

## Phase 1 · WT-B Server path — `feat/exam-wt-server` (∥) — owns `lib/adapters/engine/**` (frozen P0 files excepted) + `app/api/engine/**` + `lib/composition_engine*.ts` ONLY

| ID | Task (files) | Deps | Pass/fail (test → FR) |
|---|---|---|---|
| **B-1** | `lib/adapters/engine/assets/local_file_asset_store.ts` *(new)* — `FormAssetStore` over `node:fs` under constructor `baseDir` (no env read here — C4); path-traversal-safe key resolution; `null` on missing | B0-2 | `local_file_asset_store.test`: reads a temp dir; `../` refused; missing ⇒ null → **FR-P2-14** |
| **B-2** | `EngineDb` +2 — `getExamFormForClient(learnerId, formId)` **"fine"** (registry loader → `ClientExamForm.strict()` parse, so keys cannot leak); `getExamFormKeys(formId)` **"server-only"**; `engine_db_disposition` +2; `in_memory` + `drizzle` + `http` impls (`http` ⇒ 404 for server-only); conformance count **41→43, server-only 5→6** | B0-7 | `http_engine_db.conformance.test` `toHaveLength(43)`; server-only = 6; `HttpEngineDb.getExamFormKeys` ⇒ 404 → **FR-P2-7** |
| **B-3** | **RED-FIRST** dispatcher `app/api/engine/db/[method]/route.ts` — `EXAM_LEARNER_ARG` + `getExamFormForClient` (named learner arg 0); `getExamFormKeys` **absent** from the map + server-only ⇒ **404 at the route**; FR-38 completeness test extended | B-2 | completeness green; client `POST …/getExamFormKeys` ⇒ 404 → **FR-P2-7, FR-38** |
| **B-4** | `lib/adapters/engine/exam_server_grade.ts` *(new)* — `gradeAssetServedSection(form, keys, items, grader)` = pure `scoreExamSection` fed with keys; **server-side** `finishExamSection` path: when the run's form `delivery==="asset-served"` ⇒ ignore client grade fields, grade via `getExamFormKeys`, persist; client-bundled path **unchanged**; route stays thin (F-R4) | B-2 | L2 handler test: finish on an asset-served run returns graded result; client-supplied `correct` ignored; pre-grade payloads contain **no** answer-bearing field; Test-01 finish unchanged → **FR-P2-6, FR-P2-5** |
| **B-5** | `repos/drizzle_exam_run_repo.ts` `finishSection` — asset-served forms **skip local `scoreExamSection`** (no client keys) and call finish with items only; `getForm` resolves asset-served via `getExamFormForClient` | B-4 | repo test vs fixture: asset-served ⇒ no local grade, delegates; client-bundled ⇒ phase-1 behavior → **FR-P2-5** |
| **B-6** | `app/api/engine/asset/[formId]/[key]/route.ts` *(new)* — `requireEngineClaim` → `FormAssetStore.getImage` → stream `image/png`, `Cache-Control: private`; 401 unauth; 404 missing (G1: byte-stream shape ≠ JSON dispatcher, plan §0) | B-1 | route test: unauth ⇒ 401; missing ⇒ 404; ok ⇒ bytes + headers → **FR-P2-15, FR-P2-13** (server side) |
| **B-7** | `lib/composition_engine.ts` — construct `LocalFileAssetStore(baseDir = process.env.EXAM_ASSET_DIR ?? <repo>/docs/preact9secure/json)` (**only** env read, C4/C5); expose on the **server** `EnginePortBag`; browser root gets **no** store | B-1 | `test_engine_port_conformance`; composition test: browser bag lacks store, server bag has it → **FR-P2-14** |
| **B-8** | review reveal — `getExamRun` / review path adds correct-answer + rationale fields **only for finished attempts** (server merges from keys post-grade); in-progress ⇒ stripped | B-4 | L2: in-progress payload has no answer fields; finished payload has them → **FR-P2-9** |

## Phase 1 · WT-C Rendering — `feat/exam-wt-render` (∥) — owns `components/exam/**` ONLY (tests vs B0-6 fixture + `fake_asset_store` + a fake `ExamRunRepo`; **no live server**)

| ID | Task (files) | Deps | Pass/fail (test → FR) |
|---|---|---|---|
| **C-1** | `components/exam/exam_item_vm.ts` *(new, pure)* — `ExamQuestion → ExamItemVM { stem, choices, imageUrl: string\|null, passageLabel }`; `imageUrl` = `/api/engine/asset/<form_id>/<key>` from `AssetRef` (string mapping only, no fetch) — exam-local so the shared `quiz_item_vm` and the isolation guard stay untouched | B0-1 | `exam_item_vm.test` table: `ok` ⇒ text, no image; image-necessary ⇒ url → **FR-P2-10/11** |
| **C-2** | `ExamRunnerView.tsx` — text\|image branch: `imageUrl` ⇒ `<img alt="Question N (official image)">` **in place of** the stem text, choices still A–D `<button>`s; `onError` / missing ⇒ visible **"content unavailable"** placeholder (`role="status"`), never a broken `<img>` | C-1 | RTL: image item renders `<img>` + 4 choice buttons; failed asset ⇒ placeholder text, no broken img → **FR-P2-11, FR-P2-13** |
| **C-3** | `components/exam/ExamPassageBlock.tsx` *(new)* — passage for the current question's `passage` label from `section.passages` (title/intro/text; figure `<img>` when `passage.image`); shared by Reading + Science; layout via `@container` (repo convention) | B0-1 | RTL: correct passage for question N; figure image when present; nothing rendered for Math (no passages) → **FR-P2-12** |
| **C-4** | `exam_review.ts` / `ExamReviewView.tsx` — unscored items carry an **"unscored (field-test)"** badge and are excluded from the score summary; correct answer shown **only when present** (post-grade) | B0-1 | `exam_review.test`: badge; summary excludes unscored; pre-grade item has no correct field → **FR-P2-18, FR-P2-9** (view side) |
| **C-5** | `exam_scoring.test` — PT2-shaped fixture: scale from `scale_table`; composite = mean(E,M,R), Science separate; unscored excluded from raw/scale/composite (scoring code reused; test only) | B0-6 | `exam_scoring.test` new cases → **FR-P2-17, FR-P2-18** |

## Phase 2 · SERIAL on base (after WT-A + WT-B + WT-C merged)

| ID | Task (files) | Deps | Pass/fail (test → FR) |
|---|---|---|---|
| **S-I1** | run `pnpm convert:official -- act-practice-test-2` locally (private folder present) → `_generated/` (ignored); registry entry `{ loader, delivery:"asset-served" }` for `act-practice-test-2` | WT-A✓, B0-7 | server `listExamForms()` includes PT2; `getExamFormForClient` returns 4 sections strict-parsed → **FR-P2-19** |
| **S-I2** | exam home lists PT2 beside Test-01; section page fetches the client form via `HttpEngineDb.getExamFormForClient` (thin page/hook glue, B1 comment) | S-I1, WT-B✓, WT-C✓ | page test: PT2 listed with 4 sections' status → **FR-P2-19** |
| **S-I3** | `e2e/learn/exam.spec.ts` — PT2: start English → answer → submit ⇒ **server-graded** result; a Math image item renders `<img>`; a Science passage block renders; direct `POST getExamFormKeys` ⇒ 404; **Test-01 e2e still green** | S-I2 | chromium smoke → **FR-P2-19, P2-7, P2-11/12** |
| **S-I4** | **hardened guard bites non-vacuously**: with the real asset-served form present `test_exam_no_client_served_keys` green; `examKeyPosture` ⇒ `"server"` for PT2, `"client"` for Test-01 | S-I1 | guard green (real form) → **FR-P2-5, FR-P2-8** |
| **S-F1** | ADR-0042 Proposed→**Accepted** (index/log); ADR-0041 amendment ✓ (done 2026-09-03); `decisions.md` ✓ (image rule + parallel cut, done); `docs/preact9secure/README.md` "Step 2 (not started)" → points at converter + registry | S-I4 | OKF lint 0 failures |

## Phase 3 · VALIDATE — `∥×4` by section (after S-I3 green; read-only, disjoint reports)

| ID | Task (files) | Deps | Pass/fail |
|---|---|---|---|
| **V-E ∥ V-M ∥ V-R ∥ V-S** | per plan §6.4 table — English ∥ Math ∥ Reading ∥ Science: render every item locally; check stem/choices text (`ok` items), image used **iff** rule says so and it is the right PNG, passage block matches `question_numbers`, server-graded `correct` == official key for a scripted answer set, unscored excluded + composite E/M/R; write `docs/plan/exam-official-forms-validation/<section>.md` *(new)* discrepancy table (item · check · expected [PDF/JSON] · actual · verdict). Worktrees or subagents — each writes **only** its own report | S-I3 | report exists; **every** item covered (rows = `question_count`); key match 100 % for the scripted set; findings → **sdd-converge** fix tasks (never hand-edits of `_generated/`) |
| **V-T** | a tester sits a **full PT2 run** locally (all four sections) | V-* | DoD evidence pasted (screens + run read-back) |

## Critical path & parallelism

- **Critical path:** `B0-* → WT-B (B-1→B-2→B-3→B-4→B-5→B-6→B-7→B-8) → S-I1→S-I2→S-I3→S-I4 → max(V-E,V-M,V-R,V-S) → V-T`.
  **WT-A** (offline script) and **WT-C** (pure components vs fixture) run fully **inside** WT-B's
  window and are **off** the critical path — wall-clock floor = BASE + WT-B + SERIAL + one validation pass.
- **Parallel win:** A (3) + C (5) concurrent with B (8) on **disjoint directories**; then four
  validations concurrent (where "by section" is the right axis — plan §6.4).
- **Merge points where the guards bite:** each lane → base re-runs the **hardened**
  `test_exam_no_client_served_keys` + `test_exam_isolation` + conformance **43**; WT-B's merge is
  the first **non-vacuous** guard run (first real asset-served path).

## Stage 4 · Analyze (cross-artifact check + baseline)

- **spec ↔ plan ↔ tasks — FR coverage:** P2-1→A-1 · P2-2→A-2 · P2-3→A-3 · P2-4→B0-8,A-3 ·
  P2-5→B0-4,B-4,B-5,S-I4 · P2-6→B-4 · P2-7→B-2,B-3,S-I3 · P2-8→B0-5,S-I4 · P2-9→B-8,C-4 ·
  P2-10→C-1 · P2-11→C-1,C-2 · P2-12→C-3 · P2-13→C-2,B-6 · P2-14→B0-2,B-1,B-7 · P2-15→B-6 ·
  **P2-16 → design-only, intentionally no build task** (`GcsAssetStore` deferred to Cloud Run
  rollout per spec §2.1 / ADR-0042 follow-on — not zero-coverage by omission) · P2-17→A-2,C-5 ·
  P2-18→C-4,C-5 · P2-19→B0-7,S-I1,S-I2,S-I3. Every task cites a test.
- **Constitution (AGENTS.md):** frontend-only MVP; root invariants #1–#8 untouched; **no new
  `package.json`/`pyproject.toml` runtime dep** (`LocalFileAssetStore` = `node:fs`; `convert:official`
  is a script entry); new abstractions (`FormAssetStore`, `exam_server_grade`, `ExamPassageBlock`,
  `ClientExamForm`) carry ADR-0042 + decisions lines (G1 stated).
- **ADR seam:** ⚠️ Ask-first triggers (new abstraction, new server seam, wire change, source-of-
  truth change) → **ADR-0042** (Proposed; Accepted at S-F1) + ADR-0041 amended → `test_adr_ratchet` satisfied.
- **Grounding:** 21 existing paths verified OK on 2026-09-03; new files marked *(new)*;
  `EXAM_LEARNER_ARG` (route.ts:20,40) and the 41/5 conformance pin (conformance.test.ts:46-47) confirmed.
- **Baseline before implement:** `make check` + `pytest tests/architecture/ -q` + `pnpm vitest run`
  + `pnpm typecheck` green on `feat/exam-official-forms` after Phase 0; private folder present
  locally; `_generated/` ignored **before** the first converter run (B0-8 precedes A-3).

**Route → sdd-implement** (create the base branch + the three worktrees per plan §6; execute
BASE, then A ∥ B ∥ C, then SERIAL, then VALIDATE ∥×4).

---

## Phase 4 — Convergence (iteration 1 · 2026-09-03 · from code-review + VALIDATE)

> **sdd-converge Stage 9.** Append-only. Classification of the gaps left after implement +
> Phase-3 VALIDATE + the deterministic code-review (approve, 0 findings — but the reviewer
> cannot see runtime path bugs; the frontend key-safety/conformance suites I re-ran are green:
> py-arch **254 passed**, targeted vitest **8 files / 118 tests passed**). **Not converged** —
> the image-serve path is a `partial` gap; route to **sdd-implement**. Do **not** hand-edit
> `_generated/` (©ACT). RED-FIRST every task.

### Classification

| Finding | Source | gap-type | Route |
|---|---|---|---|
| Image serve doubles `form_id` (Math 34 + Science) | V-M-B1 ([math.md](exam-official-forms-validation/math.md) §5) | **partial** (FR-P2-11/14) | fix → sdd-implement |
| Slashy asset key doesn't bind the `[key]` route (Math + Science) | V-M-B2 ([math.md](exam-official-forms-validation/math.md) §5) | **partial** (FR-P2-11/15) | fix → sdd-implement |
| Data-path E/R/S, keys, scale, counts, text-first, key-safety, conformance | V-E/V-R/V-S, code-review | — (PASS) | none |
| Reading line-numbers dropped; dual-passage PDF headings not in JSON `text` | V-R observations | **deferred** (product call, not a §6.4 mismatch) | defer — not a fix task |
| Browser sit 500s on `:3010` (WorkOS env absent in worktree) | V-T | **environment** (not a product defect) | none |

### Fix tasks (→ sdd-implement)

| ID | Task (files) | source-ref / gap-type | Pass/fail (RED-FIRST test → FR) |
|---|---|---|---|
| **CV4-1** | Make `AssetRef.key` **store-relative** (strip the leading `<form_id>/` the JSON `image` carries) so `LocalFileAssetStore.resolveKey` (`baseDir/form_id/key`, [local_file_asset_store.ts:47](../../frontend/lib/adapters/engine/assets/local_file_asset_store.ts)) lands on the real PNG. Edit `scripts/convert_official_form.ts` key derivation; **regenerate** `_generated/` locally (gitignored, not committed). | V-M-B1 / **partial** | `convert_official_form.test`: emitted `key` does NOT start with `form_id`; `local_file_asset_store.test`: add the **real PT2 multi-segment** key `questions/math-q02.png` resolving under `baseDir/<form_id>/` (not only `math/q-2.png`) → **FR-P2-14** |
| **CV4-2** | Bind slashy keys end-to-end: `encodeURIComponent(ref.key)` in `assetRefToUrl` ([exam_item_vm.ts:26](../../frontend/components/exam/exam_item_vm.ts)) — the route already `decodeURIComponent`s a single `[key]` segment ([route.ts:33](../../frontend/app/api/engine/asset/[formId]/[key]/route.ts)) — **or** switch the route to catch-all `[formId]/[...key]` + join in the handler. Pick one; do not do both. | V-M-B2 / **partial** | `exam_item_vm.test`: slashy key → single encoded segment; `route.test`: the VM-built URL decodes back to the exact store key and 200s (missing ⇒ 404, unauth ⇒ 401 unchanged) → **FR-P2-11/15** |
| **CV4-3** | Integration re-verify (closes the gap): after CV4-1+CV4-2, prove **Math 34/34 + Science** image items resolve store→route→VM end-to-end; re-run the V-M / V-S **serve** checks and re-sit the substitute (or a real auth'd sit with `EXAM_ASSET_DIR` → main-checkout `docs/preact9secure/json`). Update [math.md](exam-official-forms-validation/math.md) / [tester.md](exam-official-forms-validation/tester.md) verdicts. | V-M rollup + V-T / **partial** | Math image rollup FAIL set → 0; a full-run sit renders official PNGs, no "content unavailable" → **FR-P2-11/13/19** (DoD evidence pasted) |

### Convergence status (Stage 10 — iteration 1 **CLOSED · converged** · verified 2026-09-03)

- [x] **(1) Converged** — CV4-1/2/3 CLOSED and **verified this pass** (not merely claimed): `storeRelativeKey` ([convert_official_form.ts:219,342](../../frontend/scripts/convert_official_form.ts)) + `encodeURIComponent(ref.key)` ([exam_item_vm.ts:26](../../frontend/components/exam/exam_item_vm.ts)) on disk; `_generated/act-practice-test-2.client.ts` regenerated 15:42 → **74 image keys = 68 `questions/` + 6 `pages/` + 0 doubled `act-practice-test-2/questions`**; `math.md`/`tester.md` FAIL→PASS. No `missing`/`partial`/`contradicts` gap remains.
- [x] **(2) gates** — `make check` **5372 passed, 55 skipped**; `pytest tests/architecture/ -q` **254 passed, 3 skipped**; `pnpm typecheck` clean; blast-radius `pnpm vitest run components/exam lib/adapters/engine app/api/engine` **410 passed** + CV4 suites **40 passed** (2026-09-03). (Full `pnpm vitest run` skipped to avoid the nested-worktree ts-morph parallel-timeout *artifact*; scoped runs are authoritative.)
- [x] **(3) ADR** — ADR-0042 **Accepted**; ADR-0041 amended; `test_adr_ratchet` green.
- [ ] **(4) comprehension gates — HUMAN** — G1 (`FormAssetStore`, `exam_server_grade`, `ClientExamForm`) recorded in ADR-0042/decisions; **G9** on the CV4 diff = no new `try/except`/`return None` (`storeRelativeKey` only strips a leading `form_id/`; store/route keep their existing G9 comments). Owner confirms in their own words.
- [x] **(5) eval-capture** — N/A (no LLM seam in this change).
- [x] **(6) blast-radius cleanup** — checked: the fix is minimal (converter `storeRelativeKey`, 1 caller + a 1-line VM encode); no scaffold/dead branch introduced, nothing to delete. `LocalFileAssetStore.resolveKey` was correct all along and is unchanged.

**Bounded loop:** iteration 1 **CLOSED — converged**. Remaining before production: the human answer on (4) + the commit/PR decision (commit only when the human asks; no PR unless asked).

## Phase 5 — Convergence (iteration 2 · 2026-09-03 · from MANUAL validation in a real Next server)

> Manual sit-through (port 3003, `NEXT_PUBLIC_FF_DURABLE_ENGINE=1` + `EXAM_ASSET_DIR`) caught a
> gap the automated suite could not: **PT2 loading was only ever exercised under vitest, never a
> real Next server**, so a server-bundle path bug slipped through green tests.

| ID | Gap | gap-type | Route |
|---|---|---|---|
| **CV5-1** | `generated_official_form.ts` resolved `_generated/` via `import.meta.url`, which does not point at the source dir inside Next's server bundle → registration no-op'd → PT2 excluded → "old questions only". **FIXED** (uncommitted): `resolveGeneratedDir()` = module-relative → `process.cwd()`-relative fallback. | **partial** (P2-19) | test + commit → PR #189 |
| **CV5-2** | No test covers PT2 loading in a **real Next runtime** — vitest resolves `import.meta.url` to source, so it cannot reproduce the bundle-path failure. | **test-gap** | add a resolver unit test (mock `existsSync`/`cwd`) now; a real-server e2e when auth-in-CI is solved (tracks S-I3) |
| Image serve (CV4) end-to-end | `GET …/asset/act-practice-test-2/questions%2Fmath-q02.png` → **official PNG 200**; `getExamFormForClient` 200; keys server-side | — (PASS, manual) | none |
| Full click-through sit (start/navigate/grade) | needs exam tables in a **local/dev** `DATABASE_URL` (`pnpm db:migrate:engine`; server has NO in-memory fallback; 0006 DROPs `exam_run_item` → never vs prod) | **env** (not a code defect) | not a fix task |

**Status:** NOT re-converged — CV5-1 fix is uncommitted and CV5-2 test is unwritten. Route → write the resolver test (red/green) + fold the fix onto PR #189, then re-run converge.
