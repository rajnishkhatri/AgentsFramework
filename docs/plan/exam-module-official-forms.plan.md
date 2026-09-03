# Plan — Exam module phase 2: real official forms (asset-served, server-graded, all four sections)

**Status:** Draft for Stage-2 plan gate — 2026-09-03
**Spec:** [exam-module-official-forms.spec.md](exam-module-official-forms.spec.md) (approved at the spec gate 2026-09-03)
**ADR:** [ADR-0042](../adr/0042-exam-official-forms-asset-served-server-graded.md) (source-of-truth change + `FormAssetStore` + server grading; fires the [ADR-0041](../adr/0041-exam-answer-key-posture.md) tripwire)
**Constitution check:** frontend-only for the MVP; root invariants #1–#8 untouched (no Python, no `trust/`, no graph node, no new runtime dependency). Frontend Ring rules F-R1…F-R9 / A2 / A3 / P1 / B1 / C4 named per lane below. The one Python touch (middleware signed-URL for `GcsAssetStore`) is the **deferred** Cloud Run follow-up, not this plan.

---

## 0. Grounding corrections to the spec (found while planning — explore map 2026-09-03)

- **`db-served` is a dormant literal.** Nothing sets it; the only occurrences are inside the
  guard's own red fixture. The spec's `"asset-served"` delivery **replaces** it; the guard's
  textual `/\bdb-served\b/` predicate is retired by the hardening (FR-P2-8), not extended.
- **Grading runs client-side in one shared class.** `DrizzleExamRunRepo.finishSection`
  ([drizzle_exam_run_repo.ts:129-194](../../frontend/lib/adapters/engine/repos/drizzle_exam_run_repo.ts))
  calls `scoreExamSection` with the client-bundled form, and the class is wired in **both**
  composition roots ([composition_engine.ts:166](../../frontend/lib/composition_engine.ts),
  [composition_engine_browser.ts:159](../../frontend/lib/composition_engine_browser.ts)).
  ⇒ for `asset-served` forms the **client** path must skip local scoring and the **server**
  path must grade; the hook lives server-side (§1).
- **The client must trigger the grade, so `finishExamSection` stays `"fine"`.** The
  `"server-only"` disposition slot ([route.ts:96](../../frontend/app/api/engine/db/[method]/route.ts))
  is used for the **key loader**, never dispatchable; grading happens inside the server-side
  finish. (FR-P2-7 = the key fetch 404s from the client.)
- **The dispatcher already probes exam ownership** ([route.ts:126-137](../../frontend/app/api/engine/db/[method]/route.ts)).
  Exam methods live in the dedicated **`EXAM_LEARNER_ARG`** map (spread into `LEARNER_ARG`,
  [route.ts:20,40](../../frontend/app/api/engine/db/[method]/route.ts)) — the two new methods join
  **that** map. The FR-38 named-arg completeness test and the conformance assertion
  ([http_engine_db.conformance.test.ts:46-47](../../frontend/lib/adapters/engine/db/http_engine_db.conformance.test.ts):
  **exactly 41 methods, 5 server-only** → **43 / 6**) go red on purpose — listed tasks.
- **Image bytes don't fit the JSON dispatcher.** ADR-0040 rejected dedicated exam JSON
  handlers, but a byte-stream with cache headers is a different shape ⇒ **one** dedicated
  authenticated asset route is justified (G1: buys streaming + `Cache-Control`; the simpler
  "base64 through the dispatcher" was rejected — it bloats every form payload).
- **`ExamQuestion.passage` stays** as the analytics facet label; rendering reads the new
  `ExamSection.passages[]` (spec §4.1) — no rename, no facet regression.
- **The exam VM translator is shared with the quiz** (`lib/translators/quiz_item_vm.ts`).
  To keep lanes disjoint and the isolation guard quiet, the exam gets its own tiny VM in
  `components/exam/` rather than widening the shared translator.
- **Private content is absent in CI.** Every lane and CI test runs against a **synthetic,
  non-©ACT 4-section fixture** + a fake `FormAssetStore` (Phase 0). Real-JSON checks run
  locally only.

