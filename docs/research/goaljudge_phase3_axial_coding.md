# GoalJudge Evaluation Pipeline: Phase 3 Axial Coding & Failure Taxonomy

> **⚠️ STATUS: PROVISIONAL / GATED — JUNE 4, 2026**
> The **taxonomy structure** below (the three axes and their categories) is firm and ready to
> drive Stage 4 rubric design. The **frequency counts** and the **top-mode pick** are
> **provisional**: they are derived from the GJ-001–GJ-022 *manual GCP-UI session*
> ([session report](../reports/goaljudge_manual_walkthrough_gj001_gj022_session_report.md)), which
> the session report itself flags as **not** a clean saturation surface — UI runs use random
> `workflow_id`s (no registry join), carry **no** `goal_judge` `eval_capture` rows, and are heavily
> contaminated by the **harness/environment confounds** catalogued on Axis B. **Do not freeze any
> count or build the Stage-4 rubric on these numbers** until the registry-prompt batch re-run +
> `eval.goal_judge` export (requirement **E1**) lands under `synthetic-saturation-user`. See §7.
>
> **Document purpose.** Execute Stage 3 of the
> [GoalJudge evaluation pipeline](goaljudge_evaluation_pipeline_open_axial_coding_rubric.md):
> cluster the Stage-2 open codes into a small set of named, counted, *testable* failure categories
> (the **failure taxonomy**), separating genuine agent-behavior failures from the environment and
> judge-reliability confounds that the manual walkthrough surfaced. This is the bridge between
> [Phase 2b open coding](goaljudge_phase2b_open_coding.md) and Stage 4 rubric design.

---

## 1. Scope, inputs, and the problem this stage solves

### 1.1 Inputs (Stage 2 outputs — reused, not restated)

| Input | Provides |
|---|---|
| [Dimension space & codebook](goaljudge_synthetic_dimension_space.md) | D1–D5 space; the **19-code merged taxonomy** with operational definitions + first-failure rule |
| [Phase 2b open coding](goaljudge_phase2b_open_coding.md) | Saturation log (15 live agent-behavior codes ≥3×); the **5-cluster bridge** seed (§4) |
| [GJ-001–GJ-022 session report](../reports/goaljudge_manual_walkthrough_gj001_gj022_session_report.md) | Per-case codings, §5.2 recurring tool-failure modes, §5.3 saturation eligibility, the **emergent environment codes** |
| [Pipeline playbook](goaljudge_evaluation_pipeline_open_axial_coding_rubric.md) | Stage-3 method, IAA contract, repo-mapping, references R1–R20 |

### 1.2 The problem: the manual session surfaced two *confound* families the codebook does not hold

The 19-code codebook is a clean **agent-behavior** taxonomy. But the GJ-001–GJ-022 walkthrough ran on
the **GCP UI sandbox**, and that environment injected a whole second layer of codes that have nothing
to do with the agent's reasoning:

1. **Harness / environment confounds.** `shell-allowlist-block` (`echo`/`printf`/`touch`/`exit`/
   `git`/`pytest` not allowlisted), `shell-metachar-block` (`;`, `>`, `2>/dev/null` rejected by the
   validator), `workspace-mount-missing` / host-path-outside-boundary (`/workspace` ENOENT for shell
   while the `file_io` boundary *is* `/workspace`), and `tool-error-to-terminal` (the orchestrator's
   `classify_outcome` escalates **any** tool output starting with `"Error:"` that lacks the word
   `"tool"` straight to a terminal abort — GJ-020/GJ-021). Many session "failures" are **sandbox
   artifacts**, not agent failures.
2. **Judge-reliability drift.** `lf-goal-met-drift` (GJ-008/012/013/015: Langfuse `goal_met=true` vs
   registry target `false`) and `lf-criteria-drift` (GJ-022: `criteria_met=0.5` vs target `0.0`).
   These are *judge* defects — the J2/J3 family already named in the codebook — not agent defects.

**If these are folded into the behavioral clusters, Stage 4's rubric is built on poisoned counts** —
you literally cannot tell "the agent failed to audit" from "the sandbox blocked every command the
agent tried." So Stage 3 keeps **three orthogonal axes** and codes each case on all three:

| Axis | What it captures | Feeds |
|---|---|---|
| **A — Agent-behavior failure taxonomy** | The 16 active agent-behavior codes, clustered (`tool-stub-limitation` retired → Axis B) | Stage 4 rubric criteria + gold-set `failure_mode` enum |
| **B — Harness / environment confound** | Sandbox/orchestrator artifacts that *masquerade* as agent failure | Stage 4 **trace-validity precondition** (which cases may be counted) |
| **C — Judge reliability** | The 2 judge-quality codes (J2/J3) + observed LF drift | Stage 6 judge calibration / red-team |

### 1.3 Why three axes — trade-off reasoning (external grounding)

