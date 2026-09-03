# Spec — Exam module phase 2: real official forms (DB/asset-served, key-safe, server-graded, all four sections)

> The spec captures the *what* (testable EARS acceptance criteria). This change fires
> several `⚠️ Ask first` triggers — a **new abstraction** (`FormAssetStore` port), a
> **new server seam** (server-side grading + server-only answer-bearing form fetch), and a
> **wire change** (image + passage rendering fields) — so the plan raises **one ADR
> (ADR-0042)**: exam content moves from the authored `Test-01.md` slice to the real
> official-form JSON, served key-safe and graded server-side.

**Status:** Draft — 2026-09-03
**Owner:** Rajnish Khatri
**Extends:** [exam-module-official-rules.spec.md](exam-module-official-rules.spec.md) (phase 1 — the durable runtime, timing, flags, analytics; its §2.1 named "loading the real official forms" and "rendering Math/Reading/Science" as non-goals and §10.1 named server-side grading "the committed evolution" — **this spec is that evolution**).
**Related:** [ADR-0040](../adr/0040-exam-module-durable-runs-analytics.md) (exam runtime + `/api/engine/db/<method>` seam), [ADR-0041](../adr/0041-exam-answer-key-posture.md) (**the tripwire this spec fires**: first DB-served official form ⇒ server-side grading, keys stripped), [ADR-0038](../adr/0038-durable-engine-seam.md) (`HttpEngineDb → /api/engine/* → pgEngineDb`, `"server-only"` disposition), private ingestion [docs/preact9secure/README.md](../../docs/preact9secure/README.md) (verified form JSON — provenance confirmed this session: sha256 match + 27 extractor tests + full key diffs).

---

## 1. Goal

Give a tester a **faithful, full-length practice exam sourced from a real official ACT
form** — all four sections (English, Math, Reading, Science) — running end-to-end on the
existing exam runtime: timed, navigable, flagged, graded, reviewable, analysed. This is
the **fastest route to a build a human can sit and validate**, using **PT2**
(`act-practice-test-2`, Enhanced ACT) as the first form. The module is built form-agnostic;
a second form (`preact-secure-805`, 5-choice Math) and a full form picker are the
committed follow-up (§2.1).

## 2. Context

- **Phase 1 (shipped).** The `exam` module renders **only** the authored Test-01 English
  slice, **client-bundled**, graded **in the browser** (`EXAM_KEY_POSTURE = "client"`,
  [exam_key_posture.ts](../../frontend/components/exam/exam_key_posture.ts)). The renderer
  ([ExamRunnerView.tsx](../../frontend/components/exam/ExamRunnerView.tsx)) shows a **single
  flat MC question** with optional underlined-`context_html`. There is **no passage block,
  no image field anywhere in the wire schema, and no server-side grading path** (explore
  map, 2026-09-03). `delivery: "db-served"` is a dormant type literal; the `exam_*` tables
  are attempt-tracking only (no form/question content table). `ExamQuestion.passage` exists
  but is used only as an analytics facet key, never rendered.
