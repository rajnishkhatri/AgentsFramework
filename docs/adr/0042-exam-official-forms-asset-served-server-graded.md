---
type: decision-record
title: 'ADR-0042: Exam content source of truth — real official-form JSON, asset-served, server-graded (fires the ADR-0041 tripwire)'
status: proposed
created: 2026-09-03
updated: 2026-09-03
owner: Rajnish Khatri
related: exam-module-official-forms.spec.md, exam-module-official-forms.plan.md, 0041-exam-answer-key-posture.md, 0040-exam-module-durable-runs-analytics.md, 0038-durable-engine-seam.md
tags: [decision-record]
---

# ADR-0042: Exam content source of truth — real official-form JSON, asset-served, server-graded (fires the ADR-0041 tripwire)

**Status:** Proposed — 2026-09-03 (Stage-2 plan gate).
**Related:** [spec](../plan/exam-module-official-forms.spec.md) · [plan](../plan/exam-module-official-forms.plan.md) · [ADR-0041](0041-exam-answer-key-posture.md) (the tripwire this fires — **amended** here to Option B for asset-served forms) · [ADR-0040](0040-exam-module-durable-runs-analytics.md) (the runtime this loads content into) · [ADR-0038](0038-durable-engine-seam.md) (`"server-only"` disposition slot) · private ingestion [README](../../docs/preact9secure/README.md).
**Audience:** anyone adding an exam form, touching `exam_forms/`, `FormAssetStore`, the exam grade path, or the `no_client_served_keys` guard — and anyone who assumes the exam "already serves the real forms."

---

## Context