## 1. Architecture (least machinery)

```
frontend/
  scripts/convert_official_form.ts (+ .test.ts)          Lane A · JSON → client form + keys artifact
  lib/wire/exam_entities.ts                              Phase 0 · +AssetRef, ExamQuestion.image,
                                                                    ExamSection.passages[], ExamPassage,
                                                                    ExamForm.delivery "asset-served"
  lib/ports/engine/form_asset_store.ts                   Phase 0 · ONE interface (P1)
  lib/adapters/engine/exam_forms/
    index.ts                                             Phase 0 · asset-served entries, server-side loader
    exam_image_rule.ts                                   Phase 0 · pure image-necessary rule (shared)
    fixtures/fake_official_form.ts                       Phase 0 · synthetic 4-section asset-served form
    _generated/<form>.client.ts · <form>.keys.ts         Lane A output · GIT-IGNORED (©ACT)
  lib/adapters/engine/assets/
    local_file_asset_store.ts                            Lane B · reads the private folder (base dir via C4)
    fake_asset_store.ts                                  Phase 0 · in-memory fake for tests
  lib/adapters/engine/db/{engine_db,engine_db_disposition,
                          http_engine_db,drizzle_engine_db,
                          in_memory_engine_db}.ts        Lane B · +getExamFormForClient ("fine")
                                                                  +getExamFormKeys ("server-only")
  lib/adapters/engine/exam_server_grade.ts               Lane B · server-side grade-on-finish for
                                                                  asset-served forms (pure scoreExamSection
                                                                  + key loader), keeps route thin (F-R4)
  app/api/engine/db/[method]/route.ts                    Lane B · LEARNER_ARG +2; finish → server grade
  app/api/engine/asset/[formId]/[key]/route.ts           Lane B · auth + FormAssetStore.getImage → stream
  lib/composition_engine{,_browser}.ts                   Lane B · select LocalFileAssetStore (server);
                                                                  browser never gets the store
  components/exam/
    exam_key_posture.ts                                  Phase 0 · per-form posture fn ("server" if asset-served)
    exam_item_vm.ts                                      Lane C · exam-local VM (image + passage refs)
    ExamPassageBlock.tsx                                 Lane C · shared passage block (text + figure image)
    ExamRunnerView.tsx                                   Lane C · text|image branch, placeholder (FR-P2-13)
    exam_review.ts / ExamReviewView.tsx                  Lane C · post-grade reveal only; unscored in review
  tests/architecture/test_exam_no_client_served_keys.test.ts   Phase 0 · HARDENED (resolved graph +
                                                                  payload-schema) + red fixture
  e2e/learn/exam.spec.ts                                 Phase 2 · PT2 section walk, server-graded
docs/adr/0042-…md · docs/preact9secure/README.md (step-2 pointer)   Phase 2
```

Reused as-is: the whole phase-1 runtime (reducer, dwell, write buffer, timer, navigator,
analytics, `exam_*` tables, the 9 exam `EngineDb` methods, `ExamRunRepo`), the pure
`Grader`/`scoreExamSection`, `requireEngineClaim`.

### Delivery + grading data flow (asset-served form)

```
converter (offline, local)  ─►  _generated/pt2.client.ts (text, NO keys)   ─► server registry
                            ─►  _generated/pt2.keys.ts   (keys, server-only)
client  ─ HttpEngineDb.getExamFormForClient(learnerId, formId) ["fine"] ─►  key-stripped form (zod .strict, no answer fields)
client  ─ <img src=/api/engine/asset/pt2/<key>>  ─►  auth ─► FormAssetStore.getImage ─► bytes
client  ─ finishExamSection(...) ["fine", no grades] ─► server: exam_server_grade (keys via getExamFormKeys ["server-only"])
                                                    ─► persists correct/raw/scale ─► client gets results only
```

Client-bundled Test-01 keeps the phase-1 path untouched (ADR-0041 exemption retained).