- **The real forms exist and are verified.** `docs/preact9secure/json/*.json` are faithful
  extractions of the ©ACT PDFs (this session: PDF `sha256` == JSON `source.sha256`; 27
  extractor regression tests pass; PT2 keys diffed section-by-section). PT2 sections:
  English 50 (40 scored) · Math 45 (41 scored) · Reading 36 (27 scored) · Science 40 (34
  scored); **entirely 4-choice** (fits the current renderer's `SUPPORTED_CHOICE_COUNTS =
  [4]` gate — no 5-choice work); **has scale + composite conversion tables**.
- **Text fidelity drives the image need.** Per-question PNGs exist for every question, but
  we render **text from the JSON bank** and pull an **image only where the text is lossy or
  the item needs a figure**: Math **34/45** stems are `math-notation`/`low`; Science ~10
  items sit on data/figure passages; English & Reading text is clean (`ok`) → text only.
- **©ACT content is git-ignored** (`docs/preact9secure/.gitignore` = `*`). Nothing — text,
  images, or keys — may be committed or shipped in the client bundle. Delivery is therefore
  **server-side**, authenticated, learner-scoped.
- **Decisions locked (this session).** Source = real official-form JSON (PT2 first, both
  forms + picker the follow-up); render **text-first, images only where necessary**;
  deliver assets via a **`FormAssetStore` port** — `LocalFileAssetStore` for the local/dev
  MVP ($0, no infra), `GcsAssetStore` as the priced Cloud Run follow-up; tester runs
  **local/dev first**; grading moves **server-side** (ADR-0041 tripwire).

### 2.1 Non-goals (each is its own later spec / the named follow-up)

- **The 805 form and 5-choice Math rendering.** PT2 is all 4-choice; `preact-secure-805`
  (5-choice Math, no scale table) + the renderer/wire work for 5 choices is the follow-up.
- **The `GcsAssetStore` build.** The port + a Cloud Run signed-URL adapter are *designed*
  here (§4.4) and priced, but built at Cloud Run rollout — the local MVP ships
  `LocalFileAssetStore` only.
- **A full multi-form picker UX.** This spec makes PT2 a *selectable* form beside Test-01
  via the existing home list (phase-1 FR-10); a richer picker is follow-up.
- **LLM-authored narratives, FSRS `skill_state` writes, proctoring, Test Mode changes** —
  all remain phase-1 non-goals.
- **Re-deriving the phase-1 runtime.** Timing, flags, dwell, the analytics read model, the
  `exam_*` tables, and the `/api/engine/db/<method>` seam are reused unchanged; this spec
  only adds sourcing, key-safe delivery, server grading, and passage/image rendering.

## 3. Functional requirements (EARS)

Failure paths first. Builds on phase-1 FR-1…FR-41 (unchanged); numbering here is fresh
(FR-P2-n) to avoid collision.

### 3.1 Sourcing & conversion

- **FR-P2-1.** IF the source JSON fails integrity at convert time — `source.sha256` ≠ the
  PDF on record, `declared_question_count` ≠ actual, or any **scored** item lacks an answer
  key — THEN THE converter SHALL fail the build and emit no form (never a partial/for-broken
  form; AP-6).
- **FR-P2-2.** THE converter SHALL read `docs/preact9secure/json/act-practice-test-2.json`
  and emit an `ExamForm` with all four `ExamSection`s, each `ExamQuestion` carrying `stem`
  and `choices` **as text from the JSON**, plus `reporting_category`, `scored`, `passage`
  (label), and an **image asset reference only where** the source `text_fidelity` ≠ `"ok"`
  **or** the item sits on a figure passage (deterministic rule, §4.1).
- **FR-P2-3.** THE emitted **client-facing** form module SHALL contain **no** answer-bearing
  field (`answer_letter`, `per_choice_rationale`, `why_correct_md`, `why_tempted_md`); the
  keys SHALL be emitted to a **separate server-only** artifact, and the client module SHALL
  declare a non-`client-bundled` delivery (§4.3).
- **FR-P2-4.** THE emitted content SHALL NOT be committed to git (©ACT); the converter
  writes under a git-ignored path and the form is loaded server-side at runtime.

### 3.2 Delivery, keys & server-side grading (ADR-0041 tripwire)

- **FR-P2-5 (tripwire).** WHERE a form's `delivery` ≠ `"client-bundled"`, THE SYSTEM SHALL
  set `EXAM_KEY_POSTURE = "server"` and SHALL NOT serialize any answer-bearing field to the
  client at any point (section start, item render, or review before grading).
- **FR-P2-6.** WHEN a section attempt finishes THE SYSTEM SHALL grade it on a **server-only
  path** that fetches the answer-bearing form server-side, runs the pure `Grader`, and
  persists `correct`/`raw_correct`/`scale_score`; the client SHALL receive only graded
  results, never keys.
- **FR-P2-7.** IF the client invokes the server-only grade or answer-bearing-form-fetch
  method directly THEN the `/api/engine/db/<method>` dispatcher SHALL reject it as
  `"server-only"` (404), never execute it client-side.
- **FR-P2-8 (guard hardening — explore caveat).** THE `test_exam_no_client_served_keys`
  guard SHALL assert the **real** contract — no answer-bearing field is reachable in any
  client-served form payload or client bundle for a non-`client-bundled` form — **not** only
  textual co-occurrence with the literal string `"db-served"`; a **red fixture** SHALL prove
  it fires on a real leak.
- **FR-P2-9.** WHEN review is shown for a finished section (after grading) THE SYSTEM SHALL
  serve correct-answer + rationale fields for **already-graded** items only, through the
  authenticated server path (post-submit reveal is allowed; pre-submit is not, FR-P2-5).

### 3.3 Rendering — text-first, images only where necessary

- **FR-P2-10.** WHERE a question's source text is faithful (`fidelity = "ok"`) THE SYSTEM
  SHALL render its `stem` and `choices` as text (English/Reading, most Science).
- **FR-P2-11.** WHERE a question is image-necessary (§4.1 rule) THE SYSTEM SHALL render the
  official question image from the `FormAssetStore` in place of the lossy stem text, with the
  text `choices` still rendered as selectable A–D controls.
- **FR-P2-12.** THE SYSTEM SHALL render a Reading/Science section's **passages** as a passage
  block shared across the section's questions (passage `text`, and the figure **image** where
  the passage carries one) — a capability absent in phase 1.
- **FR-P2-13.** IF a referenced image asset is unavailable from the `FormAssetStore` THEN THE
  SYSTEM SHALL render a visible "content unavailable" placeholder and record it, never a
  broken `<img>` or a silent blank (AP-6 honesty).

### 3.4 Asset delivery (`FormAssetStore`)

- **FR-P2-14.** THE SYSTEM SHALL serve form images through a `FormAssetStore` port; image
  bytes SHALL NOT appear in the client bundle or git. The MVP adapter `LocalFileAssetStore`
  reads the git-ignored private folder **server-side**.
- **FR-P2-15 (security).** THE SYSTEM SHALL serve an image only to the authenticated learner
  of an active/finished run; there SHALL be no anonymous or public route to ©ACT content.
- **FR-P2-16.** THE `GcsAssetStore` (Cloud Run) SHALL be a composition-root swap only; per
  **F-R9** the credential-bearing GCS read happens in **middleware** (signed URL / proxy),
  never in the BFF. (Designed here; built at Cloud Run rollout — §2.1.)

### 3.5 Scoring — Enhanced ACT specifics

- **FR-P2-17.** THE converter SHALL populate each section's `scale_table` from the form's
  conversion tables and set `composite_sections = ["english","math","reading"]` (Enhanced
  ACT — Science reported separately); scale + composite then follow phase-1 FR-27/FR-28
  unchanged.
- **FR-P2-18.** THE SYSTEM SHALL render and accept answers for **unscored** (field-test)
  items and count them in review, but SHALL exclude them from `raw_scored_total`, `scale_score`,
  and `composite` (phase-1 edge case, now exercised for real: 10E/4M/9R/6S unscored in PT2).

### 3.6 Availability

- **FR-P2-19.** WHEN the learner opens the exam home THE SYSTEM SHALL list the PT2 form beside
  the existing Test-01 form with per-section status (reuse phase-1 FR-10); starting/timing/
  navigation/flagging/dwell/analytics for PT2 SHALL behave exactly per phase-1 FR-11…FR-41.

## 4. Data model / contracts

Additive. Nothing in the phase-1 `exam_*` tables changes shape; the phase-1 wire shapes gain
optional fields (back-compatible with the client-bundled Test-01 form).

### 4.1 Wire (`lib/wire/exam_entities.ts`, zod)

```
AssetRef        { store: "form-image", form_id, key }              # opaque server-resolved ref
ExamQuestion   += image: AssetRef | null                            # necessary-image only
ExamSection    += passages: ExamPassage[]                           # NEW (rendered)
ExamPassage     { label, title | null, intro | null, text | null,
                  image: AssetRef | null, question_numbers: number[] }
ExamForm.delivery: "client-bundled" | "asset-served"                # "asset-served" = keys+images server-side
```

**Image-necessary rule (converter, deterministic):** a question gets `image` iff
`text_fidelity ∈ {"math-notation","low"}` **or** its passage is a figure passage
(Science data-representation / research-summary). English & Reading `ok` items → `image = null`.
Answer-bearing fields are **absent** from the client `ExamQuestion` for an `asset-served` form.

### 4.2 Server-only key + form store

The answer-bearing form (`answer_letter` + rationales per `(form_id, section, question_id)`)
lives **server-side only** — a git-ignored generated module or an `exam_form_key` row set —
read exclusively inside the server-only grade path (FR-P2-6). Never imported by any client
module (enforced by FR-P2-8 guard).

### 4.3 Ports / seam

- **New port** `lib/ports/engine/form_asset_store.ts` (ONE interface, P1): `getImage(ref:
  AssetRef) → bytes|stream` (+ `has(ref)`), authenticated at the call site. Adapters:
  `LocalFileAssetStore` (MVP, reads the private folder), `GcsAssetStore` (follow-up, via
  middleware signed URL). Selected in the engine composition root.
- **New server-only EngineDb method(s)** (disposition `"server-only"`, 404 from the
  dispatcher, ADR-0038): fetch the answer-bearing form + grade a section server-side. The
  existing 9 client-callable exam methods and the `/api/engine/db/<method>` dispatcher are
  reused; only the grade/key-fetch path is added and marked `"server-only"`.
- **Key-posture flip** `components/exam/exam_key_posture.ts`: `"server"` for `asset-served`
  forms (Test-01 stays the recorded `client-bundled` accepted-risk exemption, ADR-0041).

### 4.4 Asset delivery route

A server-side authenticated handler streams `getImage(ref)` bytes (`LocalFileAssetStore` reads
the private folder). Cloud Run swap = `GcsAssetStore` where **middleware** mints a short-lived
signed URL (F-R9) and the client `<img>` loads GCS directly; no image bytes cross the BFF, no
GCS credential in the BFF.

## 5. Invariants & security boundaries

- **ADR-0041 tripwire honored.** First `asset-served` form ⇒ server-side grading + keys
  stripped + posture `"server"` (FR-P2-5/6/8). This is the whole point of the ADR-0041
  tripwire; it is not optional.
- **ADR-0038 seam respected.** No new network shape; the server-only grade/fetch method uses
  the existing dispatcher's `"server-only"` disposition slot; learner-scoping unchanged.
- **©ACT copyright.** Content (text, images, keys) is git-ignored and never in the client
  bundle; images served only to the authenticated learner (FR-P2-4/14/15).
- **Frontend Ring (F-R1…F-R9).** `FormAssetStore` is one-interface-per-file (P1); adapters
  import only ports/wire/SDK (A2/A3); **F-R9** — the GCS credential-bearing read is
  middleware-side, never the BFF (FR-P2-16); renderer stays presentational (F-R1).
- **Test exclusivity + isolation.** Phase-1 `test_exam_isolation` unchanged; exam content
  never enters the practice bank / `skill_state` (inherited).
- **Root invariants #1–#8 untouched** (frontend + middleware only; no `trust/`, no graph
  node). No new `pyproject.toml`/`package.json` runtime dependency for the MVP
  (`LocalFileAssetStore` is stdlib fs; GCS SDK arrives only with the follow-up adapter).
- **⚠️ Ask first fired → ADR-0042** at plan stage: new abstraction (`FormAssetStore`), new
  server grade seam, wire change, source-of-truth change (authored slice → real official-form
  JSON). Rejected alternatives to record: keep authored `Test-01.md` and just convert its
  other 3 sections (wrong source); client-bundle the ©ACT form (copyright + key leak);
  DB-blob images (fatter rows); build `GcsAssetStore` up front (infra ahead of the local MVP).

## 6. Edge cases

- **`math-notation` choice text** (not just stems) — if a *choice* is lossy, the item is
  image-necessary and renders the question image; the A–D controls still map to letters.
- **Unscored field-test item** — answerable, in review, excluded from raw/scale/composite
  (FR-P2-18).
- **Passage figure missing a render** — "content unavailable" placeholder (FR-P2-13), section
  still submittable.
- **Reload / device switch mid-section** — server `started_at` + item upserts restore state
  exactly as phase 1; the server-graded result is computed once at finish (idempotent).
- **Composite before Science** — Enhanced ACT composite = mean(English, Math, Reading) scale;
  Science reported separately (FR-P2-17); composite `null` until all three composite sections
  finished (phase-1 FR-8).
- **Client tries to read keys** — no answer-bearing field is ever serialized pre-grade
  (FR-P2-5); the server-only method 404s from the client (FR-P2-7).
- **Local asset folder absent** (fresh checkout without the private ingestion) — the form
  fails to load with a clear message; it is not registered as available (never a blank exam).

## 7. Non-functional requirements

- **Determinism.** Converter and scoring are pure/fixture-tested; server grading is the same
  pure `Grader`, now behind the server boundary.
- **Faithfulness.** Text where the source is faithful; official image where it is not — no
  fabricated linearized math shown to a tester.
- **Latency.** Image serving is a static byte read (local fs MVP); grading is one server
  round-trip at finish; no live LLM anywhere.
- **Reversibility.** Additive wire fields + one port + one server-only method; Test-01 stays
  client-bundled and untouched; PT2 reachable only when the private content is present.
- **Cost.** MVP = $0 (local files). GCS follow-up ≈ $0 running cost (≤$0.001/mo storage for
  all forms; same-region egress free); its cost is the one middleware signed-URL endpoint.

## 8. Test plan

Failure paths first. L1 = vitest pure modules; L2 = BFF handler/adapter + `HttpEngineDb`
conformance against sqlite; L4 = Playwright chromium smoke.

| FR | Test | Layer | In gate? |
|----|------|-------|----------|
| FR-P2-1 | `convert_official_form.test::bad sha/count/missing-key ⇒ build fails` | L1 | yes |
| FR-P2-2 | `convert_official_form.test::4 sections, text choices, image-ref only where necessary` | L1 | yes |
| FR-P2-3 | `convert_official_form.test::client module has zero answer-bearing fields` | L1 | yes |
| FR-P2-5/8 | `test_exam_no_client_served_keys.test::real leak fires (red fixture); asset-served form green` | arch | yes |
| FR-P2-6/7 | `api/engine grade handler test::server-only grades; client-invoke ⇒ 404; keys never in client payload` | L2 | yes |
| FR-P2-9 | `exam_review.test::post-grade reveal only, via server path` | L1/L2 | yes |
| FR-P2-10/11 | `ExamRunnerView.test::text when ok; image when necessary; choices selectable` | L1 | yes |
| FR-P2-12 | `ExamRunnerView.test::passage block renders text + figure image` | L1 | yes |
| FR-P2-13 | `form_asset_store.test / ExamRunnerView.test::missing asset ⇒ placeholder, not broken img` | L1 | yes |
| FR-P2-14/15 | `local_file_asset_store.test::reads private folder; unauthenticated ⇒ refused` | L2 | yes |
| FR-P2-17 | `exam_scoring.test::PT2 scale from table; composite = E+M+R, science separate` | L1 | yes |
| FR-P2-18 | `exam_scoring.test::unscored items excluded from raw/scale/composite` | L1 | yes |
| FR-P2-19 | `e2e/learn/exam.spec::PT2 listed; walk one section end-to-end (server-graded)` | L4 | smoke |

Every new test is **seen to fail first** (red) before its implementation.

## 9. Definition of Done

- [ ] All FR-P2-* implemented; each has a passing test seen to fail first.
- [ ] `make check` green; frontend `pnpm vitest run` + `pnpm typecheck` green;
      `pytest tests/architecture/ -q` green (paste actual counts).
- [ ] ADR-0042 accepted (index + log entries); `decisions.md` line for the image-necessary rule.
- [ ] PT2 loads server-side, all four sections; keys never in the client bundle
      (`test_exam_no_client_served_keys` green with the real form + red fixture proven).
- [ ] Server-side grading proven; `EXAM_KEY_POSTURE = "server"` for the asset-served form;
      Test-01 still `client-bundled` and its e2e still green (ADR-0041 exemption intact).
- [ ] A tester completes a PT2 section locally end-to-end (screenshot/evidence pasted).
- [ ] §2.1 non-goals untouched: no 805/5-choice, no `GcsAssetStore` build, no LLM narrative,
      no FSRS write, Test Mode untouched.