The shipped exam module serves **only English**, and that English is the **authored**
`PreAct/practice-tests/Test-01.md` slice (an original practice test "built to the Form 805
spec") — **not** a real ACT form — converted by `convert_test01_english.ts`, **client-bundled**
with its answer key, and **graded in the browser**. The user discovered this as "only English
is implemented"; the phase-1 spec had deliberately scoped the real forms and the other three
sections as non-goals (§2.1) and named server-side grading "the committed evolution" (§10.1).

The real official forms already exist as **verified** JSON under the git-ignored
`docs/preact9secure/json/` (this session: PDF `sha256` == JSON `source.sha256`; 27 extractor
regression tests pass; PT2 keys diffed section-by-section against the PDF's scoring page).
They are **©ACT**: nothing may be committed or shipped in a public bundle.

[ADR-0041](0041-exam-answer-key-posture.md) accepted client-side grading for phase-1 **only
because** no trigger was fired, and pre-committed to server-side grading with keys stripped
"the moment the first DB-served official form lands" (**delivery** trigger). Loading a real
form fires that trigger. Explore map (2026-09-03): there is **no** server grading path, **no**
image field in the wire, **no** passage rendering, and `db-served` is a dormant literal — so
this is a genuine build, not a switch flip.

---

## Decision

Source exam forms from the **verified private official-form JSON** via an offline converter;
deliver them **`asset-served`** — question **text** fetched by the authenticated learner (never
in the JS bundle, never in git), **answer keys server-only**, **images through a `FormAssetStore`
port** — and **grade server-side** (ADR-0041 **Option B**, now enabled for asset-served forms).
Ship **PT2** (`act-practice-test-2`, Enhanced ACT, all 4-choice) first across **all four
sections**; render **text-first, official image only where the text is lossy or the item needs a
figure**; `LocalFileAssetStore` for the local/dev MVP, `GcsAssetStore` (middleware signed-URL,
F-R9) as the Cloud Run follow-up. Test-01 stays client-bundled as ADR-0041's recorded exemption.

---

## Options considered & rejected

| Option | Verdict |
|---|---|
| **A. Real official-form JSON, asset-served, server-graded** (**chosen**) | The only option that is both *faithful* (real ACT items, official keys + conversion tables) and *safe* (keys never client-side, ©ACT never in bundle/git). Fires ADR-0041's pre-committed flip exactly as designed. Cost **M**: converter + port + 2 `EngineDb` methods + server grade hook + passage/image rendering. |
| **B. Keep authored `Test-01.md`, convert its other three sections** | Cheapest, but the **wrong source**: original practice content built *to* a blueprint, not a real ACT — a tester cannot validate official fidelity, and Test-01's 5-choice Math + no scale table give worse coverage than PT2. Rejected. |
| **C. Client-bundle the ©ACT form like Test-01** | Puts copyrighted text **and keys** in a public JS bundle; fires the ADR-0041 tripwire anyway (delivery) while violating it. Rejected outright. |
| **D. Images as base64/bytea blobs in the engine DB** | One seam, but bloats every form payload/row and adds a seed of image bytes for no local benefit — the images are already files on disk. Rejected for the MVP; not precluded later. |
| **E. Build `GcsAssetStore` up front** | ~$0 running cost but pulls bucket + IAM + a **middleware** signed-URL endpoint (F-R9 forbids GCS creds in the BFF) ahead of a *local* tester loop. Deferred behind the port (one-adapter swap), priced in the spec §7. |
| **F. Parallelize implementation by section (Science/Math/Reading worktrees)** | Sections share one converter/renderer/store/grade path — per-section lanes collide on the same files. Re-cut by file ownership (plan §6). Recorded in `decisions.md`. |

---

## Rationale

- **Faithfulness is the point.** The whole ask is a test a human can sit and trust; only real
  items with official keys and conversion tables deliver that. PT2 first because it is all
  4-choice (drops into the existing renderer gate) and carries scale/composite tables.
- **ADR-0041 pre-decided the safety posture.** The delivery trigger is fired; enabling
  Option B now is the planned code diff, not a retrofit under stake. The exemption for the
  public Test-01 slice stays intact, so nothing already shipped changes posture.
- **Least machinery that still honors copyright.** Text must reach the learner to render;
  keys and images need not. `asset-served` draws that line: authenticated fetch for text, a
  port for images, server-only keys. `LocalFileAssetStore` is `node:fs` — no dependency, no infra.
- **The port earns its place (G1).** Two real substrates exist by decision (local files now,
  GCS at Cloud Run), matching the repo's V3/V2 adapter pattern; the simpler "hard-code fs
  reads" was rejected because the Cloud Run swap would then touch the route and renderer.
- **Text-first, image-only-where-necessary** keeps English/Reading crisp and selectable
  (0 images) while making Math (34/45 lossy stems) and figure-based Science answerable.

---

## Consequences

- **Commits us to** server-side grading + key stripping for every `asset-served` form;
  `EXAM_KEY_POSTURE` becomes per-form (`"server"` for asset-served). **ADR-0041 is amended**:
  Decision → Option B for asset-served forms; Test-01 client-bundled exemption retained.
- **The `no_client_served_keys` guard is hardened** from a textual `db-served` co-occurrence
  heuristic to a real contract (resolved-graph: no client-reachable import of `*.keys.ts`;
  payload-schema: the client form is `.strict()` with no answer-bearing field) with a red
  fixture — the explore map showed the old guard passes vacuously.
- **New surfaces:** `FormAssetStore` port + `LocalFileAssetStore`; wire `AssetRef`,
  `ExamQuestion.image`, `ExamSection.passages[]`, `ExamForm.delivery: "asset-served"`;
  `EngineDb` +2 (`getExamFormForClient` fine, `getExamFormKeys` server-only; count 41→43);
  one authenticated byte-stream asset route; `exam_server_grade.ts`; `ExamPassageBlock`.
- **Accepted risk:** question **text** (not keys, not images) reaches authenticated learners —
  unavoidable to render; bounded by auth, no bundle, no git. Recorded, not hidden.
- **CI cannot see private content** ⇒ a synthetic non-©ACT 4-section fixture + fake store is
  the CI/lane test substrate; real-JSON converter checks are a documented local-only tier.
- **Follow-ons (committed):** `preact-secure-805` + 5-choice Math rendering; a form picker;
  `GcsAssetStore` + middleware signed-URL + bucket/IAM/seed for Cloud Run.

---

## Compliance

Automatable: (1) hardened `test_exam_no_client_served_keys` — resolved-graph + payload-schema
+ red fixture; (2) converter integrity test (sha/count/missing-key ⇒ build fails; client artifact
has zero answer-bearing fields); (3) asset route refuses unauthenticated requests; (4)
dispatcher 404s `getExamFormKeys`; (5) `EngineDb` count/disposition/`LEARNER_ARG` totality tests.
Manual: a tester sits one PT2 section locally end-to-end (DoD).

---

## Supersedes / related

- **Amends** [ADR-0041](0041-exam-answer-key-posture.md) (fires its delivery tripwire; Option B for asset-served forms). Does not supersede it.
- Builds on [ADR-0040](0040-exam-module-durable-runs-analytics.md) and [ADR-0038](0038-durable-engine-seam.md).
- Realizes [exam-module-official-forms.spec.md](../plan/exam-module-official-forms.spec.md) via [exam-module-official-forms.plan.md](../plan/exam-module-official-forms.plan.md); extends [exam-module-official-rules.spec.md](../plan/exam-module-official-rules.spec.md) phase 1.