### `EngineDb` additions (Lane B)

| Method | Disposition | Args | Semantics |
|---|---|---|---|
| `getExamFormForClient` | `"fine"` | `(learnerId, formId)` | Returns the **key-stripped** `ExamForm` (zod `.strict()` schema without answer-bearing fields); `null` if the form isn't loadable server-side (private content absent) |
| `getExamFormKeys` | `"server-only"` | `(formId)` | Answer-bearing key map for grading; **404 from the dispatcher** (FR-P2-7); only `exam_server_grade` calls it |

`finishExamSection` (existing, `"fine"`): for `delivery === "asset-served"` the **server** path
grades before persisting and ignores client-supplied grade fields; client-bundled forms unchanged.

### Image-necessary rule (`exam_image_rule.ts`, pure, Phase 0 — `decisions.md`)

`needsImage(q, passage) = q.text_fidelity ∈ {"math-notation","low"} || passage?.is_figure`.
English/Reading `ok` ⇒ `image = null`. Deterministic; the converter and the fixture both use it.

## 2. Lanes (dependency order; ∥ = parallel, disjoint file sets)

| Lane | Owns (only) | Depends on | FRs |
|---|---|---|---|
| **P0 Base** | wire + zod snapshot · `form_asset_store.ts` port · `exam_image_rule.ts` · `exam_key_posture.ts` per-form fn · registry `asset-served` type + server loader stub · `fixtures/fake_official_form.ts` + `fake_asset_store.ts` · **hardened guard + red fixture** · `.gitignore` for `_generated/` | — | P2-5(flag), P2-8, (fixture for all) |
| **A Converter** ∥ | `scripts/convert_official_form*.ts` | P0 | P2-1, P2-2, P2-3, P2-4, P2-17 |
| **B Server path** ∥ | `lib/adapters/engine/assets/**`, `db/**` (+2 methods, disposition, http/in-memory/drizzle, conformance 41→43), `exam_server_grade.ts`, `app/api/engine/**` (dispatcher `LEARNER_ARG` +2, finish→grade, asset route), `composition_engine*.ts` | P0 | P2-5, P2-6, P2-7, P2-9, P2-14, P2-15, P2-16(design) |
| **C Rendering** ∥ | `components/exam/**` (exam_item_vm, ExamPassageBlock, ExamRunnerView branches, placeholder, review reveal/unscored) — tested against the P0 fixture + fake store, **no** live server | P0 | P2-10, P2-11, P2-12, P2-13, P2-18 |
| **P2 Integrate** | run converter locally (real JSON) → `_generated/` · registry entry PT2 · composition selects `LocalFileAssetStore` (base dir env, C4) · home lists PT2 · e2e walk · ADR-0042 accept · README step-2 pointer | A + B + C | P2-19, DoD |
| **P3 Validate** ∥×4 | **per-section** fidelity validation — English ∥ Math ∥ Reading ∥ Science — each renders every item locally and checks stem/choices/image-use/key against the PDF page + verified JSON; records discrepancies; a tester sits a full run | P2 | DoD (evidence) |

## 3. Migration / rollout

1. Land **P0** on the base branch; freeze wire + port + rule + fixture after it (a lane needing a
   wire change routes it back to base — never edits it in-lane).
2. **A ∥ B ∥ C** in three worktrees, each rebasing on base; merge each when green, any order.
3. **P2** serially: local converter run (private content present), wire PT2, e2e, ADR accept.
   No migration — no schema change (forms are file-loaded server-side; keys never in DB).
4. **P3** — four **parallel per-section validation** passes (§7) once P2 is green, then a
   tester sits a full run. Discrepancies route to fix tasks (sdd-converge), never to
   hand-edits of the generated content.
5. Rollback = remove the PT2 registry entry; Test-01 unaffected.
6. Cloud Run (later, separate): `GcsAssetStore` + middleware signed-URL + bucket/IAM/seed
   (spec FR-P2-16, ADR-0042 follow-on).

## 4. Risks & mitigations

