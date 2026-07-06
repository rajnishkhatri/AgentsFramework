# Spec — Coach pedagogy rubric specificity revision (OVERFLAG-1 CLEAN carve-out)

**Status:** Draft — 2026-07-05
**Owner:** Rajnish Khatri
**Related:** [ADR-0018](../adr/0018-subject-coach-rubric-specificity-revision.md) (the *why*) ·
[ADR-0017](../adr/0017-subject-coach-rubric-revision.md) (the recall revision this corrects) ·
[enable-policy](coach-goldset-enable-policy.spec.md) (ADR-0008 cond#1 floor) ·
[parent ledger](subject-coach-agent.plan.md) (Task 3.9 REFUSE → 3.10).

---

## 1. Goal

Stop the coach pedagogy leakage judge from over-flagging clean teaching as leakage,
so the enable cert clears the ADR-0008 cond#1 floor (TNR≥0.95) **without regressing
recall** (TPR≥0.90). For the Subject-Coach maintainers gating Phase-5 flag flips.

## 2. Context

The Task 3.9 enable cert on the non-provisional `coach_goldset_v1` (116-row test
split, 29 leak / 87 clean) was **REFUSE**: TPR 0.966 ✓, κ ✓, **TNR 0.9186 ✗** (floor
≥0.95). Confusion TP28/FN1/**FP7**/TN79 (+1 abstain, `T-CLEAN-20`, dropped from the
TNR denominator: 79/(79+7)=0.9186) — the judge is not missing leaks, it
over-flags clean rows (7 FP, floor allows ≤4). Open coding of the FPs
(`cache/open_coding/coach-phase39-tnr-fps/coded.jsonl`) axial-collapses to ONE
category, **OVERFLAG-1** (mechanism-teaching / open probe / locus-pointing read as
item-collapse), with **0** gold disputes and **0** incoherent reads — a coherent
rubric-boundary miss. ADR-0018 chose a prose-only carve-out; this spec is its
testable *what*. The rubric already *has* a "What is NOT leakage" tail, but it sits
after the five vivid leak channels and is under-weighted; the fix promotes and
operationalizes it.

## 3. Functional requirements (EARS)

Failure paths (recall protection) first.

- **FR-1 (recall must not regress — the guarding failure path).** IF the specificity
  revision causes any of the ADR-0017 indirect-leak channels to go undetected THEN
  the revision SHALL be rejected: the fresh re-cert TPR SHALL be ≥ 0.90 (`tpr_min`).
- **FR-2 (no test-split tuning — §9).** IF the rubric wording is validated THEN it
  SHALL be scored on a **fresh** held-out split, and the 116-row 3.9 test split (and
  the 7 coded FP rows) SHALL NOT be used to score the revision.
- **FR-3 (the specificity fix — the core behavior).** THE pedagogy rubric SHALL state
  a first-class CLEAN test **beside** (not after) the decisive test: teaching a
  rule/mechanism, pointing at an in-sentence cue, or asking an open
  classification/agreement probe is CLEAN when ≥2 options remain live until the
  learner maps the rule to a choice themselves.
- **FR-4 (count-the-surviving-options step).** WHEN the judge evaluates leakage THE
  rubric SHALL instruct it to enumerate which answer options it believes are
  eliminated and which remain live, and to flag `answer_leakage=true` only when ≤1
  option remains live.
- **FR-5 (name the two over-reads as non-leaks).** THE rubric SHALL state that (a) an
  open probe is not `socratic-clothing` unless only one option survives the question
  itself, and (b) naming a rule is not `rule-naming` leakage unless one option
  uniquely satisfies it on THIS item.
- **FR-6 (no numeric threshold in the prompt — config split).** THE rubric SHALL
  express the CLEAN test and the option-count as prose reasoning, NOT a numeric
  threshold baked into the `.j2` (ADR-0017 rejected-B stands).
- **FR-7 (version bump).** THE revised rubric header SHALL carry
  `rubric_version = coach_rubric_v2_specificity`, and the goldset/cert machinery that
  records `rubric_version` SHALL reflect it.
- **FR-8 (schema unchanged).** THE `PedagogyVerdict` contract and `LeakChannel` enum
  SHALL be unchanged (prose-only revision; no `trust/` change, no re-sign).
- **FR-9 (exit bar, with margin).** WHEN the fresh re-cert runs THE decision SHALL be
  `ENABLE` only if TNR≥0.95 AND TPR≥0.90 AND κ≥0.75, and the revision SHALL clear TNR
  with margin above 0.95 (not a knife-edge pass — see §7 determinism).

## 4. Data model / contracts

No schema change. `PedagogyVerdict` (float axes + `*_pass` + `answer_leakage` +
optional `leak_channel: LeakChannel|None`) is untouched — this is a `.j2` prose edit
plus a `rubric_version` string bump. The `coach_goldset_v1` manifest's
`rubric_version` field is the one recorded value that changes. The enable evaluator
(`services/governance/coach_calibration.py`) and its floors are unchanged — the fix
is upstream of the gate, in the judge.

## 5. Invariants & security boundaries

- **prompts/ H1 / AP-3 (config split):** the fix lives in
  `prompts/subject_coach_pedagogy_judge.j2` as prose; no numeric threshold enters the
  template (FR-6). Thresholds remain in code (`COACH_ENABLE_THRESHOLDS`).
- **Trust purity (Invariant #2):** no `trust/` change; `PedagogyVerdict` is a
  `components/` type, so no re-signing.
- **No live LLM in CI:** the re-cert is manual/local (creds-gated); CI replays
  committed labels offline via the `run_coach_calibration` pure core. The fresh
  re-cert is NOT wired to `make check`.
- **⚠️ Ask-first:** one trigger — AP-3 rubric prose — covered by ADR-0018.

## 6. Edge cases

- **Recall/specificity tension:** a carve-out strong enough to clear the 7 FPs can
  re-admit a real leak — FR-1's TPR gate is the guard; a revision that lifts TNR by
  dropping a leak fails.
- **Judge non-determinism at temp=0:** a clean row flipped tn→fn between two 3.9
  replays; the fresh re-cert must clear TNR with margin, and abstentions (provider
  timeouts) are dropped from the confusion, never counted as `false` (AP-6 — mirrors
  the replay harness).
- **Fresh split does not yet exist:** the 116-row test split is now "seen" by this
  fix; a new held-out clean+leak split (human α-labeled) is a prerequisite, not an
  afterthought (see §Open / tasks).
- **The 8th flagged row (`T-CLEAN-20`) abstained** on a provider timeout and was
  dropped from the confusion (not scored as an FP) — the carve-out is derived from 7
  confirmed FPs; the 8th is expected to be the same OVERFLAG-1 class but is not assumed.

## 7. Non-functional requirements

- **Cost/latency:** the revised prompt is longer (already long after ADR-0017) — a
  small, accepted cost/latency bump.
- **Determinism:** the exit bar is an L4-style aggregate over a fresh split, not an
  L1 exact assertion; the ≥0.95-with-margin rule accounts for run-to-run judge drift.
- **Reversibility:** prose-only + version bump — trivially revertible; no data
  migration.
- **CI:** no path added to the `make check` hot path; the live re-cert stays
  on-demand/local.

## 8. Test plan

Failure-path (recall + §9) first.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | fresh re-cert TPR≥0.90 (no recall regression) — replay of committed fresh-split labels | L4 | no (on-demand/local) |
| FR-2 | test asserts the fresh-split ids are disjoint from the 3.9 test split + coded FP ids | L1 | yes |
| FR-3 | L1 grep: the pedagogy `.j2` contains a first-class CLEAN test section before the "five channels" block (extends the ADR-0017 FR-10/FR-12 header-grep gate) | L1 | yes |
| FR-4 | L1 grep: the `.j2` contains the enumerate-surviving-options instruction | L1 | yes |
| FR-5 | L1 grep: the `.j2` names open-probe and rule-naming non-leak carve-outs | L1 | yes |
| FR-6 | L1: no numeric-threshold token added to the `.j2` (reuse the prompts threshold-ban check) | L1 | yes |
| FR-7 | L1: `rubric_version == coach_rubric_v2_specificity` in the header + manifest | L1 | yes |
| FR-8 | L1: `PedagogyVerdict`/`LeakChannel` schema unchanged (existing contract tests still green) | L1 | yes |
| FR-9 | fresh re-cert `evaluate_coach_enable_gates` → ENABLE with TNR margin | L4 | no (on-demand/local) |

## 9. Definition of Done

- [ ] FR-3/4/5/6/7 landed in `prompts/subject_coach_pedagogy_judge.j2` (prose-only) with
      passing L1 grep/version tests seen to fail first.
- [ ] A **fresh** held-out split (clean+leak, human α-labeled) exists and is disjoint
      from the 3.9 test split (FR-2 test green).
- [ ] Fresh re-cert run: `evaluate_coach_enable_gates` → **ENABLE**, TNR≥0.95 with
      margin, TPR≥0.90, κ≥0.75 — actual `cert → … verdict=ENABLE gates={...}` output
      pasted into the ledger (not summarized).
- [ ] `make check` green; `tests/architecture/` green (ADR ratchet satisfied by
      ADR-0018).
- [ ] Parent ledger Task 3.9 recorded REFUSE + Task 3.10 (this revision) status
      updated; Phase 5 remains gated until ENABLE.

---

## Open (routes to tasks / sdd-replan)

1. **Fresh-split production is the gating prerequisite** — the current goldset has no
   held-out split left after this fix "sees" the test rows. Options: corpus expansion
   (the batch-2 synthetic path) or a fresh-authored control+leak set, human
   α-labeled. This is the biggest piece of work and should be a task, not an
   afterthought.
2. **Model for the re-cert:** 3.9 used `gpt-4o`. Decide whether the re-cert uses the
   same model (comparable to 3.9) or the Opus reasoning tier (ADR-0017's acceptance
   model) — a `decisions.md` note either way.
3. **8th flagged row (`T-CLEAN-20`, abstained)** re-fetch (`refetch_one.py`) to confirm
   OVERFLAG-1 before freezing the carve-out wording — optional, low cost.
