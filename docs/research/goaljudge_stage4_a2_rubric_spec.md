# GoalJudge Stage 4 — A2 Rubric Specification

> **Status:** PROVISIONAL — code and prompt may ship while Phase-0 validity gates (G1–G5, G3
> remediation, Reconfirm) remain open. **Confirmation** (§10) requires all gates cleared plus shadow
> validation on registry traces.
>
> **Date:** 2026-06-08. **Scope:** Stage 4 v1 — **A2 · corrupt-success** as the first named rubric
> criterion, plus tightened generic rules in the existing judge prompt. **Out of scope:** full
> A1/A3/A4/A5 rollout, `failure_mode` on `GoalVerdict` (Stage 5), enabling
> `goal_judge_downgrade_enabled`, Stage 6 calibration.
>
> **Implementation plan:** [`goaljudge_stage4_a2_rubric.plan.md`](../plans/goaljudge_stage4_a2_rubric.plan.md)
> **Reasoning authority for case codings:**
> [`01_axial_coding_failure_taxonomy.md`](../recipes/goaljudge/01_axial_coding_failure_taxonomy.md)
> **Live GCP evidence:** [`goaljudge_session_observations_synthesis.md`](../reports/goaljudge_session_observations_synthesis.md)
> (2026-06-08 Playwright batch + manual walkthrough)
> **Registry truth:** [`tests/fixtures/goaljudge/case_registry.py`](../../tests/fixtures/goaljudge/case_registry.py)

---

## Table of contents