This is not an idiosyncratic choice; it is the **published norm** for agentic-failure taxonomies in
2025–2026, and the alternatives were considered and rejected:

| Option | Pro | Con — why rejected |
|---|---|---|
| **Single-axis fold-in** (env codes become more behavioral clusters) | Simplest; one taxonomy | **Biases every Stage-4 count** — "agent failed" and "sandbox blocked agent" land in the same bucket. The session shows this is most cases (GJ-002/004/005/007/009/011/013/014/019/020/021). |
| **Env codes out of scope** (validity-threats appendix only) | Keeps taxonomy pure to the codebook | Discards the session's **biggest finding** and leaves Stage 4 blind to *which* cases are valid evidence. |
| **Three orthogonal axes** ✅ | Clean per-category frequencies; explicit validity filter | Costs one extra coding pass per case — the only real cost, and it is cheap and mechanical. |

**External precedent.** *Characterizing Faults in Agentic AI: A Taxonomy of Types, Symptoms, and Root
Causes* ([arXiv 2603.06847](https://arxiv.org/abs/2603.06847)) builds a taxonomy on **exactly** a
multi-axis structure (Fault Type / Symptom / Root Cause) and **explicitly partitions
environment-infrastructure faults** ("Runtime & Environment Grounding", "Tooling, Integration &
Actuation", "System Reliability & Observability") **from agent-cognition faults** ("Agent Cognition &
Orchestration", "Perception, Context & Memory") — via grounded theory (open → axial → selective
coding), Cohen's κ 0.83–0.86, encoding each fault as `Category=X, Symptom=Y, Root Cause=Z`. Our
Axis A ≈ their cognition faults; our Axis B ≈ their environment/runtime faults. The separation is
their central methodological move, and it is ours.

---

## 2. Methodology

- **Grounded-theory axial coding.** Open codes (Stage 2) → **axial** clustering into categories →
  **selective** synthesis into the three named axes. This is the standard open→axial→selective
  pipeline used by both MAST ([arXiv 2503.13657](https://arxiv.org/abs/2503.13657), NeurIPS 2025,
  κ = 0.88) and the agentic-fault taxonomy ([2603.06847](https://arxiv.org/abs/2603.06847)).
- **LLM-assisted clustering, human-validated.** Per the playbook ([R3](goaljudge_evaluation_pipeline_open_axial_coding_rubric.md)),
  an agent assistant may *propose* clusters from the open-code CSV, but a human owns the final names
  and rejects over-broad categories ("capability limitations" is not actionable). The
  [walkthrough](../walk-through/05_goaljudge_axial_coding_failure_taxonomy_walkthrough.md) operationalizes
  this split.
- **First-failure discipline.** The **primary** Axis-A code is the *first* point the trajectory
  deviated; cascading downstream symptoms are secondary (codebook §4.2). This matters because the
  session shows long cascades — e.g. a `shell-allowlist-block` (Axis B) → prose fallback →
  `incomplete-synthesis` (Axis A). Error-propagation as the dominant failure driver is the headline
  finding of AgentErrorTaxonomy ([arXiv 2509.25370](https://arxiv.org/abs/2509.25370)): "a single
  root-cause error propagates through subsequent decisions."
- **≤3 codes per case per axis.** Preserves cascade signal (codebook §4.1).
- **Each category must be *testable*.** A category is admissible only if you can write a binary
  pass/fail check for it (the seed of a Stage-4 rubric criterion) — "interrupts user mid-thought,"
  not "bad UX" ([R3](goaljudge_evaluation_pipeline_open_axial_coding_rubric.md)).
- **IAA target.** When a second analyst (or second model) re-codes a sample, target **κ ≥ 0.8**
  (the MAST / 2603.06847 reliability bar). Definitions that score below are revised before any count
  is trusted. No κ has been computed yet (single-coder session) — this is part of the §7 gate.

---

## 3. Axis A — Agent-behavior failure taxonomy

The agent-behavior codes (the 19-code set minus the two J2/J3 judge codes, which live on Axis C —
**16 active** after retiring `tool-stub-limitation`; see the A3 note below)
cluster into **five** named categories. Each is defined, given its correct `goal_met` consequence, a
**binary testable check** (the Stage-4 rubric-criterion seed), its member codes, and its **provisional**
session count (primary-code tallies from the §6 matrix).

> **Step 4 finalization.** The one-line testable checks below are finalized — with explicit pass/fail
> poles, the observable evidence source, and the anti-gaming justification — in
> [`goaljudge_step4_axisA_testable_checks.md`](goaljudge_step4_axisA_testable_checks.md) (+ `.csv`).
> The wording here and there is identical in substance; that artifact is the expanded view the
> Stage-4 rubric author works from.

### A1 · Semantic / synthesis failures
*The agent did the work but the **final answer** does not deliver the requested information.*

| | |
|---|---|
| **Member codes** | `missing-requested-information`, `incomplete-synthesis`, `fluent-evasion`, `criteria-mismatch` |
| **Correct verdict** | `goal_met=False` (deliverable absent/garbled despite work done) |
| **Testable check** | "Does the final answer contain every datum the prompt explicitly requested, integrated (not a raw step dump or a polite deferral)?" |
| **Provisional count (primary)** | 3 (GJ-004B, GJ-005, GJ-002 secondary) |

### A2 · Decomposition & progress-accounting failures ("corrupt success")
*Part of a multi-part goal is missing or unverified, but the agent **frames it as complete**.*

| | |
|---|---|
| **Member codes** | `subtask-dropped`, `partial-counted-as-full`, `fabricated-progress` |
| **Correct verdict** | `goal_met=False`; `partial_fraction` recorded as metadata |
| **Testable check** | "Is every required subtask verified by observable tool evidence (not narration), AND does the final answer's success claim match that evidence?" |
| **Provisional count (primary)** | 5 (GJ-010, GJ-011, GJ-012, GJ-013, GJ-015) |

> **This is the "corrupt success" cluster** of *Beyond Task Completion: Revealing Corrupt Success in
> LLM Agents through Procedure-Aware Evaluation* ([arXiv 2603.03116](https://arxiv.org/abs/2603.03116)),
> which names `partial completion` and `fluent evasion` as procedure-violation types and frames the
> exact `outcome=success / goal_met=false` split the session repeatedly observed. It is the
> **strongest-aligned cluster in the session** (GJ-010/GJ-011 match `criteria_met≈0.67` to registry
> `partial_fraction`) and the leading **candidate top mode** (§6.3).

### A3 · Error & exception handling
*A tool error or missing resource is mishandled in the final answer.*

| | |
|---|---|
| **Member codes** | `raw-error-propagation`, `tool-error-misread`, `non-existent-file-error` ~~`tool-stub-limitation`~~ (**RETIRED** — see note) |
| **Correct verdict** | `goal_met=False` |
| **Testable check** | "On a tool error / empty result, does the final answer correctly interpret it (neither dumping a raw traceback nor reading failure as success)?" |
| **Provisional count (primary)** | 3 active (GJ-020 `non-existent-file-error`, GJ-021, GJ-003B); GJ-006B was `tool-stub-limitation` (now retired → re-code on post-SearXNG batch, §7) |

> **Retired member code.** `tool-stub-limitation` is **retired** from Axis A: with live web search (SearXNG) now replacing the batch web-search stub, the "failure" it named is a batch-environment artifact (Axis-B B5 `telemetry/environment-split`), not agent behavior. Step 2 Axis-A clusters already drop it from A3 (16 active codes). Its only primary case here, **GJ-006B**, is itself the canonical B5 illustration (live-search pass vs stub failure from one prompt) and must be **re-coded on the post-SearXNG batch re-run** (§7 Axis-B retirement gate) rather than counted as an Axis-A failure.

### A4 · Feasibility & gracefulness
*How the agent handles impossible or blocked tasks.*

| | |
|---|---|
| **Member codes** | `graceful-failure-honest`, `impossible-task-reported`, `impossible-task-unhandled`, `premature-impossible` |
| **Correct verdict** | impossible-correctly-reported ⟹ `goal_met=False`, `graceful_failure=True`; unhandled/premature ⟹ `goal_met=False`, `graceful_failure=False` |
| **Testable check** | "If the task is impossible/blocked, did the agent report the impossibility *after adequate exploration* and without looping or crashing?" |
| **Provisional count (primary)** | 2 (GJ-022 unhandled; GJ-019 graceful-honest) |

### A5 · Process quality (outcome ≠ process)
*The goal may be met, but the path is invalid, unsafe, or wasteful — a separate axis from correctness.*

| | |
|---|---|
| **Member codes** | `right-answer-wrong-process`, `goal-met-but-unsafe-wasteful` |
| **Correct verdict** | `goal_met` per evidence; process flagged in `failure_mode` |
| **Testable check** | "Is the answer supported by a valid, safe, non-wasteful trajectory (no lucky-guess hardcoding, no `rm -rf`, no 10k-step `find /`)?" |
| **Provisional count (primary)** | 1 (GJ-002 `right-answer-wrong-process` secondary; weak in session) |

**Coverage check (no orphans):** A1∪A2∪A3∪A4∪A5 = the **16 active** agent-behavior codes exactly
(the original 17 minus the retired `tool-stub-limitation`):
`missing-requested-information`, `incomplete-synthesis`, `fluent-evasion`, `criteria-mismatch` (A1);
`subtask-dropped`, `partial-counted-as-full`, `fabricated-progress` (A2); `raw-error-propagation`,
`tool-error-misread`, `non-existent-file-error` (A3 — `tool-stub-limitation` **retired**, see A3 note);
`graceful-failure-honest`, `impossible-task-reported`, `impossible-task-unhandled`, `premature-impossible` (A4);
`right-answer-wrong-process`, `goal-met-but-unsafe-wasteful` (A5). The two judge codes
(`criterion-conflation` J2, `outcome-bias-on-graceful-failure` J3) are on **Axis C**.

---

## 4. Axis B — Harness / environment confound axis *(the new contribution)*

These categories are **not agent failures**. They are sandbox/orchestrator behaviors that *block* or
*distort* the agent and therefore *contaminate* Axis-A evidence. The decision rule that separates
this axis from Axis A is: **"Could a perfectly-reasoning agent have succeeded in this environment?"**
If no — because the tool the prompt requires is allowlist-blocked, the path is outside the boundary,
or the orchestrator aborted on a non-fatal tool error — the case carries a **B** code and **must not
count toward Axis-A behavioral saturation** without an environment-corrected re-run.

| Code | Definition | Session cases | Contaminates |
|---|---|---|---|
| **B1 · shell-allowlist-block** | A command the prompt needs is not in the shell allowlist (`echo`, `printf`, `touch`, `exit`, `git`, `pytest`) → validation error. | GJ-002, GJ-004, GJ-005, GJ-009, GJ-011, GJ-013, GJ-014, GJ-019 | A1 (synthesis forced to prose), A2 (GJ-011/013 decomposition), A4 (false "graceful") |
| **B2 · shell-metachar-block** | Validator rejects shell metacharacters (`;`, `>`, `2>/dev/null`) → blocks `python -c` one-liners and `find` recovery. | GJ-002, GJ-007, GJ-011, GJ-013, GJ-021 | A2/A5 (forces prose fallback for computation) |
| **B3 · workspace-path/mount-mismatch** | Host-absolute registry path is outside the `/workspace` boundary; or `/workspace` ENOENT for **shell** while the `file_io` boundary *is* `/workspace`. | GJ-001A, GJ-003A, GJ-007, GJ-014 | A3 (read failures), A4 (premature-impossible look-alikes) |
| **B4 · tool-error-to-terminal-escalation** | Orchestrator `classify_outcome` escalates any tool output starting `"Error:"` lacking `"tool"` to a **terminal abort**, killing the run before the agent can recover. | GJ-001A, GJ-020, GJ-021 | A3 (no chance to interpret the error), A4 |
| **B5 · telemetry/environment-split** | UI random `workflow_id` ≠ registry deterministic `trace_id`; `user_id` = WorkOS not `synthetic-saturation-user`; live `web_search` (SearXNG) vs batch **stub**; **no** `goal_judge` EC rows. | GJ-006 (A vs B env divergence), GJ-015 + all UI cases | **All counts** (no registry join, no EC half of export) |

> **§4-vs-§6 reconciliation (2026-06-05).** The B1 and B4 case lists above were realigned to the §6
> per-case matrix (the single coding surface, agreeing with the remediation memo §5 per-case table):
> **B1** now includes **GJ-011 and GJ-013** (previously listed only under B2, though §6 codes them
> `B1, B2`) and so additionally contaminates **A2**; **B4** drops **GJ-014** (§6 codes it `B1, B3`,
> not B4) and retains GJ-001A. §6.2's B1 count is 6 → **8** and B4's `2–4` resolves to **3**. The
> per-case matrix remains authoritative; §4 and §6.2 are now derived views of it.

> **Why B5 matters most for saturation.** GJ-006 is the cleanest illustration: the **same prompt**
> produced `goal_met=true` (full pass) on GCP-UI with live search and an honest "no results" stub
> failure in local batch — *different failure modes from one prompt*, purely environment-driven. Any
> Axis-A count that mixes UI and batch runs is measuring the environment, not the agent.

This axis is the operational form of the agentic-fault taxonomy's **environment-infrastructure
dimension** ([2603.06847](https://arxiv.org/abs/2603.06847): "Runtime & Environment Grounding",
"Tooling, Integration & Actuation"). B4 specifically is a **System Reliability & Observability** fault
— the orchestrator's own error-classification logic, not the agent.

---

## 5. Axis C — Judge-reliability axis

These are the two **judge-quality** codes (J2/J3) plus the observed Langfuse drift. They are defects
in the *evaluator*, and they feed **Stage 6 judge calibration / red-team**, not the Stage-4 agent
rubric.

| Code | Definition | Session cases |
|---|---|---|
| **C1 · criterion-conflation (J2)** | Judge marks one criterion true/false based on another / shows logical contradiction across `per_criterion`. Surfaces as `lf-goal-met-drift`: judge says `goal_met=true` where the agent's evidence (and registry target) says false. | GJ-008, GJ-012, GJ-013, GJ-015 |
| **C2 · outcome-bias-on-graceful-failure (J3)** | Judge penalizes a clean graceful failure on quality/consistency criteria *solely* because the goal was unmet; or, conversely, over-credits partial work. Surfaces as `lf-criteria-drift`. | GJ-022 (`criteria_met=0.5` vs target `0.0`); watch GJ-019 (graceful-honest) |

C1/C2 map to MAST's **"task verification" / verification-gap** root category
([2503.13657](https://arxiv.org/abs/2503.13657)). They are confirmable only against the judge's real
`per_criterion` output — which on GCP-UI requires the **E1** `eval.goal_judge` export (no such rows
exist in this session; §7).

---

## 6. Per-case axial matrix (GJ-001–GJ-022)

Coded directly from the [session report](../reports/goaljudge_manual_walkthrough_gj001_gj022_session_report.md)
per-case sections and §5.3. **Axis-A primary** is the first-failure agent code; **(sec)** are
secondary agent codes; **Axis-B / Axis-C** list confound/judge codes present. "**Counts A?**" carries
the §5.3 saturation-eligibility verdict — whether this run may count toward **Axis-A** behavioral
saturation (almost never, because of Axis-B contamination).

> **Step 5 standalone matrix.** This matrix is reproduced — with a per-row **first-failure-event
> evidence column** (citing the session-report §4 subsection) and a ≥5-case human-verification table —
> in [`goaljudge_step5_axial_matrix.md`](goaljudge_step5_axial_matrix.md) (+ `.csv`). The two are
> identical in coding; that artifact is the evidence-annotated view the Step 6 frequency count is
> computed from.

**Coverage reconciliation with Step 0.** Step 0's environment table is a source-faithful **run-level**
extraction with 23 rows. This §6 matrix is an **axial-coding adjudication surface** with 21 rows: it
keeps both A/B trajectories only where they represent meaningfully distinct coding outcomes (e.g.,
GJ-001 and GJ-006), and collapses duplicate exploratory variants where one run is analytically
subsumed by its paired run (GJ-003A subsumed by GJ-003B; GJ-004A subsumed by GJ-004B).

| Case | Run | Axis-A primary | Axis-A (sec) | Axis-B | Axis-C | LF `goal_met` vs target | Counts A? |
|---|---|---|---|---|---|---|---|
| GJ-001 | A | `raw-error-propagation` | — | B3, B4 | — | false ✓ | No (env) |
| GJ-001 | B | *(correct-complete — target miss)* | — | — | — | true ✗ | No (positive control) |
| GJ-002 | — | `incomplete-synthesis` | `right-answer-wrong-process` | B1, B2 | — | false ✓ | Partial (LF only) |
| GJ-003 | B | `missing-requested-information` | `subtask-dropped` | B3 | — | false ✓ | Partial (behavior) |
| GJ-004 | B | `incomplete-synthesis` | — | B1 | — | false ✓ | Partial (Run B) |
| GJ-005 | — | `incomplete-synthesis` | `fluent-evasion` | B1 | — | false ✓ | Partial (strong) |
| GJ-006 | A | *(correct-complete — target miss)* | `criteria-mismatch` | B5 | — | **true ✗** | **No** (prompt/corpus mismatch) |
| GJ-006 | B | ~~`tool-stub-limitation`~~ → **B5 (retired)** | `graceful-failure-honest` | B5 | — | n/a (batch) | **No** (stub artifact; re-code post-SearXNG, §7) |
| GJ-007 | A | `impossible-task-unhandled`† | — | B2, B3 | — | false ✓ | Partial (env dominates) |
| GJ-008 | — | `fabricated-progress` | `fluent-evasion` | — | C1 | **true ✗** | Partial (LF contradicts) |
| GJ-009 | — | `fluent-evasion`† | — | B1 | — | false ✓ | Partial (env-shaped) |
| GJ-010 | — | `partial-counted-as-full` | — | — | — | false ✓ (`0.67`) | **Partial — strongest** |
| GJ-011 | — | `partial-counted-as-full` | `right-answer-wrong-process` | B1, B2 | — | false ✓ (`0.67`) | **Partial — strongest** |
| GJ-012 | — | `partial-counted-as-full` | — | — | C1 | **true ✗** | Partial (LF contradicts) |
| GJ-013 | — | `subtask-dropped` | `partial-counted-as-full` | B1, B2 | C1 | **true ✗** | Partial (LF contradicts) |
| GJ-014 | — | `subtask-dropped` | — | B1, B3 | — | false ✓ | Partial (blocks ⇒ 0.0) |
| GJ-015 | — | *(correct-complete — env)* | `goal-met-but-unsafe-wasteful` | B5 | C1 | **true ✗** | No (live search) |
| GJ-019 | — | `graceful-failure-honest` | `impossible-task-reported` | B1 | (C2 watch) | false ✓ | Partial |
| GJ-020 | — | `non-existent-file-error` | `impossible-task-unhandled` | B4 | — | false ✓ | **Aligned** |
| GJ-021 | — | `impossible-task-unhandled` | — | B2, B4 | — | false ✓ | **Aligned** |
| GJ-022 | — | `impossible-task-unhandled` | — | — | C2 | false ✓ | **Aligned** |

† *First-failure note:* GJ-007/GJ-009's **primary** observable is an Axis-B block (B2/B3, B1), with the
Axis-A target code (`fluent-evasion`) never cleanly exercised — the environment pre-empted the agent
behavior the case was designed to elicit. These are coded to the *intended* Axis-A target with the
Axis-B confound flagged, per the session report's "target mismatch retained as evidence" rule.

`correct-complete` is the non-failure baseline (codebook §2 note), shown in *italics* where the run
landed there against a failure target — a **target miss**, not an Axis-A failure code.

### 6.1 Provisional Axis-A frequency (primary codes only)

Tallied from the **Axis-A primary** column of the §6 matrix. `correct-complete` runs (GJ-001B,
GJ-006A, GJ-015) are **target misses**, not Axis-A codes, and are excluded from the failure tally.
Because §6 is the 21-row adjudication surface (not Step 0's 23-row extraction), denominators below
use 21.

> **Step 6 standalone tables.** The full Step 6 frequency + confound-contamination tables (Axis-A
> primary tally with `clean`/contaminated split, Axis-B frequency, ≥1-Axis-B breadth, and the
> Axis-A↔Axis-B co-occurrence matrix), all recomputed from the Step 5 matrix, live in
> [`goaljudge_step6_frequency_contamination.md`](goaljudge_step6_frequency_contamination.md) (+ `.csv`).
> **G6 + G9 applied (2026-06-07):** §6.1/§6.3 match the Step 5 matrix with GJ-003B recoded to
> **A2 `subtask-dropped`** per the G9 conditional-prompt tie-breaker (else-branch never attempted).

| Axis-A category | Primary count | Cases (primary) |
|---|---|---|
| A2 Decomposition / corrupt-success | **7** | GJ-003B, GJ-008 (`fabricated-progress`); GJ-010, GJ-011, GJ-012 (`partial-counted-as-full`); GJ-013, GJ-014 (`subtask-dropped`) |
| A4 Feasibility & gracefulness | 4 | GJ-007†, GJ-019, GJ-021, GJ-022 |
| A1 Semantic / synthesis | **4** | GJ-002, GJ-004B, GJ-005, GJ-009† (`fluent-evasion`) |
| A3 Error & exception handling | 2 active (was 3) | GJ-001A (`raw-error-propagation`), GJ-020 (`non-existent-file-error`); ~~GJ-006B (`tool-stub-limitation`)~~ **retired → B5** |
| A5 Process quality | 0 primary / 2 secondary | GJ-011, GJ-002 (`right-answer-wrong-process`, sec) |

> **Every count above is provisional and confound-contaminated.** 16 of 21 rows carry ≥1 Axis-B
> code and 5 carry an Axis-C drift, so these tallies indicate *where to look*, not saturation. A2
> leads on **both** volume (7) and the cleanest target alignment (GJ-010/GJ-011), which is why it is
> the §6.3 candidate top mode. The `†` cases (GJ-007/GJ-009) are coded to their *intended* target but
> were pre-empted by an Axis-B block, so they are the weakest evidence in their category.

### 6.2 Axis-B confound frequency (the contamination map)

| Confound | Count | Share of cases |
|---|---|---|
| B1 shell-allowlist-block | 8 | GJ-002/004/005/009/011/013/014/019 |
| B5 telemetry/env-split | ~all UI | GJ-006/015 + every UI run |
| B2 shell-metachar-block | 5 | GJ-002/007/011/013/021 |
| B3 workspace-path/mount | 4 | GJ-001A/003A/007/014 |
| B4 tool-error-to-terminal | 3 | GJ-001A/020/021 |

**Reading:** the modal session "failure" is *the sandbox blocking a command the prompt required*, not
the agent reasoning poorly. This is the single most important Stage-3 finding for Stage 4.

### 6.3 Candidate top mode (gated)

Per the playbook ("build one judge for your biggest issue first"), the leading candidate is **A2 ·
Decomposition & progress-accounting / corrupt-success** — it has the most primary cases (**6**, per
the Step 6 recompute and the G6 §6.1 reconciliation), the **cleanest target
alignment** (GJ-010/GJ-011: LF `goal_met=false` + `criteria_met≈0.67` ≈ registry `partial_fraction`),
and direct external grounding ([2603.03116](https://arxiv.org/abs/2603.03116)). A2 also owns **3 of
the only 4 Axis-B-clean failure primaries** (GJ-008/010/012), so it is the strongest *behavioral*
signal, not merely the largest. **This pick is gated**: it must be reconfirmed on the registry-prompt
batch re-run before any Stage-4 rubric work begins (§7).

> **Step 8 standalone artifact.** The top-mode decision (A2, with A1/A3/A4/A5 scored and rejected on
> the biggest-and-cleanest rule) and the full Stage-4 **gate checklist** — validity gates G1–G5
> (mirroring §7.1–§7.5) plus consistency gates G6–G9 (the §6.1/§6.3 count reconciliation and the three
> Step 7 definition revisions), each with status, owner, and dependency order — are consolidated in
> [`goaljudge_step8_topmode_gating.md`](goaljudge_step8_topmode_gating.md) (+ `.csv`). That artifact
> states the Stage-4 *entry criteria* (reconfirm-on-re-run + human κ ≥ 0.8 + count reconciliation).

---

## 7. Saturation & validity gate (why this is PROVISIONAL)

The session report is explicit that its evidence is **not** saturation sign-off. Stage 3 inherits
those gaps; all of the following must clear before counts freeze and Stage 4 begins:

1. **Registry join.** UI runs used random `workflow_id`s (Axis-B5). Re-run GJ-001–GJ-022 with the
   deterministic `trace_id`s (session report §2) and `user_id=synthetic-saturation-user` via
   `scripts/run_goaljudge_synthetic_batch.py`.
2. **`eval.goal_judge` rows.** `logs/evals.log` has **zero** `target=goal_judge` rows for these runs;
   the full GoalJudge axes (`graceful_failure`, `partial_fraction`, `per_criterion`) and **Axis C**
   confirmation depend on requirement **E1** (export `eval_capture` → Langfuse `eval.{target}`).
3. **Environment correction (Axis-B retirement).** Re-run with `/workspace`-aligned paths, shell
   allowlist documented/widened or prompts adapted, and the `classify_outcome` B4 escalation
   reviewed — so a case's Axis-A code reflects the agent, not the sandbox. Sequencing, trade-offs,
   and per-case adjudication: [`goaljudge_axis_b_remediation_strategy.md`](goaljudge_axis_b_remediation_strategy.md).
4. **GCS posture confirmed.** `curl $BACKEND_URL/healthz | jq .goal_judge` shows a file-backed
   `gs://…/ops/goal_judge_config.json` source before crediting any `goal_met`.
5. **IAA pass.** Second-coder re-code of a ≥10-case sample; **κ ≥ 0.8** on Axis-A before counts are
   trusted; revise definitions otherwise. Two provisional model passes have been run:
   - *Single model-as-second-coder* ([`goaljudge_step7_iaa_kappa.md`](goaljudge_step7_iaa_kappa.md) +
     `.csv`): κ = 0.77 over 12 cases (below bar), 0.86 excluding the two `†` cases — but only
     *partially* blind (the one coder had seen the matrix in-session).
   - *Five-model blind panel* ([`goaljudge_step7_iaa_multimodel.md`](goaljudge_step7_iaa_multimodel.md)
     + `.csv`): five models re-coded from a **code-free** packet (no matrix access). **Fleiss' κ =
     0.50** (0.51 with the matrix as a 6th rater); only **grok-4.3** reproduced the matrix closely
     (κ = 0.77), the other four cluster at κ ≈ 0.46. **The single-model 0.77 was optimistic; genuine
     blind reliability is ≈0.50 (moderate).** Four cases are unanimous (GJ-005, GJ-007, GJ-008,
     GJ-009 — notably GJ-007/GJ-009 are now *agreed*); eight disagree along **three** systematic
     seams: (a) **A2 vs A5** "blocked-tool → prose computation → claimed done" (GJ-002/GJ-011/GJ-013,
     new), (b) the **`†` no-final-answer mapping** for terminally-aborted cases (GJ-001A/GJ-019/GJ-020),
     and (c) the **A1/A2/A3 conditional-prompt boundary** (GJ-003B). Three definition revisions are
     proposed there. A real **human** IAA pass on the revised definitions remains **OPEN**; both model
     passes are weaker evidence.

Until 1–5 clear, the taxonomy *structure* (§3–§5) is usable for Stage-4 *design*, but the *counts*
(§6) and the *top-mode pick* (§6.3) stay provisional.

> **Step 8 consolidated gate.** These five validity gates are restated as **G1–G5** — alongside four
> **consistency gates G6–G9** (the §6.1/§6.3 count reconciliation and the three Step 7 definition
> revisions: A2/A5 prose-after-block, the `†` no-final-answer mapping, the A1/A2/A3 conditional-prompt
> tie-breaker) — in [`goaljudge_step8_topmode_gating.md`](goaljudge_step8_topmode_gating.md) (+ `.csv`),
> with owners and dependency order. Key sequencing note: the cheap doc fixes (G6–G9) should land
> **first**, and the **human** IAA (G5) should run on the *revised* definitions so κ measures the
> taxonomy we intend to ship.

---

## 8. Bridge to Stage 4 (rubric design)

| Axis | Stage-4 / downstream role |
|---|---|
| **A — behavioral categories** | Each becomes **one analytic rubric criterion** (the testable check in §3) **and** one gold-set `failure_mode` enum value + Langfuse categorical score config. A2 first. |
| **B — confounds** | Becomes a **trace-validity precondition / exclusion filter**: a case with an un-corrected Axis-B code is *not eligible* for the gold set's behavioral strata. Also a backlog of environment fixes (session report §3.4). |
| **C — judge reliability** | Becomes a **Stage-6 calibration target**: C1/C2 are exactly the `goal_met` drift the §2.8 κ-gate and CoT-gaming red-team must catch. |

Per the playbook's repo-mapping, the rubric lands in `prompts/goal_judge_system_prompt.j2` via
`PromptService.render_prompt()`; categories become Langfuse score configs; the gold set is an offline
Langfuse dataset. Borrow vetted vocabulary from MAST (verification gap) and 2603.06847
(env/cognition split) rather than re-inventing.

The hands-on procedure for *running* this stage (human analyst + agentic assistant) is
[walkthrough 05](../walk-through/05_goaljudge_axial_coding_failure_taxonomy_walkthrough.md).

> **Stage 4 v1 spec (2026-06-08):** [`goaljudge_stage4_a2_rubric_spec.md`](goaljudge_stage4_a2_rubric_spec.md)
> — A2 corrupt-success criterion, matrix↔registry crosswalk, anchor cases, and confirmation gates.
> Implementation plan: [`goaljudge_stage4_a2_rubric.plan.md`](../plans/goaljudge_stage4_a2_rubric.plan.md).
> Intern-facing walkthrough of the build: [`02_stage4_a2_rubric.md`](../recipes/goaljudge/02_stage4_a2_rubric.md)
> — how the A2 check became prompt rules, the crosswalk/GJ-008 (G10) reconciliation, and the
> two-gate (Code §8.2 vs Confirmation §8.3) ship-PROVISIONAL discipline.

> **Stage 5 v1 plan + spec (2026-06-08):** [`goaljudge_stage5_goldset.plan.md`](../plans/goaljudge_stage5_goldset.plan.md)
> + [`goaljudge_stage5_goldset_spec.md`](goaljudge_stage5_goldset_spec.md) — the golden dataset that turns
> each Axis-A category (this §8 table's first row) into a gold-set stratum + `failure_mode` label, with
> the double-labeling **α ≥ 0.8** gate. The `failure_mode` axis landed on `GoalVerdict` (telemetry-only).
> **Gated on Stage 4 Confirmation.** Stage 6 (the Axis-C calibration target in this §8 table's third row)
> follows.

---

## 9. References

### External (2025–2026)

| # | Title | URL | Used for |
|---|---|---|---|
| X1 | Characterizing Faults in Agentic AI: A Taxonomy of Types, Symptoms, and Root Causes | https://arxiv.org/abs/2603.06847 | Multi-axis structure; **env-infra vs agent-cognition partition**; grounded theory + κ 0.83–0.86; per-fault `Category=X, Symptom=Y, Root Cause=Z` encoding |
| X2 | Beyond Task Completion: Revealing Corrupt Success in LLM Agents through Procedure-Aware Evaluation | https://arxiv.org/abs/2603.03116 | "Corrupt success"; `partial completion` + `fluent evasion` procedure-violation types; outcome-vs-procedure judging → anchors A2 |
| X3 | Where LLM Agents Fail and How They Can Learn From Failures (AgentErrorTaxonomy / AgentErrorBench) | https://arxiv.org/abs/2509.25370 | memory/reflection/planning/action/system categories; **error propagation / cascades** → first-failure discipline, B4 cascade |
| X4 | Why Do Multi-Agent LLM Systems Fail? (MAST) | https://arxiv.org/abs/2503.13657 | 14 modes → 3 root categories; grounded theory; **κ = 0.88 IAA target**; "verification gap" → Axis C |

### In-repo foundations

- [Dimension space & 19-code codebook](goaljudge_synthetic_dimension_space.md)
- [Phase 2b open coding & saturation log](goaljudge_phase2b_open_coding.md)
- [GJ-001–GJ-022 session report](../reports/goaljudge_manual_walkthrough_gj001_gj022_session_report.md)
- [Pipeline playbook (Stage 3 method + R1–R20)](goaljudge_evaluation_pipeline_open_axial_coding_rubric.md)
- [GCP compatibility plan (E1 / GCS posture)](../plans/goaljudge_gcp_compatibility.plan.md)
- [Walkthrough 05 — running this stage](../walk-through/05_goaljudge_axial_coding_failure_taxonomy_walkthrough.md)
- [Axis-B remediation strategy (critical evaluation)](goaljudge_axis_b_remediation_strategy.md)