- **©ACT text reaches the client** (unavoidable to render) — bounded by auth (`requireEngineClaim`),
  never in the JS bundle (fetched, not imported), never in git (`_generated/` ignored). Keys
  and images never leave the server pre-grade. **Hardened guard** is the tripwire.
- **CI has no private content** — every lane + CI uses the synthetic fixture; real-JSON converter
  checks are a local-only test tier (documented, not skipped silently).
- **Totality tests break on purpose** (method count 41→43, disposition keys, `LEARNER_ARG`
  completeness, conformance rows) — each a listed red-first task.
- **Converter fidelity** (scale tables, reporting categories, passage/figure detection) —
  asserted against the real PT2 JSON locally with the session's verified keys as the oracle.
- **Three-lane merge** — disjoint directory ownership + Phase-0 freeze; composition roots
  belong to Lane B only.
- **Scope magnets** — 805/5-choice, form picker UX, `GcsAssetStore` build, LLM narrative:
  named non-goals; route to sdd-replan if they surface.

## 5. Stage-4 analyze checklist (run before implementation)

- Every path in §1 probed (glob/grep) — see tasks "grounding" column.
- No `package.json` / `pyproject.toml` runtime change (LocalFile = `node:fs`).
- Baseline `make check` + `pytest tests/architecture/ -q` + `pnpm vitest run` + `pnpm typecheck` green.
- `_generated/` and the private folder are git-ignored **before** the converter first runs.

---

## 6. Parallel-worktree execution + merge strategy

> Clarify answer (2026-09-03): "use multiple worktrees; Science / Math / Reading in three
> parallel worktrees." **Adopted the goal (3 worktrees), re-cut the axis.**

### 6.1 Why not one worktree per section (considered, rejected)

The four sections share **the same code**: one converter, one renderer, one asset store, one
server grade path. Per-section differences are *data* (Math → notation images; Science →
passages + figure images; Reading → text passages; English → clean text) flowing through
shared components. Three worktrees editing `convert_official_form.ts`, `exam_entities.ts`,
`ExamRunnerView.tsx` concurrently = the conflict hotspot the phase-1 plan §6.2 warns about
("splitting them across lanes would collide on the same files"). Each section lane would
also re-build the same passage/image components. **Rejected** — recorded in `decisions.md`.

### 6.2 Lane topology (by disjoint file ownership — same three worktrees)

```mermaid
flowchart TB
  subgraph P0["Phase 0 · BASE (feat/exam-official-forms) — land FIRST, freeze, stays releasable"]
    W[wire: AssetRef · image · passages[] · delivery asset-served + zod snapshot]:::b
    PT[form_asset_store.ts port + fake_asset_store]:::b
    RL[exam_image_rule.ts + per-form exam_key_posture]:::b
    FX[fixtures/fake_official_form (synthetic, non-©ACT, 4 sections)]:::b
    GD[HARDENED test_exam_no_client_served_keys — resolved graph + payload schema + red fixture]:::b
    GI[.gitignore _generated/ · registry asset-served type + server loader stub]:::b
  end
  subgraph P1["Phase 1 · THREE PARALLEL LANES (each its own worktree off base)"]
    A["WT-A Converter · feat/exam-wt-converter<br/>frontend/scripts/** ONLY"]:::w
    B["WT-B Server path · feat/exam-wt-server<br/>lib/adapters/engine/** + app/api/engine/** + composition_engine* ONLY"]:::w
    C["WT-C Rendering · feat/exam-wt-render<br/>components/exam/** ONLY"]:::w
  end
  subgraph P2["Phase 2 · SERIAL on base"]
    I[Integrate: converter run · PT2 registry · LocalFileAssetStore wired · home lists PT2]:::s --> E[e2e PT2 walk, server-graded]:::s --> D[ADR-0042 accept · README step-2 · tester sits a section]:::s
  end
  P0 --> A & B & C
  A -->|merge when green| P2
  B -->|merge when green| P2
  C -->|merge when green| P2
  classDef b fill:#eef,stroke:#88a; classDef w fill:#efe,stroke:#8a8; classDef s fill:#ffe,stroke:#aa8;
```