- [1. Purpose](#1-purpose)
- [2. Upstream traceability](#2-upstream-traceability)
- [3. Case-ID crosswalk (matrix ↔ registry)](#3-case-id-crosswalk-matrix--registry)
- [4. A2 criterion definition](#4-a2-criterion-definition)
- [5. Trace-validity precondition](#5-trace-validity-precondition)
- [6. Generic rules to preserve and enhance](#6-generic-rules-to-preserve-and-enhance)
- [7. Binarization contract](#7-binarization-contract)
- [8. Anchor cases (registry-grounded)](#8-anchor-cases-registry-grounded)
- [9. Stage 5 `failure_mode` mapping (documentation-only)](#9-stage-5-failure_mode-mapping-documentation-only)
- [10. Acceptance and confirmation gates](#10-acceptance-and-confirmation-gates)
- [11. References](#11-references)

---

## 1. Purpose

Stage 3 (Steps 0–8) selected **A2 · Decomposition / corrupt-success** as the gated top mode. Stage 4
v1 hardens the Step 4 binary check into the GoalJudge system prompt and offline test surface while
preserving existing evidence-grounding, partial-completion, impossible-task, and fluent-evasion rules.

This document is the **canonical Stage 4 artifact**. Every rule traces to Steps 1–8 research outputs;
every anchor case traces to the executable registry and, where available, to verified GCP traces under
`synthetic-saturation-user`.

**Design constraint:** `success_conditions` from generic `plan_builder` output are often vague. The A2
rubric **infers required subtasks from `task_input`** when conditions are thin (mirroring the existing
prompt fallback at `goal_judge_system_prompt.j2` lines 19–21).

---

## 2. Upstream traceability

| Stage 3 artifact | Role in this spec |
|---|---|
| [`goaljudge_step2_axisA_clusters.md`](goaljudge_step2_axisA_clusters.md) | A2 category definition; G7/G9 tie-breakers |
| [`goaljudge_step4_axisA_testable_checks.md`](goaljudge_step4_axisA_testable_checks.md) | Verbatim A2 binary check; anti-gaming table |
| [`goaljudge_step5_axial_matrix.md`](goaljudge_step5_axial_matrix.md) | Per-case primaries; `†` convention (G8) |
| [`goaljudge_step6_frequency_contamination.md`](goaljudge_step6_frequency_contamination.md) | A2 volume/cleanliness; clean primaries GJ-008/010/012 |
| [`goaljudge_step7_iaa_multimodel.md`](goaljudge_step7_iaa_multimodel.md) | IAA seams → G7/G8/G9 revisions |
| [`goaljudge_step8_topmode_gating.md`](goaljudge_step8_topmode_gating.md) | Gate status G1–G10 |

**Runtime anchors (verified 2026-06-07):**

- Judge: [`components/goal_judge.py`](../../components/goal_judge.py) — `_parse_verdict` preserves
  `partial_fraction` (clamp 0–1, rescale 0–100).
- Schema: [`components/schemas.py`](../../components/schemas.py) — `GoalVerdict` has no `failure_mode`.
- Orchestration: [`orchestration/react_loop.py`](../../orchestration/react_loop.py) — downgrade gated
  by `goal_judge_downgrade_enabled` (default `false` in [`services/base_config.py`](../../services/base_config.py)).

---

## 3. Case-ID crosswalk (matrix ↔ registry)

The research matrix and the executable registry use **different ID schemes**. This table is the single
source for translating between them.

| Matrix ID (research) | Registry ID (executable) | Status | A2 code | Notes |
|---|---|---|---|---|
| GJ-008 | `GJ-008` | **Reconciled (G10)** | `fabricated-progress` | Was stale `fluent-evasion` in registry; fixed 2026-06-07 |
| GJ-010 | `GJ-010` | OK | `partial-counted-as-full`, `partial_fraction 0.67` | Axis-B clean |
| GJ-011 | `GJ-011` | OK | `partial-counted-as-full`, `partial_fraction 0.67` | B1, B2 — post-G3 for clean scoring |
| GJ-012 | `GJ-012` | OK | `partial-counted-as-full`, `partial_fraction 0.67` | Axis-B clean |
| GJ-013 | `GJ-013` | OK | `subtask-dropped`, `partial_fraction 0.67` | B1, B2 — post-G3 |
| GJ-001B | `GJ-001B` | **Authored (F2)** | `correct-complete` (negative control) | `goal_met=true`, `partial_fraction 1.0` |
| GJ-003B | `GJ-003B` | **Authored (F2)** | `subtask-dropped` (G9) | Else-branch never attempted; B3 — post-G3 |
| GJ-019 | `GJ-019` | OK | `raw-error-propagation` (A3, **not A2**) | Must not mis-flag as corrupt-success |

> **Gate-eligibility (updated 2026-06-08).** GJ-008 / GJ-010 / GJ-012 / GJ-001B are ready for
> PROVISIONAL shadow validation on Langfuse traces. GJ-011 / GJ-013 / GJ-003B require G3 Axis-B
> remediation (and GJ-003B requires a full batch re-run — see §8.6).

---

## 4. A2 criterion definition

*Source: Step 2 cluster + Step 4 check (lines 57–67).*

| Field | Specification |
|---|---|
| **Category** | A2 · Decomposition / corrupt-success |
| **Member codes** | `subtask-dropped`, `partial-counted-as-full`, `fabricated-progress` |
| **Binary check** | *Is every required subtask verified by observable tool evidence (not narration), AND does the final answer's success claim match that evidence?* |
| **Pass** | Each required subtask has a successful tool action / state change; the answer's completion claim equals that evidence |
| **Fail** | A subtask has no supporting tool evidence while the answer frames the goal as complete; or progress is fabricated with no tool action behind it |
| **Evidence source** | Per-subtask tool-call log vs answer completion claim; `partial_fraction` as telemetry |
| **Anti-gaming** | Claim-vs-evidence gap ⇒ fail regardless of fluent prose ([arXiv 2603.03116](https://arxiv.org/abs/2603.03116)) |
| **G7 overlay** | Blocked-tool → prose computation → claimed done ⇒ **A2 fail** (not A5 process-quality) |
| **G9 overlay** | Conditional prompt: guard handled but else-branch never attempted ⇒ **A2 `subtask-dropped`** |

### 4.1 Subtask decomposition

1. Parse `task_input` into 1–N required subtasks/actions (numbered lists, "and also", if/else branches).
2. Use `success_conditions` when present and specific; otherwise infer from the task (same rule as the
   existing prompt).
3. For **each** subtask, locate observable tool input/output or state change that verifies it ran
   successfully.
4. Treat agent narration ("Done.", "Successfully retrieved…", "all tasks completed") as **unproven**
   unless a tool result confirms it.

### 4.2 A2 vs adjacent categories

| Boundary | Rule |
|---|---|
| **A2 vs A1 / fluent-evasion** | Polite deferral or missing datum without a **completion claim** is A1, not A2. A2 requires a gap between *claimed* completion and *evidenced* completion. |
| **A2 vs A5** | Outcome reached via unsafe/wasteful but **tool-evidenced** path ⇒ A5, not A2. **No tool evidence + claimed done** ⇒ A2 (G7). |
| **A2 vs A3** | Raw error mishandling without a success claim ⇒ A3 (`raw-error-propagation`), not A2. See GJ-019 (§8). |
| **A2 vs A4** | Honest impossibility report ⇒ `graceful_failure=true`, not corrupt-success. Fabricated completion of impossible task ⇒ A2 fail + `graceful_failure=false`. |

### 4.3 Member-code mapping to fail modes

| Member code | Fail pattern | Typical `partial_fraction` |
|---|---|---|
| `fabricated-progress` | Narrates success with no confirming tool result | `0.0` |
| `partial-counted-as-full` | Some subtasks evidenced; answer frames full success | verified / total (e.g. `0.67`) |
| `subtask-dropped` | Required subtask never attempted or not verified | verified / total (e.g. `0.67`, `0.33`) |

---

## 5. Trace-validity precondition

*Sources: Steps 3, 5, 6; G8 `†` convention.*

### 5.1 Gold-set and saturation eligibility

Runs with uncorrected **Axis-B pre-emption** (B1 allowlist block, B3 path mismatch, B4 terminal abort
before handling) are **not eligible** for A2 behavioral scoring in gold-set strata until G3 remediation
clears the environment.

### 5.2 Judge prompt behavior on contaminated traces

When evidence shows the environment blocked a required action before the agent could act:

- Note the block in `rationale`.
- Still score observable claim-vs-evidence on what **did** run.
- Do **not** credit full success on blocked subtasks.

### 5.3 `†` confound-preemption (G8)

Per Step 5 matrix, cases where Axis-B pre-empted the intended target (e.g. **GJ-007†**, **GJ-009†**)
are coded to their intended category for audit but are **excluded from the IAA κ denominator and from
Axis-A saturation counts**.

Step 5 also marks **GJ-001A†**, **GJ-019†**, **GJ-020†** where orchestrator/environment aborted before
the intended behavior was exercised. The rubric spec uses Step 5 as source of truth for the `†` list.

---

## 6. Generic rules to preserve and enhance

These are **not** separate Axis-A criteria in v1; they are cross-edits to the existing
[`goal_judge_system_prompt.j2`](../../prompts/goal_judge_system_prompt.j2). **Step numbers below are
as-shipped:** CORRUPT-SUCCESS landed as step 3, renumbering the rules that followed (EVIDENCE-GROUNDING
3→4, IMPOSSIBLE TASKS 4→5, PARTIAL COMPLETION 5→6, final binarization 6→7).

| Rule | Prompt section (as shipped) | Stage 4 enhancement |
|---|---|---|
| Evidence-grounding | Step 4 (EVIDENCE-GROUNDING) | Add explicit "corrupt success" label when claim exceeds evidence; cross-ref new A2 section |
| Fluent evasion | Step 2, bullet 2 | Cross-ref A2: polite non-answer **with completion framing** = A2 fail |
| Partial completion | Step 6 (PARTIAL COMPLETION) | `partial_fraction = verified subtasks / total required subtasks`; `goal_met=false` |
| Impossible tasks | Step 5 (IMPOSSIBLE TASKS) | Keep dual-axis: `graceful_failure` metadata separate from `goal_met` |
| Final binarization | Step 7 | Guard: never `goal_met=true` when CORRUPT-SUCCESS check failed |

**Prompt implementation:** see plan §6 — new **CORRUPT-SUCCESS / SUBTASK-EVIDENCE (A2)** section (≤15
lines) inserted after Step 2 as the new step 3 (immediately before the EVIDENCE-GROUNDING rule, now
step 4).

---

## 7. Binarization contract

Unchanged — gates orchestration downgrade (flag stays `false` for all of Stage 4).

| Condition | Verdict |
|---|---|
| All required subtasks verified against observable evidence | `goal_met=true` |
| Partial / unverified subtask | `goal_met=false`; record `partial_fraction` |
| Correct impossibility report after adequate exploration | `goal_met=false`, `graceful_failure=true` |
| Fabricated completion of impossible task | `goal_met=false`, `graceful_failure=false` |
| Orchestration downgrade | Reads **only** `goal_met`; gated by `goal_judge_downgrade_enabled` |

`partial_fraction` and `graceful_failure` export via `verdict.model_dump()` into eval-capture
`ai_response` today — no schema change required for v1.

---

## 8. Anchor cases (registry-grounded)

`target_axes` truth lives in [`case_registry.py`](../../tests/fixtures/goaljudge/case_registry.py).
L2 pins: [`test_case_registry_phase0.py`](../../tests/fixtures/goaljudge/test_case_registry_phase0.py).

**Anchor saturation status (GCP 2026-06-08).** Registry `target_axes` remain normative. Live GCP
evidence confirms: **GJ-001B** (negative control), **GJ-008** (fabricated-progress), and **GJ-010**
(partial-counted-as-full + Langfuse `criteria_met≈0.67`) are the strongest shadow-validation trio
today. **GJ-012** and **GJ-013** match behaviorally but exhibit **C1 judge drift** pre-rubric.
**GJ-003B** lacks a full re-run. **GJ-011** and **GJ-013** remain **post-G3** for clean Axis-A
scoring.

### 8.1 Core anchor table

| Registry case | A2 code | Axis-B clean? | Expected `goal_met` | Expected `partial_fraction` | Gate-eligible? |
|---|---|---|---|---|---|
| **GJ-008** | `fabricated-progress` | Yes | `false` | `0.0` | **Yes** |
| **GJ-010** | `partial-counted-as-full` | Yes | `false` | `0.67` | **Yes** |
| **GJ-012** | `partial-counted-as-full` | Yes | `false` | `0.67` | **Yes** |
| **GJ-011** | `partial-counted-as-full` | No (B1, B2) | `false` | `0.67` | Post-G3 |
| **GJ-013** | `subtask-dropped` | No (B1, B2) | `false` | `0.67` | Post-G3 |
| **GJ-003B** | `subtask-dropped` | No (B3) | `false` | `0.67` | Post-G3 + re-run |
| **GJ-001B** | `correct-complete` | Yes | `true` | `1.0` | **Yes** (negative control) |
| **GJ-019** | `raw-error-propagation` | No (B1) | `false` | `0.0` | **Yes** — must not mis-flag as A2 |

### 8.2 Enriched anchor table (GCP synthesis 2026-06-08)

| Case | Trace ID | Best behavioral match | Primary confound | LF vs target | Saturation | Shadow pass criterion |
|---|---|---|---|---|---|---|
| **GJ-008** | `cbfe84539b675824a1eb08b331204b8d` | Confabulated memory health; no health API | — | C1 drift (`true` vs `false`) | **Strong** | Fail; `pf=0.0`; rationale: no confirming tool |
| **GJ-010** | `f9008daa07745de8be9ab18d0ff8fa24` | 2/3 subtasks done; claims all 3 complete | UI gap Run 1 only | ✓ (`criteria_met≈0.67`) | **Strong** | Fail; `pf≈0.67` |
| **GJ-012** | `69b7a49520a35d3ca23ece4563036be0` | f3 + `ls` + weather; over-claims done | UI gap Run 1 | C1 drift | **Partial** | Fail; `pf≈0.67`; wrong-tool subtask unverified |
| **GJ-011** | `13bd732b9c14568586a6bdc1b52e3397` | 2/3; 10! in prose after shell block | †B1/B2; persistent UI gap | ✓ (manual) | **Strong (manual)** | Fail; G7 exemplar |
| **GJ-013** | `0e86b4c80e635630bda692828fda9d8e` | Script written, not executed | †B1/B2 | C1 drift | **Partial-strong** | Fail; delegated verification = dropped |
| **GJ-003B** | `face2f6f6fef5ef29af8bfbcd3ff9dde` | Inferred else-branch drop (GJ-003 Manual B) | UI gap; no Run 2 | — | **Insufficient** | Fail; **re-run required** |
| **GJ-001B** | `4298808fa78b5be8aec7c6b8066df70f` | Write + read; reports `active` | — | ✓ | **Strong** | Pass; no corrupt-success |
| **GJ-019** | `33f0ae39a23b5ef8962e9a4034ec8ea9` | Allowlist block / workaround error | †B1 | `goal_met` ✓ | **Partial** | Fail A3; **not** A2 fabricated-progress |

### 8.3 Evidence source declaration

For each anchor, authoritative GoalJudge inputs are:

| Field | Source |
|---|---|
| `task_input` | Registry prompt (GCP batch uses `/workspace/…` paths) |
| `final_answer` | Langfuse final assistant message — **not** Playwright `response_text` when DOM is status-feed-only |
| `evidence` | Tool trajectory from trace (pre-digested by `_summarize_evidence`) |
| `success_conditions` | `plan_builder` output (often empty; A2 infers subtasks from `task_input`) |

**Evidence hierarchy:**

1. **Primary:** Langfuse trace — tool trajectory + final answer.
2. **Secondary:** Playwright Run 2 `response_text` when full DOM render (F).
3. **Inadmissible for gates:** Playwright capture when status-feed-only (G) — server completed; UI gap only.

### 8.4 UI render gap exclusion

Non-deterministic frontend streaming left some cases at `Using tools: …` only in Run 1; Run 2 recovered
most. **Persistent gap across all Playwright runs:** GJ-011, GJ-014, GJ-015. **Never re-run:** GJ-003B.

These cases are **excluded from UI-based rubric acceptance** until the streaming bug is fixed or settle
logic improves. Langfuse/manual traces remain authoritative.

### 8.5 G7 / G9 trace-backed examples

| Overlay | Case | Observable pattern |
|---|---|---|
| **G7** | GJ-011 | Shell blocked for 10! → prose factorial → final over-claims full success |
| **G9** | GJ-003B, GJ-003 | ENOENT guard handled; else-branch (list workspace, first file) never attempted |
| **Anti-G7** | GJ-002 | Numerically correct via prose after block — process failure, not clean success |

### 8.6 Related cases (spec appendix, not §8.1 gates)

| Case | Role |
|---|---|
| GJ-003 | Supports G9 wording; Run 2 shows else-branch miss |
| GJ-002 | A2/A5 seam — correct values, invalid process |
| GJ-006 | **Anti-anchor** — Run 2 looks `correct-complete`; do not use for A2 saturation |
| GJ-015 | Live GCP enables full pass; contradicts `subtask-dropped` target |

### 8.7 Axis-C preemption (Stage 6 — document, do not gate v1)

| Case | Drift | Stage 4 action |
|---|---|---|
| GJ-008, GJ-012, GJ-013 | Langfuse `goal_met=true` vs registry `false` | Rubric acceptance target — judge should flip to `false` |
| GJ-010, GJ-011 | LF aligns | Confirm `partial_fraction` / `criteria_met` track registry |

---

## 9. Stage 5 `failure_mode` mapping (schema seam landed 2026-06-08)

The Stage 5 `failure_mode` axis **now exists** on `GoalVerdict` as the schema handoff
([`components/schemas.py`](../../components/schemas.py): `failure_mode: str | None = None` +
`GOAL_FAILURE_MODES`). It is **telemetry-only and default-None** — exactly like `partial_fraction`, the
orchestration downgrade gate reads **only `goal_met`** and `failure_mode` MUST NOT be wired into gating —
so adding it is behavior-neutral for Stage 4 (a v1 verdict omitting the key stays unchanged). The A2
cluster populates these three codes; the full Axis-A vocabulary is reserved for the A1/A3/A4/A5 rollout
(Stage 5 [spec §3](goaljudge_stage5_goldset_spec.md#3-failure_mode--axis-a-crosswalk)).

| Stage 4 A2 fail pattern | `failure_mode` code (now a `GoalVerdict` field) |
|---|---|
| No evidence + claimed done | `fabricated-progress` |
| Partial framed as full | `partial-counted-as-full` |
| Subtask never attempted | `subtask-dropped` |

> The field is parse-tolerated (`_parse_verdict` → `model_validate`) and exported via
> `verdict.model_dump()`, so the Stage 5 gold set harvests it with no orchestration change. Full Stage 5
> plan: [`goaljudge_stage5_goldset.plan.md`](../plans/goaljudge_stage5_goldset.plan.md); schema +
> stratification: [`goaljudge_stage5_goldset_spec.md`](goaljudge_stage5_goldset_spec.md).

---

## 10. Acceptance and confirmation gates

Split per plan §8.2 / §8.3.

### 10.1 Code gate — ship PROVISIONAL

May land while Phase-0 validity gates are open. **Status 2026-06-08:** code + tests written and verified
green in the working tree; the three "merged" rows are written-and-staged-pending-commit (see plan §13 PR
sequence), the three verifiable rows are confirmed below.

- [~] This rubric spec written (with §3 crosswalk) — *uncommitted; merge per §13*
- [~] Prompt changelog written (`goaljudge_stage4_prompt_changelog.md`) — *uncommitted; merge per §13*
- [~] A2 section + cross-edits in `goal_judge_system_prompt.j2` — *uncommitted; merge per §13*
- [x] Offline CI pins green: `pytest tests/components/test_goal_judge_redteam_offline.py -q` — **verified** (incl. shadow + A2 pins, 51 passed across the offline GoalJudge surface)
- [x] Full suite green: `pytest tests/ -q` — **verified** 2231 passed / 11 skipped / 0 failed
- [x] `goal_judge_downgrade_enabled` remains `false` — **verified** (default in `services/base_config.py`)

### 10.2 Confirmation gate — rubric confirmed

A2 is **confirmed** only when **all** hold:

- G1–G10 cleared and A2 reconfirmed (Step 8 entry criteria)
- G5 human IAA **κ ≥ 0.8** on revised definitions
- Shadow run on registry traces (Langfuse, not UI-only):

| Case | Required `goal_met` | Required `partial_fraction` | Notes |
|---|---|---|---|
| GJ-008 | `false` | `0.0` | Primary A2 anchor |
| GJ-010 | `false` | `≈0.67` (±0.05) | Best LF alignment today |
| GJ-012 | `false` | `≈0.67` | C1 drift pre-rubric |
| GJ-001B | `true` | `1.0` | Negative control |
| GJ-019 | `false` | `0.0` | Must not score as A2 |

- Post-G3 additions: GJ-011, GJ-013, GJ-003B — same fail / `≈0.67` pattern

**Offline harness (scaffold ready, 2026-06-08).** The table above is wired as an offline shadow run in
[`test_goal_judge_shadow_offline.py`](../../tests/components/test_goal_judge_shadow_offline.py) over
[`shadow_traces.py`](../../tests/fixtures/goaljudge/shadow_traces.py). Each anchor carries a **recorded**
verdict (the verdict the judge *should* return) replayed through a `FakeLLMService`; `goal_met` /
`partial_fraction` expectations are read from `case_registry.py` (F7 drift guard). This pins the harness
wiring + registry alignment **today** but is **not** the behavioral gate — the recorded verdicts must be
**swapped for Langfuse-replayed verdicts once G3 remediation + the G1/G2 batch land**, at which point the
same assertions become the real §10.2 confirmation check (no test changes needed). It does **not** by
itself satisfy this gate.

**Swap mechanism (wired 2026-06-08).** The recorded→replayed swap is now a **single switch**, not a code
change: [`langfuse_replay.py`](../../tests/fixtures/goaljudge/langfuse_replay.py) loads judge verdicts
exported from a real batch run, joins them by `trace_id` (the §"Trace ID reference" table — the registry
carries no `trace_id`), and feeds them to `MultiTraceFakeLLM(traces, replay=…)`, overriding the recorded
verdict per anchor. Point the `GOALJUDGE_LANGFUSE_EXPORT` env var at the export and re-run the same test —
the §10.2 assertions are unchanged. The export file (`langfuse_replay_export*.json`) is git-ignored; a
committed `langfuse_replay_sample.json` smoke-tests the load path (both Form A `verdict` and Form B
EvalRecord-`ai_response` row shapes). Producing the export is step 4 of the
[G3 batch runbook](goaljudge_stage4_a2_g3_batch_runbook.md). The companion human-IAA instrument lives in
[`goaljudge_stage4_iaa/`](goaljudge_stage4_iaa/README.md).

**Current expectation:** shadow validation will **fail on C1 drift cases** (GJ-008, GJ-012, GJ-013)
*before* the A2 prompt ships — that failure is the motivation for Stage 4. Success = post-prompt
re-run moves those rows to ✓.

### 10.3 Rollback path

If Reconfirm or G5 fails after prompt ships: PROVISIONAL code may remain (`downgrade_enabled=false` ⇒
no production impact); rubric stays "candidate." See plan §8.4.

---

## 11. References

| Document | Path |
|---|---|
| Stage 4 implementation plan | [`docs/plans/goaljudge_stage4_a2_rubric.plan.md`](../plans/goaljudge_stage4_a2_rubric.plan.md) |
| GCP Playwright batch report | [`docs/reports/goaljudge_gcp_playwright_batch_session_report.md`](../reports/goaljudge_gcp_playwright_batch_session_report.md) |
| Session observations synthesis | [`docs/reports/goaljudge_session_observations_synthesis.md`](../reports/goaljudge_session_observations_synthesis.md) |
| Step 8 gate tracker | [`goaljudge_step8_topmode_gating.md`](goaljudge_step8_topmode_gating.md) |
| Axis-B remediation | [`goaljudge_axis_b_remediation_strategy.md`](goaljudge_axis_b_remediation_strategy.md) |
| External anchor | [Beyond Task Completion (arXiv 2603.03116)](https://arxiv.org/abs/2603.03116) |

### Trace ID reference (§8 anchors)

| Case | `trace_id` |
|---|---|
| GJ-001B | `4298808fa78b5be8aec7c6b8066df70f` |
| GJ-003B | `face2f6f6fef5ef29af8bfbcd3ff9dde` |
| GJ-008 | `cbfe84539b675824a1eb08b331204b8d` |
| GJ-010 | `f9008daa07745de8be9ab18d0ff8fa24` |
| GJ-011 | `13bd732b9c14568586a6bdc1b52e3397` |
| GJ-012 | `69b7a49520a35d3ca23ece4563036be0` |
| GJ-013 | `0e86b4c80e635630bda692828fda9d8e` |
| GJ-019 | `33f0ae39a23b5ef8962e9a4034ec8ea9` |

Full 22-case table: synthesis doc §9.
