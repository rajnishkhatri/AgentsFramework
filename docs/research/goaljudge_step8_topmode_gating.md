# GoalJudge Step 8 — Top-Mode Pick + Stage-4 Gating Conditions

> **⚠️ PROVISIONAL / GATED.** This step makes two decisions: **what the first judge/rubric should
> target** (the *top mode*) and **what must clear before building it** (the *gate*). The top-mode pick
> is **A2 · corrupt-success**, but it is **gated** — every frequency it rests on is
> confound-contaminated and the IAA bar is unmet. Nothing here authorizes Stage-4 rubric construction
> until the gate conditions below clear. Lands in [Phase 3](goaljudge_phase3_axial_coding.md) **§6.3**
> (top mode) and **§7** (gate).

## Scope and posture

- **Computed from**, not coded fresh:
  - [`goaljudge_step6_frequency_contamination.md`](goaljudge_step6_frequency_contamination.md) (+ `.csv`)
    — the Axis-A primary frequency, the clean/contaminated split, and the Axis-A↔Axis-B co-occurrence.
  - [`goaljudge_step7_iaa_multimodel.md`](goaljudge_step7_iaa_multimodel.md) (+ `.csv`) and the
    superseded [`goaljudge_step7_iaa_kappa.md`](goaljudge_step7_iaa_kappa.md) — the reliability number
    and the three definition revisions the disagreements demand.
  - [Phase 3 §7](goaljudge_phase3_axial_coding.md) — the validity-gate conditions (registry join, E1
    export, Axis-B remediation, GCS posture).
- **Walkthrough step** [`05_…walkthrough.md`](../walk-through/05_goaljudge_axial_coding_failure_taxonomy_walkthrough.md)
  §Step 8: "Pick the **biggest, cleanest-aligned** Axis-A category as the top mode… then **gate it**."
- **Role split.** The agent assembles the evidence and drafts the gate; the **human analyst owns the
  top-mode decision and the saturation/gating verdict** (playbook R3/R12). The pick below is recorded
  as the analyst's disposition of the agent's proposal, not a delegated call.

## The decision: top mode = **A2 · Decomposition & progress-accounting / corrupt-success**

Per the playbook ("build one judge for your biggest issue first"), the top mode must be the category
that is simultaneously **largest**, **cleanest** (least confound-contaminated), and **tightest-aligned**
to a checkable `goal_met` consequence. **A2 wins on all three** — the only category that does.