| Lane | Worktree / branch | Owns (only) | Tests against | FRs |
|---|---|---|---|---|
| **WT-A Converter** | `.worktrees/exam-converter` · `feat/exam-wt-converter` | `frontend/scripts/convert_official_form*.ts` | real PT2 JSON (local) + P0 fixture shape | P2-1…4, 17 |
| **WT-B Server path** | `.worktrees/exam-server` · `feat/exam-wt-server` | `lib/adapters/engine/**`, `app/api/engine/**`, `lib/composition_engine*.ts` | in-memory/sqlite + fake store; conformance | P2-5, 6, 7, 9, 14, 15, 16 |
| **WT-C Rendering** | `.worktrees/exam-render` · `feat/exam-wt-render` | `components/exam/**` | P0 fixture + `fake_asset_store` + fake `ExamRunRepo` | P2-10…13, 18 |

**Why this is conflict-free:** the three file sets are **disjoint** by directory; the only
shared surfaces (wire, port, rule, fixture, posture fn, guard) are landed and **frozen in P0**,
so each lane *inherits* them. Lane C compiles against the `FormAssetStore` interface and the
fixture without any of Lane B's live code; Lane A's output is a git-ignored artifact no lane
imports until P2. Composition roots are Lane B's alone.

### 6.3 Merge strategy — continuous to base

1. Land **P0** on `feat/exam-official-forms` off `main`; base is green (hardened guard proves
   red via fixture, green vacuously — no asset-served form yet). **Freeze** wire/port/rule/fixture.
2. WT-A ∥ WT-B ∥ WT-C branch off base; each rebases on base frequently (base rarely moves post-P0).
3. Merge each lane → base **independently when green** (`make check` + `pnpm vitest run` +
   `pnpm typecheck` + `pytest tests/architecture/ -q`). Order is free (disjoint files). The
   hardened guard bites at **B's merge** (first real asset-served path) — the boundary is
   verified at integration, not deferred to P2.
4. P2 serially on base. Final: one PR `feat/exam-official-forms → main` (or per-phase PRs).

### 6.4 Where "by section" parallelism IS right — Phase 3 validation

Implementation shares files, so it splits by ownership (§6.2). **Validation does not share
files** — it is read-only comparison of rendered output against the source — so it splits by
**section** exactly as first proposed. After P2 is green, run **four parallel validation
passes** (English ∥ Math ∥ Reading ∥ Science; worktrees or subagents — they write only their
own report), each producing a per-item discrepancy table:

| Check | Oracle |
|---|---|
| Every item of the section renders (count = section `question_count`) | verified JSON |
| Stem + choices text match the source (`ok` items) | PDF page render + JSON |
| Image is used **iff** the image-necessary rule says so; the image is the right item | `exam_image_rule` + PNG |
| Passage block shows the right passage for the item's `question_numbers` | JSON passages |
| Server-graded `correct` matches the official key for a scripted answer set | PDF scoring key (p51-style) |
| Unscored items excluded from raw/scale; composite = E+M+R | JSON `scored` + `scale_table` |

Findings feed sdd-converge as fix tasks. This is the manual-validation ask from the start of
the session, now placed where it belongs — *after* the real forms are actually rendered.

### 6.5 Worktree hygiene (this repo)

Fresh worktrees need `frontend/node_modules` symlinked to the main worktree and the root
`.venv` symlinked (repo worktree notes) — do it at `add` time. The **private folder is not
in any worktree by default**: only P2 (and WT-A's local real-JSON tests) need it — point the
converter at the main checkout's `docs/preact9secure/` via its base-dir argument. Also run
`make skills-pack` once per fresh worktree: `docs/skills/sdd-skills-bundle.zip` is git-ignored,
so `tests/architecture/test_skills_pack.py` is red in a new worktree until it exists
(found 2026-09-03; `make skills-sync` does **not** fix it).
