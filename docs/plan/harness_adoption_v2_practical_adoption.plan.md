# Practical-Adoption Assessment — Harness Adoption v2 Plan

> **Status:** In progress — **Wave 0 COMPLETE**, **Wave 1 SUBSTANTIVELY COMPLETE**
> (2026-06-28). Waves 2–4 pending. Wave 1's residual gate now PASSES; the only Wave-1
> remainder is the *deferred live A/B + blind re-adjudication* that grows the frozen
> seed past 100 rows (corpus authored; live runs gated for go-ahead). Nothing
> committed yet (commit only when asked).
>
> ### Execution log
>
> **2026-06-28 — Wave 1 landed** (residuals; the 🔴 core). The re-adjudication the
> plan demanded (1.1) **overturned the plan's premise** and the work followed the
> evidence (ADR-0003):
> - **1.1 — re-adjudicate `70ff3369`.** The deepseek-v4-pro answer for
>   `GEN-L3-iterative-refine-15` is **truncated at source** (ends mid-sentence at
>   "office: up", before the cuts/verification). GoalJudge's `goal_met=false` was the
>   *correct* call; the blind gold `correct` label was the error (rater-1's note
>   "proceeds to cut proposal" — it never does). Per user choice, **excluded** as a
>   truncated-at-source data defect via the freeze script's audited `EXCLUDED_ITEMS`
>   (seed 53→**52 rows**, v0.1; blind α 0.910 holds, blinding preserved).
> - **The real TNR breach was elsewhere.** `judge_validation` after exclusion still
>   FAILED (TNR 0.875) on **2 FPs on `GEN-L2-dependency-resolve-12`**: claude-haiku +
>   claude-opus produced **reversed** topological orders (`A→B→C→D` vs correct
>   `D,B,C,A`) and the LLM rubric rubber-stamped them. The **deterministic verifier
>   cascade** (`components/answer_verifiers.py`, already on this branch) grades these
>   correctly. Applied it **offline with zero live-LLM** via the new
>   `scripts/apply_verifier_cascade_l2l3.py` (mirrors `GoalJudge.evaluate`'s contract:
>   verifier bool wins, abstain→LLM verdict). Flips 2 FP + 1 FN toward gold.
> - **Gate now PASSES:** `judge_validation` TPR 1.0000 / TNR 0.9375 (both ≥0.90),
>   across strict-clean, strict-full, and exclude-partial mappings (n=37/52/25).
> - **1.2 — version + ADR.** Wrote **ADR-0003** (registered in `index.md`/`log.md`,
>   `okf_lint` 0 failures) recording the re-adjudication, the exclusion, and the
>   cascade overlay. Seed manifest bumped v0.0→v0.1 with an `excluded_items` field.
> - **1.3/1.4 — grow seed ≥100 (authoring half done; live half deferred).** Authored
>   **9 new L2/L3 cases (16–24)** — fixtures + `GROUND_TRUTH` in
>   `seed_model_ab_l2l3_workspace.py`, corpus rows via new
>   `scripts/build_l2l3_growth_corpus.py`, answer keys regenerated (**18 cases** →
>   18×6 arms = 108 cells ≥100). Cases 17/20/21 are verifier-checkable (free
>   grading); 16/18/19/22/23/24 are prose. Tests updated + green (lint/format clean).
>   **Deferred (gated, spends budget):** the live A/B sweep over the 18-case batch +
>   judge pass + 2-rater blind re-adjudication that actually grows the *frozen* seed
>   to ~108 rows. Until then the seed stays at 52 (gate already passes there).
>
> **2026-06-28 — Wave 0 landed** (4 items, docs/json only — no Python touched,
> JSON valid, `okf_lint` 0 failures):
> - **5.3 ADOPT** — `AGENTS.md` ✅ Always gained two lines: red/green TDD
>   ("watch it fail first") + "demand evidence — paste actual output, not a summary."
> - **3.2 ADAPT** — `.cursor/hooks.json` `afterFileEdit` kept `failClosed:false`
>   (advisory formatter per HOOK-1) with an inline `_comment_failClosed` documenting
>   the scoped deviation; safety gate `beforeShellExecution` stays `failClosed:true`.
> - **6.3 ADOPT** — `docs/adr/decisions.md` created (frontmatter `type: log`),
>   registered in `index.md` + `log.md`; first entry = the 3.2 decision.
> - **6.1a ADOPT** — `docs/plan/_spec_template.md` (EARS, failure-paths-first,
>   invariant/security section, FR→test table); referenced from `AGENTS.md`.
> - Side effect: `AGENTS.md` 126 → 134 lines (the +8 W0 additions). The Wave-3
>   bounded trim (5.4) pulls it back toward ~115.
>
> **2026-06-28 — SDD lifecycle runbook reviewed + accuracy-fixed** (6.1a-adjacent
> process artifact, `docs/research/agenticengineeringplaybook/sdd_lifecycle_runbook.md`):
> Reviewed against the playbooks + this session's work; verdict **keep** (operationalizes
> 6.1 as an executable 10-stage human↔agent loop; agrees independently with this plan
> that the constitution is already `AGENTS.md` + `tests/architecture/` and Spec Kit must
> *project* from it, not rebuild). Four fixes applied: (1) "14 tests" → "14 test files /
> 106 test functions" (verified on disk); (2) reconciled the `.cursor/hooks.json`
> `afterFileEdit failClosed` item to the Wave-0 decision (kept `false` by design, was
> calling for the rejected flip); (3) updated `_spec_template.md`/`decisions.md` to
> "landed Wave 0" + demoted `tech-debt-tracker.md` to **[v2-P6.2]** not-yet-created
> (it's DEFER); (4) added an "⚠️ Adoption status" banner — the `/speckit.*` spine is
> aspirational pending the 6.1b trial (`.specify/` MISSING, skills not installed), with
> the runnable-today subset listed. Untracked, uncommitted; outside `make check`/OKF surface.

## Context

`docs/research/agenticengineeringplaybook/harness_adoption_critical_review_and_v2_plan.md`
was written 2026-06-28 as a critique of the Track A/B/C harness work plus a 6-phase,
~30-item improvement plan. It was written against a **snapshot** of the repo. Since
then, a second effort — the **unified context-routed reviewer** plan — landed its first
five work items the *same day*, which moved several seams the v2 plan assumed were
missing. This document does **not** re-litigate whether the critique is right (it is, on
its own terms). It assesses, item-by-item, whether each proposed item is **practically
adoptable in this workspace today** — does the seam exist, what's the cost/risk, does it
collide with the in-flight reviewer work or the security constraints — and produces a
**sequenced execution path** of only the items worth doing, in feasibility order.

Deliverable confirmed with the user: adoption assessment **+** sequenced execution plan,
reconciled with the unified-reviewer plan.

---

## What changed since the v2 plan was written (the reframe)

Verified on disk this session:

- **The unified-reviewer plan landed WI-1…WI-5** (2026-06-28, branch
  `fix/track-b-eval-review-hardening`): `code_reviewer/routing.py` (deterministic path
  router, 36 tests), **10 per-folder `REVIEW.md`** maps (cite-don't-copy), the **v3
  single reviewer prompt** (`prompts/codeReviewer/v3/`, FD1–FD7), TDD fold into v3/D3 +
  `TDD_AGENTS_MD_REVIEW.md` deprecated, and **`scripts/hooks/AGENTS.md`** with
  HOOK-1/2/3. `review_config.py` now allows `{v1,v2,v3}`.
- This **supersedes or front-runs** several v2 items (5.4 partly, M9 partly, the TDD
  concern entirely) and **overlaps** the deferred WI-6…WI-9.
- **The C1 evidence is weaker than the v2 plan states.** `residual_fp_revalidation.json`
  re-validated **2** cases, not 3: `df252d51` the judge scored **correctly**
  (`matches_expectation: true` — the answer really does omit the claim); only
  `70ff3369` is a true false-positive. And that one FP's 5 rationales cite **genuine
  arithmetic incoherence** ("850 vs 880", "non-zero remainder framed as offset"), *not*
  the "wants the literal words 'zero-balance'" story in the plan. So item 1.1 is **not**
  a trivial phrase-allowlist edit — it needs real re-adjudication of whether the answer
  is actually coherent.
- **`meta/judge_prompt.j2` is a generic 1–5 taxonomy scorer** — it has no
  "zero-balance" sub-criterion at all. The verification criterion lives in the L2/L3
  *case rubric/answer-key*, not the prompt template. So 1.1's "edit the rubric" points
  at the goldset/case definitions, not `judge_prompt.j2`.

---

## Adoption verdict — by phase

Legend: **ADOPT** (do as written) · **ADAPT** (do, but the plan's framing/target is off) ·
**DEFER** (real but not now / blocked) · **DONE/SUPERSEDED** (already shipped) · **SKIP**.

### Phase 1 — close the named residuals 🔴

| Item | Seam verified | Verdict | Note |
|---|---|---|---|
| **1.1** fix GoalJudge rubric | `meta/judge_prompt.j2` (generic), case rubric in goldset; `goaljudge_calibration.py` ✓ | **ADAPT** | Not a word-allowlist fix. Only 1 of 2 revalidated FPs is real; its answer is arithmetically incoherent. **Re-adjudicate the case first**, then fix the rubric *or* relabel the gold row. Don't ship a fix that teaches the judge to pass incoherent answers. |
| **1.2** file FP as guardrail bug + version judge | `goaljudge_calibration.py` ✓, `docs/adr/` ✓ | **ADOPT** | After 1.1, bump GoalJudge manifest version + ADR. Correct per playbook P14. |
| **1.3** grow seed to ≥100 | seed = 53 rows ✓, blind-adj corpus exists | **ADOPT** | Underpowered at n=53 (CI ±13.5pt). Gated on 1.4 for the new rows. |
| **1.4** run L2/L3 blind adjudication | `docs/plans/model_ab_l2l3_blind_adjudication.plan.md` = "PLAN (not started)" ✓ | **ADOPT** | Plan written + scoped. This is the keystone — unblocks 1.3 *and* the "L2/L3 UNGRADED" gap. **Do first in Phase 1.** |

**Phase-1 reorder:** 1.4 → 1.3 → 1.1 (re-adjudicate) → 1.2. The plan lists 1.1 first;
the evidence says 1.4 must precede it (the adjudication produces the labels that decide
whether `70ff3369` is a judge bug or a correct fail).

### Phase 2 — make Track C mechanically enforced 🟠

| Item | Seam | Verdict | Note |
|---|---|---|---|
| **2.1** `Stop`-hook ADR trigger | no Stop hook wired; `.claude/settings.local.json` has PreToolUse+PostToolUse only | **ADAPT (verify-first)** | Highest-leverage Track C uplift, but the plan **assumes the Stop payload carries touched-files**. Must verify against *this* Claude Code version before building (claude-code-guide check). Fallback if not: a pre-commit/pre-push sensor diffing the ADR-trigger paths — works regardless of hook payload. Wire fail-safe (HOOK-3). Add its own ADR. |
| **2.2** forced-engagement wording + re-add G3/G7 | gates G1/G4/G8 in `AGENTS.md`; no `GATES.md` | **ADAPT** | Real gap (named-gate-without-mechanism). But put the rotating wording in **`docs/adr/GATES.md`** as the plan says — do **not** bloat root `AGENTS.md` (we're already at 126 vs 90–110 target; M6). Honest limit stands: hooks can't capture the typed answer, so this is convention + the 2.1 trigger. |
| **2.3** rotate gate wording | — | **ADOPT** | Cheap; lives with 2.2 in `GATES.md`. |

### Phase 3 — missing sensors 🟠

| Item | Seam | Verdict | Note |
|---|---|---|---|
| **3.1** test-deletion/skip detector | no `pre_commit_test_guard.py`, no `test_no_test_weakening.py`; pre-commit + arch-tests exist ✓ | **ADOPT** | The mechanical form of G8. Lowest-risk, highest-ratio sensor. Implement as a `tests/architecture/` test (git-diff `tests/**` for removed `def test_*` / added skip/xfail) **or** a pre-commit hook. Prefer the arch-test (already a trusted gate, runs in CI). |
| **3.2** `.cursor/hooks.json` afterFileEdit→failClosed:true | confirmed `false` ✓ | **ADAPT — DONE (W0)** | Resolved in Wave 0: kept `false` (advisory formatter, HOOK-1) with inline `_comment_failClosed` + `decisions.md` entry, rather than flip-and-break-edits. |
| **3.3** mutation testing scoped to `trust/` | no `mutate-trust`, no mutmut | **DEFER** | Right idea (behaviour-harness gap), but new dev-dep + new subsystem. Not a blocker; schedule after Phase 1–3 land. Keep off CI hot path (no live cost, but slow). |

### Phase 4 — judge validation to 2026 MVVP bar 🟡

| Item | Seam | Verdict | Note |
|---|---|---|---|
| **4.1** test-retest + position-bias | `judge_validation.py` has TPR/TNR/RG/κ only ✓; 5-trial data exists ✓ | **ADOPT** | `residual_fp_revalidation.json` already bootstraps test-retest. Pure functions, L1, no live calls — fits the module's existing contract. Position-bias only applies to pairwise use. |
| **4.2** cross-family judge for Claude arms | judge = claude-haiku-4-5 | **DEFER** | Sound (self-enhancement risk) but adds a second provider + cost. Do on a sample, after 4.1. Not gate-critical. |
| **4.3** graduate first regression tier | `eval_graduation.py` `graduate()`+`regression_floor_violations()` ✓; **no row tagged `tier: regression`** | **ADOPT** | Converts Track B from machinery to practice. Tag stable high-pass L1 rows `tier: regression`; wire `regression_floor_violations()` into a gate. **The single biggest "machinery-without-practice" fix.** |
| **4.4** schedule pass^k | `make model-ab` ("NEVER in CI") ✓; no `model-ab-passk` | **ADAPT** | Add `make model-ab-passk` (wraps existing `pass_hat_k`). **Cadence/cron only — never CI** (live LLM constraint). A scheduled GitHub Action *or* a documented pre-swap manual run. |

### Phase 5 — context engineering & workflow discipline 🟡

| Item | Seam | Verdict | Note |
|---|---|---|---|
| **5.1** subagent-as-firewall + define `explore`/`reviewer` | no `.claude/agents/` dir | **ADAPT** | The *prose* convention in `AGENTS.md` is cheap+good. Defining a `reviewer` subagent **overlaps unified-reviewer WI-6** — do it *there*, not here, to avoid two reviewer dispatch surfaces. An `explore` (read-only) subagent is independent → ADOPT that half. |
| **5.2** `PostCompact` re-injection | no PostCompact hook | **DEFER (verify-first)** | Mitigates a real gotcha (nested AGENTS.md don't survive `/compact`). But depends on PostCompact being a supported event in this CC version (verify). Lower priority than 2.1/3.1. |
| **5.3** two `AGENTS.md` lines (red/green TDD, paste real output) | partially present (G4 ≈ "green test you can't explain is not done") | **ADOPT — DONE (W0)** | Landed in Wave 0. The explicit "watch it fail first" + "paste actual output" lines are in `AGENTS.md` ✅ Always. |
| **5.4** trim root `AGENTS.md` to 90–110 | 134 lines (after W0 +8); Key Directories table duplicates nested | **ADAPT (bounded)** | Architecture Invariants are load-bearing and must stay in root (a nested file loads too late). Safe trims: Key Directories per-folder detail (dup'd in nested), the 6 `@`-imports. **Do not** drop invariants to hit a number. Likely floor ~110–115, not 90. |

### Phase 6 — spec-anchored + janitor 🟡

| Item | Seam | Verdict | Note |
|---|---|---|---|
| **6.1a** repo-native EARS spec template | `_spec_template.md` ✓ (W0); ADR template exists ✓ | **ADOPT — DONE (W0)** | `docs/plan/_spec_template.md` created (EARS, failure-paths-first, invariant/security section, FR→test table); referenced from `AGENTS.md`. |
| **6.1b** Spec Kit CLI scoped trial | no `.specify/`; constitution-equivalent = `AGENTS.md` invariants ✓ | **DEFER** | Trial-then-decide is correct, but it's the heaviest item and **the constitution concept overlaps the v3 reviewer + AGENTS.md hierarchy already shipped**. Run the trial only after 6.1a proves the methodology; seed any constitution *from* AGENTS.md. Not now. |
| **6.2 / 6.2.1** janitor + drift dashboard | `.github/workflows/` has **no cron** (all push/PR); no `tech-debt-tracker.md` | **DEFER** | Real (instruction/doc drift isn't caught by `tests/architecture/`). But it's a new scheduled subsystem; do after the sensors (Phase 3) and regression tier (4.3) exist so the janitor has signals to track. |
| **6.3** lightweight `decisions.md` | `docs/adr/decisions.md` ✓ (W0); ADR bundle ✓ | **ADOPT — DONE (W0)** | Created, registered in `index.md` + `log.md`, OKF lint clean. |

---

## Reconciliation with the unified-reviewer plan (overlap map)

| v2 item | Unified-reviewer status | Resolution |
|---|---|---|
| TDD review concern (whole) | **WI-4 DONE** — TAP-1…4 folded to v3/D3, doc deprecated | **SUPERSEDED** — drop from v2 scope. |
| M9 fresh-thread review gate | router+rules **DONE** (WI-1/3); dispatch **deferred WI-6** | **MERGE into WI-6** — don't plan a second gate. |
| 2.2 / H1 forced-engagement wording | not in unified plan (it's about *rules citation*, not human gates) | **Independent** — keep in v2 (Phase 2), lives in `GATES.md`. |
| 5.1 `reviewer` subagent | **deferred WI-6** (Claude Code dispatch) | **MERGE into WI-6**; v2 keeps only the `explore` subagent + the firewall prose. |
| 6.1b constitution | AGENTS.md hierarchy + v3 prompt = de-facto constitution **DONE** | Trial must **seed from** existing assets, not rebuild. Reinforces DEFER. |
| WI-8 (validate reviewer judge ≥0.90) | **deferred** | Same TPR/TNR machinery as v2 4.1 — **reuse `judge_validation.py`** for both. |

Net: the reviewer-shaped half of the v2 plan is mostly **already done or belongs in
WI-6…WI-9**. The v2 plan's *distinct* value is **Phases 1, 3, 4** (residuals, sensors,
judge rigor) + a few cheap doc items (5.3, 6.1a, 6.3 — all landed in Wave 0).

---

## Recommended execution sequence (feasibility-ordered, reversible)

**Wave 0 — cheap, zero-risk, no dependencies (hours): ✅ DONE (2026-06-28)**
- 5.3 (two AGENTS.md lines) · 3.2 (cursor failClosed decision) · 6.3 (`decisions.md`) ·
  6.1a (`_spec_template.md`). All landed; see Execution log at top.

**Wave 1 — the residuals (the 🔴 core), reordered: ← NEXT (paused for go-ahead, spends live-LLM budget)**
- 1.4 blind adjudication → 1.3 grow seed ≥100 → 1.1 **re-adjudicate `70ff3369`** then
  fix rubric/relabel → 1.2 version + ADR. Gate: `judge_validation` PASS (TPR≥0.90 AND
  TNR≥0.90) on ≥100 rows. Candidate driver: `agentsframework-eval` skill.

**Wave 2 — sensors + practice (🟠/practice):**
- 3.1 test-weakening arch-test → 4.3 graduate `tier: regression` + wire floor gate →
  4.1 test-retest + position-bias in `judge_validation.py` → 4.4 `make model-ab-passk`
  (cadence only).

**Wave 3 — Track C mechanism (verify-first):**
- 2.1 Stop-hook ADR trigger (verify payload; pre-commit fallback) → 2.2/2.3 `GATES.md`
  wording + G3/G7 re-add → 5.4 bounded AGENTS.md trim → explore subagent (5.1 half).

**Wave 4 — deferred subsystems (schedule, don't block):**
- 3.3 mutation testing (`trust/`) · 5.2 PostCompact re-inject · 4.2 cross-family judge ·
  6.2 janitor + dashboard · 6.1b Spec Kit trial.

**Hand to WI-6…WI-9 (not v2):** M9 review gate, `reviewer` subagent dispatch, reviewer
judge validation (reuse 4.1 machinery).

---

## Critical files (read/edit targets when executing)

- **Residuals:** `docs/plans/model_ab_l2l3_blind_adjudication.plan.md`,
  `cache/goaljudge_eval/model_ab_l2l3_goldset_seed.json`,
  `cache/goaljudge_eval/residual_fp_revalidation.json`, the L2/L3 case rubric/answer-key,
  `services/governance/goaljudge_calibration.py`, `meta/judge_validation.py`.
- **Sensors:** `tests/architecture/` (new `test_no_test_weakening.py`),
  `.cursor/hooks.json`, `scripts/hooks/` (+ `AGENTS.md` cite),
  `services/governance/eval_graduation.py`, `Makefile`.
- **Track C:** `docs/adr/GATES.md` (new), `docs/adr/decisions.md` (created W0),
  `.claude/settings.local.json` (Stop wiring), `AGENTS.md` (5.3 lines done; bounded trim pending).
- **Spec/janitor (deferred):** `docs/plan/_spec_template.md` (created W0),
  `.github/workflows/` (cron), `docs/adr/tech-debt-tracker.md` (new).
- **Reuse, don't rebuild:** `meta/judge_validation.py` (4.1 + WI-8),
  `model_ab_eval.py::pass_hat_k` (4.4), `code_reviewer/routing.py` (reviewer dispatch),
  ADR template `docs/adr/0000-template.md`.

## Verification (per wave)

- **W0 ✅:** `AGENTS.md` shows the TDD/evidence lines; `_spec_template.md` + `decisions.md`
  exist; `.cursor/hooks.json` decision recorded; `okf_lint` 0 failures.
- **W1:** `python -m meta.judge_validation` → `VALIDATION: PASS`, TPR≥0.90 AND TNR≥0.90,
  n≥100; L2/L3 adjudication frozen (κ≥0.80); GoalJudge version bumped + ADR linked.
- **W2:** a commit deleting `def test_*` fails the arch-test; ≥1 row `tier: regression`
  and `regression_floor_violations()` gates a drop; `judge_validation` prints
  test-retest + position-bias; `make model-ab-passk` runs (off-CI).
- **W3:** an ADR-trigger edit with no new `docs/adr/*` → Stop hook blocks (or pre-commit
  fallback); `GATES.md` has rotated wordings incl. G3/G7; root `AGENTS.md` ≤ ~115.
- **W4 (when scheduled):** `make mutate-trust` reports a score; PostCompact re-injects;
  janitor cron has opened ≥1 PR; Spec Kit trial outcome recorded as an ADR.

## Out of scope (agreed not to do)

- Multi-agent fleets/orchestration tooling (playbook scopes out for solo operator).
- Spec-as-source / code-as-generated (repo is durable + human-curated).
- A typed-answer-capturing gate (hooks can't; honest limit stands).
- Lowering the TNR floor to dodge C1 (fix the judge/label, don't move the goalpost).
- Re-planning the reviewer gate here (belongs in unified-reviewer WI-6…WI-9).

> Note: this assessment is documentation only. Nothing here is committed; per the
> standing constraint, commit only when the user asks.