| Signal | A2 (picked) | A1 | A4 | A3 | A5 |
|---|---|---|---|---|---|
| **Volume** (primary count / 17) | **7** | 4 | 4 | 2 | 0 |
| **Cleanliness** (Axis-B-clean primaries) | **3** (GJ-008/010/012) | 0 | 1 (GJ-022, carries C2) | 0 | — |
| **Target alignment** | **GJ-010/011: `goal_met=false` + `criteria_met≈0.67` ≈ registry `partial_fraction`** | forced to prose by B1 | dual-pole, no single target | handling never tested (B4 pre-empts) | orthogonal to `goal_met` |
| **External anchor** | **[arXiv 2603.03116](https://arxiv.org/abs/2603.03116) "corrupt success"** | — | — | — | — |
| **Verdict** | ✅ **top mode** | rejected | rejected | rejected | rejected |

### Why the others were rejected

- **A1 (semantic/synthesis), volume 5 — rejected on cleanliness.** Tied-second on count, but **0 of
  5** A1 primaries are Axis-B-clean: every one sits on a `B1` allowlist block that forced a prose
  fallback. Building a synthesis judge on A1 would be measuring the sandbox, not the agent.
- **A4 (feasibility/gracefulness), volume 4 — rejected as incoherent target.** It is a **dual-pole**
  bucket (honest-graceful *vs* unhandled-impossible), so it cannot become *one* rubric criterion;
  and its only Axis-B-clean primary, GJ-022, carries an Axis-C judge drift.
- **A3 (error handling), volume 2 — rejected on contamination.** Fully **B4-shaped**: the
  orchestrator's terminal-escalation fires before the agent can handle the error, so A3 handling was
  never cleanly exercised.
- **A5 (process quality), volume 0 — rejected as non-primary.** Appears only as a *secondary* code;
  it is orthogonal to `goal_met` and belongs as a cross-cutting check, never a top mode.

### The headline caveat that gates this pick

The same Step 6 recompute that selects A2 also shows **16 of 21 rows carry ≥1 Axis-B code** — the
modal session "failure" is *the sandbox blocking a required command*, not the agent reasoning poorly.
A2 is picked because it owns **3 of the only 4 Axis-B-clean failure primaries** — i.e. it is the
strongest *behavioral* signal precisely because most everything else is environment noise. That makes
A2 the right *first* target **and** makes the gate non-negotiable: the count is real but small, and it
must survive an environment-corrected re-run.

## Stage-4 gating conditions (must clear before any rubric work)

Two families: **validity gates** (G1–G5, from Phase 3 §7 — without these the counts are not evidence)
and **consistency gates** (G6–G9, surfaced by Steps 6–7 — without these the taxonomy is not yet
self-consistent or reliably applicable). The machine-readable form with owners is in
[`goaljudge_step8_topmode_gating.csv`](goaljudge_step8_topmode_gating.csv).

### Validity gates (Phase 3 §7)

| Gate | Status | What must happen |
|---|---|---|
| **G1 · Registry join / batch re-run** | **OPEN** | UI runs used random `workflow_id`s (no registry join, Axis-B5). Re-run GJ-001–GJ-022 with deterministic `trace_id`s + `user_id=synthetic-saturation-user` via `scripts/run_goaljudge_synthetic_batch.py`. |
| **G2 · `eval.goal_judge` export (E1)** | **OPEN** | `logs/evals.log` has **zero** `target=goal_judge` rows. The GoalJudge axes (`graceful_failure`, `partial_fraction`, `per_criterion`) and **Axis-C** confirmation depend on requirement **E1**. |
| **G3 · Axis-B environment correction** | **OPEN** | Re-run with `/workspace`-aligned paths, shell allowlist widened / prompts adapted, and the `classify_outcome` B4 escalation reviewed — so each Axis-A code reflects the agent, not the sandbox. Sequencing: [`goaljudge_axis_b_remediation_strategy.md`](goaljudge_axis_b_remediation_strategy.md). |
| **G4 · GCS posture confirmed** | **OPEN** | `curl $BACKEND_URL/healthz \| jq .goal_judge` shows a file-backed `gs://…/ops/goal_judge_config.json` source before crediting any `goal_met`. |
| **G5 · Human IAA κ ≥ 0.8 on Axis-A** | **OPEN** | Only model passes exist: single-model κ = 0.77 (partially blind, superseded); **five-model blind panel Fleiss' κ = 0.50** (moderate). A real **human** panel on the revised definitions is the actual playbook requirement. |

### Consistency gates (from Steps 6–7 — close these *before* the re-run is coded)

| Gate | Status | What must happen |
|---|---|---|
| **G6 · Count reconciliation (§6.1/§6.3)** | **CLEARED** | Phase 3 §6.1/§6.3 match Step 5 with G9: GJ-003B → A2; A1=**4**, A2=**7**. Applied 2026-06-07. |
| **G7 · Def revision — A2/A5 prose-after-block** | **CLEARED** | Step 2 §"Definition revisions (G7, G9)" — "no tool evidence + claimed done" ⇒ **A2**, not A5. Applied 2026-06-07. |
| **G8 · Def revision — `†` no-final-answer mapping** | **CLEARED** | Step 5 `†` rule sharpened: excluded from κ denominator + Axis-A saturation count. Applied 2026-06-07. |
| **G9 · Def revision — A1/A2/A3 conditional prompt** | **CLEARED** | Step 2 §"Definition revisions" — else-branch never attempted ⇒ **A2 `subtask-dropped`**; registry `GJ-003B` authored. Applied 2026-06-07. |
| **G10 · GJ-008 registry coding** | **CLEARED** | `case_registry.py` GJ-008 `target_code` → `fabricated-progress` (recipe Lesson 5 / Step 6). **Analyst sign-off: approved 2026-06-07.** L2 pins in `test_case_registry_phase0.py`. |

> **Dependency order.** G6–G9 are cheap documentation fixes that should land **first** (they cost
> nothing and make the re-run's coding unambiguous). G3 (Axis-B remediation) gates G1/G5 in practice —
> there is no point re-running for clean counts until the environment that produced the confounds is
> corrected. G5's *human* IAA should run on the **revised** definitions (post-G7–G9), not the current
> ones, so the κ measures the taxonomy we intend to ship.

## What "cleared" looks like (Stage-4 entry criteria)

The top mode (A2) graduates from *candidate* to *confirmed* — and Stage-4 rubric work may begin — when:

1. The registry-prompt batch re-run (G1) under `synthetic-saturation-user` has produced `eval.goal_judge`
   rows (G2) on an Axis-B-corrected environment (G3) with confirmed GCS posture (G4); **and**
2. A2 is still the largest/cleanest Axis-A category on those *re-taken* counts (the pick is
   **reconfirmed**, not assumed); **and**
3. Definitions G7–G9 are merged and a **human** IAA pass on them clears **κ ≥ 0.8** (G5); **and**
4. §6.1/§6.3 are internally consistent (G6).

Until then: the **taxonomy structure** (Phase 3 §3–§5) is usable for Stage-4 *design*; the **counts**
(§6) and this **top-mode pick** (§6.3) stay **PROVISIONAL**.

## Acceptance check (Step 8 walkthrough)

- Top mode picked — **A2 corrupt-success** — on the biggest-and-cleanest rule, with A1/A3/A4/A5
  explicitly rejected and the reason recorded. ✔
- The pick is **gated**, not frozen: validity gates G1–G5 (Phase 3 §7) + consistency gates G6–G9
  (Steps 6–7) recorded with status and owner. ✔
- Stage-4 entry criteria stated (reconfirm-on-re-run + human κ ≥ 0.8 + count reconciliation). ✔
- Phase 3 §6.3 and §7 are filled and marked **PROVISIONAL / GATED**; this doc is the consolidated
  Step 8 view they point to. ✔
