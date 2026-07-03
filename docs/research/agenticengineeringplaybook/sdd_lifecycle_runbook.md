# SDD Lifecycle Runbook — Spec-Driven Development for This Repo

> **What this is:** An executable, repo-specific runbook for running a spec-driven
> change end-to-end. It operationalizes Phase 6.1 of the v2 harness-adoption plan
> ([`harness_adoption_critical_review_and_v2_plan.md`](./harness_adoption_critical_review_and_v2_plan.md))
> by grounding the operator's lifecycle
> (`brainstorm → plan → task → design → replan → implementation → review → test → fixes → refine`)
> in the 2026 SDD + GitHub Spec Kit research and in this repo's actual harness.
>
> **Date:** 2026-06-28
> **Scope:** Production-grade, durable changes to this repo. Trivial/throwaway
> work is out of scope (see §6). No repo code is changed by this document; it is
> a process artifact.
> **Companion artifacts:** the v2 plan (gaps + phased improvement plan), the
> [`_spec_template.md`](../../plan/_spec_template.md) (landed Wave 0, 2026-06-28),
> and the existing `AGENTS.md` Architecture Invariants + ADR OKF bundle.

> ### ⚠️ Adoption status — read before running this
>
> **The `/speckit.*` command spine is aspirational, pending the v2 plan's 6.1b
> Spec Kit trial (rated DEFER).** Spec Kit is **not installed** in this repo
> (`.specify/` does not exist; the `sdd-brainstorm` / `review-local-changes` /
> `spec-kit-loop` skills are external references, not local skills). Treat every
> `/speckit.…` reference below as *the shape of the stage*, not a runnable command.
>
> **What is runnable today** (the executable subset, all verified on disk):
> `make check` (lint + format-check + pyright + test) · `tests/architecture/`
> (14 files / 106 functions) · the 4 hook scripts (`pre_bash_guard.py`,
> `post_edit_ruff.py`, `cursor_after_edit.py`, `cursor_before_shell.py`) ·
> pre-commit + CI · `make model-ab` + `python -m meta.judge_validation` · the
> repo skills (`agentsframework-eval-probe`, `governance-trace-audit`,
> `security-review`, `code-review`). The `_spec_template.md` (6.1a) and
> `decisions.md` (6.3) **are** landed (Wave 0). The constitution is `AGENTS.md`
> + `tests/architecture/` (§2) — that is real and enforced now.
>
> So: the **methodology** (the ten-stage human↔agent loop, EARS specs, the
> constitution check, the converge mechanics) is usable today against the
> runnable subset; the **Spec Kit tooling** that automates it is gated behind the
> 6.1b trial decision. Adoption-status detail: see
> [`harness_adoption_v2_practical_adoption.plan.md`](../../plan/harness_adoption_v2_practical_adoption.plan.md).

---

## 0. The shaping principle — every stage is a human↔agent micro-loop

This runbook is **not** "hand the agent a spec and let it run." Every one of the
ten stages is a **human↔agent micro-loop** with a fixed role split:

| Role | Who | What they do |
|---|---|---|
| **Initiate** | Human | Poses the idea / the artifact to react to / the rejection feedback |
| **Do the work** | Agent | Expands, drafts, validates, checks, proposes alternatives |
| **Gatekeep** | Human | Validates, accepts / rejects, nudges direction |
| **Re-enter or advance** | Both | Loop back if the gate fails; advance if it passes |

The agent is the **workhorse**; the human is the **initiator + gatekeeper +
steerer**. The crux from the operator: *agent does most of the work, human
initiates, validates, accepts/rejects, and nudges the workflow.*

Concrete example (the brainstorm stage, which sets the pattern for all ten):
human proposes an idea → agent expands it and generates candidate approaches →
human/agent propose hypotheses for the idea → agent validates or rejects each
hypothesis against repo evidence → human accepts a direction or nudges. That
same initiate→do→gate→(re-enter|advance) shape repeats at every stage below.

---

## 1. The lifecycle map

The operator's 10-stage lifecycle mapped to (a) the Spec Kit v0.11.9
high-assurance command spine, (b) the 2026 research that fills the stages Spec
Kit leaves open, and (c) where the loop re-enters.

```
                     ┌──────────────────────── the converge loop ────────────────────────┐
                     │                                                                  ▓
  1 brainstorm       │  2 plan        3 task      4 design    5 replan/                 ▓
  (Phase 0 ideate)   →  (specify+     (checklist  (analyze    sprint      6 implementation
                        clarify+      +tasks)     +design     board
                        plan)                     artifacts) validation)
                                                                            ↓
                                                                      7 review
                                                                            ↓
                                                                      8 test
                                                                            ↓
                                                                      9 issue fixes
                                                                            ↓
                                                                 10 refine: acceptable?
                                                                            │
                                                              ┌─────────────┴─────────────┐
                                                              ▓ no                        yes → production
                                                              ▓                            ▓
                                                              ▓ re-enter:                  ▓
                                                              ▓  converge appends          ▓
                                                              ▓  Phase N tasks → 6 impl    ▓
                                                              └─────────────────────────────┘
```

| # | Stage | Spec Kit command(s) | Research backing | Re-enters self when |
|---|---|---|---|---|
| 1 | **brainstorm** | `/speckit.brainstorm` (Nexo Phase 0), `/speckit.ideate`→`/select`→`/structure`→`/validate`; constitution is the backdrop | Nexo Spec Kit Phase 0; `sdd-brainstorm` skill (6-solution generation); ASDLC Agent Constitution pattern | Human rejects all directions / hypotheses don't validate |
| 2 | **plan** | `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` (+ `data-model.md`, `contracts/`, `research.md`) | BCMS/DEV/Allegro 2026 SDD guides; Spec Kit Agents discovery hooks | Clarify surfaces new ambiguity; plan violates constitution |
| 3 | **task** | `/speckit.checklist` → `/speckit.tasks` | Spec Kit "unit tests for English"; Microsoft SDD lifecycle | Checklist flags unmeasurable criteria; task order infeasible |
| 4 | **design** | `/speckit.analyze` (cross-artifact: spec↔plan↔tasks↔constitution) | Spec Kit Agents validation hooks (front-load error detection) | Analyze reports CRITICAL violations / zero-coverage requirements |
| 5 | **replan / sprint board** | **No native Spec Kit command** — this is the deliberate gap | `spec-kit-loop` externalized state; operator's sprint-board practice | Blocked tasks, reprioritization, mid-flight scope change |
| 6 | **implementation** | `/speckit.implement` | Spec Kit Agents discovery+validation hooks per-task; `spec-kit-loop` maker/checker | Task fails its verification criteria |
| 7 | **review** | `review-local-changes` skill (6 parallel review agents); repo `code-reviewer` + `security-review` subagents; Bugbot | 2026 multi-agent review pattern; fresh-thread self-review (playbook Runbook #2 §6) | Reviewer finds load-bearing issues |
| 8 | **test** | (none — this is repo-internal) | `make check` + `tests/architecture/` + (proposed) mutation testing on `trust/` | Any gate fails red |
| 9 | **issue fixes / improvements** | `/speckit.converge` gap classification (`missing`/`partial`/`contradicts`/`unrequested`) | Spec Kit converge append-only semantics; `spec-kit-loop` adversarial checker | Gaps classified; fixes spawned as Phase N tasks |
| 10 | **refine: acceptable?** | `/speckit.converge` (did it converge?) + sign-off gate | `spec-kit-loop` human sign-off; comprehension gates G1/G4/G8 + ADR | Not converged → re-enter at 6; converged + signed → production |

---

## 2. The repo already has a constitution — use it as the projection

The single most load-bearing idea in the 2026 SDD research is the
**constitution**: non-negotiable principles that the planner is checked against,
so principles become *enforced* rather than *aspirational*. Spec Kit stores it as
`.specify/memory/constitution.md` and `/speckit.plan` checks the plan against it.

**This repo already has a stronger, hand-curated constitution than a fresh
Spec Kit install would produce.** It lives in three places:

1. **`AGENTS.md` → Architecture Invariants** (the 8 invariants: dependencies
   flow downward, trust kernel has zero outward deps, components/services are
   framework-agnostic, no peer imports, orchestration nodes are thin, services
   don't import components, meta doesn't import orchestration).
2. **`AGENTS.md` → Boundaries** (✅ Always / ⚠️ Ask first / 🚫 Never) — the
   ADR triggers and the hard prohibitions.
3. **`tests/architecture/`** (14 test files / 106 test functions) — the
   *mechanical* enforcement of the invariants. This is what most SDD projects
   lack: the constitution as executable tests, not just prose.

**Runbook rule:** if/when the Spec Kit CLI trial (v2 plan 6.1b) is adopted, the
`.specify/memory/constitution.md` must be **generated from** these three
sources, not rewritten from scratch. The constitution is a *projection* of the
repo's invariants into Spec Kit's format, not a new source of truth. Until the
trial decides, the constitution is `AGENTS.md` + `tests/architecture/`, and the
"constitution check" at stages 2 and 4 is `make check` + an architecture-test
run + a manual invariant review.

---

## 3. The runbook — stage by stage

Each stage follows the same 5-part structure:

> **Initiation** · **Agent work** · **Human gate** · **Loop-back condition** · **Harness instrumentation**

"Harness instrumentation" lists what fires *today* (existing hooks/gates) and
what fires *once the v2 plan lands* (marked **[v2-Pn]**). This keeps the runbook
honest about what is enforced now vs. promised.

### Stage 1 — Brainstorm  *(Phase 0 ideation)*

**Initiation (human):** Pose the idea as a one-paragraph problem statement.
State the *problem*, not the solution. Optionally pin constraints up front
("must not touch `trust/`", "must keep `make check` green", "is throwaway" →
see §6).

**Agent work:**
- Read the relevant subtree's nested `AGENTS.md` (the on-demand folder guide).
- **Audit the human-supplied framing's load-bearing premises against repo
  evidence *before* generating directions.** Publish a premise-status table:
  `verified` / `refuted` / `unverifiable`. A `refuted` premise is re-posed
  with corrected facts in the same document (directions are then generated
  over the *corrected* space — never silently atop the stale framing); an
  `unverifiable` premise marks its dependent directions `needs-probe`.
- Expand the idea: generate candidate approaches. Use the `sdd-brainstorm`
  pattern — produce **~6 directions**: 3 high-probability (follow existing
  patterns in this repo) + 3 exploratory (different abstractions / integrations
  / architectural shifts). For each: tradeoffs, what-breaks-if-chosen, which
  invariant it stresses; measurement proposals name confounds + the
  clean-toggle requirement, signal-consuming proposals characterize the signal
  on coverage × quality, and data-dependent directions probe the quantity
  first and carry `gated-on-data: <measured-count>` (or `needs-probe`).
- Propose **hypotheses** for the chosen direction: "this works *because* X";
  "this is safe *because* Y".
- **Validate / reject each hypothesis against repo evidence** — this is the
  key step. The agent must ground each hypothesis in actual files (glob/grep),
  not parametric memory. Hallucinated APIs and non-existent file paths are the
  named failure mode (Spec Kit Agents, "context blindness"); reject any
  hypothesis that references something the repo doesn't contain.

**Human gate:** Accept one direction, reject all and re-pose, or nudge. The
accept criterion is *direction-level*, not spec-level — you're choosing *what
to specify next*, not yet specifying it. Multi-option prompts label options
with explicit ids; a bare "yes" is not valid multi-option consent.

**Loop-back:** Re-enter brainstorm if (a) every direction violates an
invariant, (b) the hypotheses don't validate against repo evidence, (c) a
load-bearing premise is `refuted` and the corrected framing has not been
re-posed, or (d) the human rejects the framing. Advance to Stage 2 with a
chosen direction + the validated hypotheses.

**Harness instrumentation:**
- **Today:** nested `AGENTS.md` subtree guide (read on demand); `AGENTS.md`
  Architecture Invariants as the constitution backdrop; `tests/architecture/`
  as the ground truth for what's actually enforceable.
- **[v2-P5]:** `explore` subagent (read-only: Read/Grep/Glob) as the
  context-firewall for the repo-evidence gathering — only the summary returns
  to the root context, so brainstorm doesn't pollute the working context with
  raw grep noise.

---

### Stage 2 — Plan  *(specify + clarify + plan)*

**Initiation (human):** Hand the agent the chosen direction + validated
hypotheses from Stage 1. Pin the tech-stack constraints that aren't already in
the constitution (rare — most are already in `AGENTS.md`).

**Agent work:**
- **Specify:** draft `spec.md` — user stories + acceptance criteria in **EARS**
  notation. EARS is the de facto 2026 standard because each pattern collapses
  to a single testable claim an agent can implement and verify without
  guessing. The five patterns:
  - *Ubiquitous:* `The system shall …`
  - *Event-driven:* `WHEN [trigger] THE system SHALL [response]`
  - *State-driven:* `WHILE [state] THE system SHALL [behavior]`
  - *Unwanted:* `IF [condition] THEN THE system SHALL [response]`
  - *Optional:* `WHERE [feature is included] THE system SHALL [behavior]`
- **Clarify:** run a structured ambiguity pass *before* planning. Scan the spec
  against a taxonomy (functional scope, data model, edge cases, NFRs) and ask
  up to 5 targeted questions, one at a time, with recommended answers. Do
  **not** treat the first spec draft as final — this is the cheapest rework
  multiplier in the whole lifecycle.
- **Plan:** derive `plan.md` (architecture, file-level touchpoints, migration
  steps, data model, contracts) from the clarified spec **and** the
  constitution. The plan must respect all 8 Architecture Invariants; if it
  can't, that's an ADR trigger (see Stage 4 / §5).

**Human gate:** Review the spec before the plan is generated; review the plan
before tasks are generated. **Golden rule (2026 consensus): never skip from
spec to code.** The two review points are: spec → (gate) → plan → (gate) →
tasks.

**Loop-back:** Re-enter specify if clarify surfaces new ambiguity that changes
scope. Re-enter plan if the plan violates a constitution invariant (→ either
redesign, or raise an ADR and redesign around it). Advance to Stage 3 with a
spec + plan that pass the constitution check.

**Harness instrumentation:**
- **Today:** `AGENTS.md` ⚠️ Ask-first list (new dep, trust-kernel type change,
  new graph node, new horizontal service, new abstraction) — these are the
  plan-level ADR triggers; the human gate must catch them here.
- **Today:** `tests/architecture/` as the executable constitution — run the
  relevant architecture test mentally against the plan; if the plan would
  break one, stop.
- **[v2-P6.1b]:** if Spec Kit adopted, `/speckit.plan` mechanically checks the
  plan against `.specify/memory/constitution.md`; the constitution is the
  projection from `AGENTS.md` invariants (§2).
- **[v2-P2]:** `Stop`-hook ADR trigger — if the plan touches an ADR seam
  (`trust/models.py`, new orchestration node, new service, new abstraction)
  and no ADR file appears under `docs/adr/`, the hook blocks the turn.

---

### Stage 3 — Task  *(checklist + tasks)*

**Initiation (human):** Hand the agent the approved plan.

**Agent work:**
- **Checklist:** generate a quality checklist that validates the *requirements
  themselves* (not whether the code works) — "unit tests for English." Items
  like: "Is 'fast loading' quantified with a threshold?" "Is every EARS
  criterion measurable?" Flag any unmeasurable criterion back to Stage 2.
- **Tasks:** decompose the plan into atomic, independently-verifiable tasks in
  `tasks.md`. Each task gets: file-level specificity (which files to create /
  modify, in what order), dependency markers, parallelization markers, and
  **explicit pass/fail verification criteria** that the implementation stage
  can check automatically. The criteria map 1:1 from the EARS acceptance
  criteria in the spec.

**Human gate:** Review the task list before implementation. Check: does every
spec acceptance criterion have a task that delivers it? Is the task order
feasible? Are the verification criteria actually checkable (not "looks right")?

**Loop-back:** Re-enter checklist→specify if criteria are unmeasurable (the
spec is under-specified). Re-enter tasks if ordering is infeasible or a
criterion has no owning task. Advance to Stage 4 with a task list that covers
every acceptance criterion.

**Harness instrumentation:**
- **Today:** none mechanical at this stage — the gate is human review.
- **[v2-P6.1b]:** `/speckit.analyze` (run in Stage 4) catches coverage gaps
  between spec ↔ plan ↔ tasks mechanically.

---

### Stage 4 — Design  *(analyze + design-artifact validation)*

> **Note on naming:** the user's "design" stage is broader than a single
> artifact. The *design content* (data model, contracts, architecture) is
> produced during Stage 2's plan. This stage is the **design-consistency gate**
> — the checkpoint where the design is validated against the spec, the
> constitution, and the repo as it actually exists, *before* code is written.
> This is where Spec Kit Agents' core finding lives: front-load error
> detection so hallucinated paths / missing deps / infeasible plans are caught
> before code generation compounds them.

**Initiation (human):** Hand the agent the spec + plan + tasks triple.

**Agent work:**
- **Analyze (cross-artifact):** read-only check across `spec.md` ↔ `plan.md` ↔
  `tasks.md` ↔ constitution. Classify findings by severity
  (CRITICAL → HIGH → MEDIUM → LOW). CRITICAL = constitution MUST violations,
  zero-coverage requirements, references to non-existent files/APIs.
- **Grounding pass (Spec Kit Agents discovery pattern):** for every file path
  and API the plan references, probe the repo and confirm it exists. For every
  dependency the plan introduces, confirm it's in `pyproject.toml` or flag it
  as an ADR trigger. This is the explicit "context blindness" defense.
- **Constitution check:** run the plan against the 8 Architecture Invariants +
  the ⚠️ Ask-first list. Any hit → either redesign, or raise an ADR.

**Human gate:** Resolve all CRITICAL findings before proceeding. The human
signs off that the design is grounded in the actual repo, not a hallucinated
one. **This is the last cheap correction point** — after this, mistakes
compound in code.

**Loop-back:** Re-enter Stage 2 (plan) if analyze finds CRITICAL constitution
violations or hallucinated references. Re-enter Stage 3 (tasks) if it finds
coverage gaps. Advance to Stage 5 with a clean analyze report.

**Harness instrumentation:**
- **Today:** `tests/architecture/` (run them — they're the executable
  constitution); `AGENTS.md` Ask-first list as the ADR-trigger checklist.
- **Today:** `make check` against the *current* codebase as the baseline — the
  design must not break what's currently green.
- **[v2-P2]:** `Stop`-hook ADR trigger fires here if the design touches an ADR
  seam and no ADR was raised.
- **[v2-P6.1b]:** `/speckit.analyze` automates the cross-artifact +
  constitution check; `make spec-check` (gated behind adoption) runs it on
  PRs touching `specs/**`.

---

### Stage 5 — Replan / sprint board  *(the deliberate gap)*

> This stage has **no native Spec Kit command**. It is the operator's
> first-class addition and the place where mid-flight re-prioritization,
> blocked-task surfacing, and loop re-entry are decided. Spec Kit's
> `/speckit.converge` touches re-planning but only *post-implementation*;
> mid-flight replanning is the gap the operator flagged.

**Initiation (human):** Triggered by one of: (a) a blocked task discovered
during implementation, (b) a scope change from the human, (c) a review finding
that invalidates a task, (d) the refine gate (Stage 10) sending the loop back.

**Agent work:**
- Read the current `tasks.md` and the blocked/failed items.
- Propose a re-prioritization: which tasks stay, which slip, which get split,
  which get dropped. Externalize state into the tasks file (the `spec-kit-loop`
  pattern: externalized state, not in-context-only).
- If scope changed, propagate back: does the spec need updating? (2026 best
  practice: *if requirements change, update the spec before touching the
  code* — the spec is the source of truth, code follows.)

**Human gate:** Approve the replan. This is the steering nudge — the human
decides what's in/out of the sprint, the agent proposes the re-ordering.

**Loop-back:** This stage *is* the loop-back hub. Outputs route to:
- Stage 2 (plan) if scope/spec changed.
- Stage 3 (task) if only task ordering/decomposition changed.
- Stage 6 (implementation) if only re-prioritization, no spec/plan change.

**Harness instrumentation:**
- **Today:** `tasks.md` (or the repo's `docs/plan/*.plan.md`) as the
  externalized state; the human reads it to decide.
- **[v2-P5]:** scratchpad/progress-file convention for long sessions (playbook
  Runbook #4 B1–B5) so the replan doesn't lose context across `/compact`.

---

### Stage 6 — Implementation  *(implement, per-task, maker/checker)*

**Initiation (human):** Hand the agent the (re-)approved task list. Start with
the first unblocked task.

**Agent work:**
- Execute tasks in order, respecting dependency and parallelization markers.
- **Per-task verification:** each task ends with a verification step — did the
  produced code satisfy the task's EARS-derived acceptance criteria? If not,
  iterate *bounded by the spec, not free-running*.
- **Red/green TDD for anything verifiable** (playbook Runbook #4 D2/D3/D7):
  write the test, watch it FAIL, then implement. Paste the actual command
  output, not a summary.
- **Record every LLM call** via `eval_capture.record()` with `user_id` +
  `task_id` (repo rule, `AGENTS.md` ✅ Always).

**Human gate:** Per-task: watch the red→green transition. The human nudges
when the agent gets stuck or drifts; does not write code.

**Loop-back:** Re-enter the same task if its verification criteria fail.
Re-enter Stage 5 (replan) if the task is blocked by something outside the
plan. Advance to Stage 7 (review) when the task (or the feature's task set) is
implemented green.

**Harness instrumentation:**
- **Today:** `PreToolUse` Bash → `pre_bash_guard.py` (blocks dangerous
  commands); `PostToolUse` Edit|Write → `post_edit_ruff.py` (ruff on every
  edit); `.cursor/hooks.json` `afterFileEdit` → `cursor_after_edit.py`;
  `beforeShellExecution` → `cursor_before_shell.py`.
- **Today:** `make check` is the per-implementation checkpoint (lint +
  format-check + pyright + test).
- **[v2-P3]:** test-deletion/skip detector — flags any deleted `def test_*`,
  added `pytest.skip`/`@pytest.mark.skip`/`@pytest.mark.xfail` flips. The
  ratchet move against silent test-weakening to go green.
- **[v2-P5]:** `PostCompact` re-injection of the current subtree's
  `AGENTS.md` so implementation doesn't lose the folder guide after a
  compaction.

---

### Stage 7 — Review  *(fresh-thread, multi-agent)*

**Initiation (human):** Trigger the review once implementation is green
locally. The key discipline: **review in a fresh thread**, as if someone else
wrote the diff (playbook Runbook #2 §6, Runbook #4 G4).

**Agent work:**
- Run the `review-local-changes` pattern: multiple specialized review passes
  in parallel — security, bug detection, code quality, API contracts, test
  coverage, change history — aggregated with confidence scoring and
  false-positive filtering.
- Map findings to the spec's acceptance criteria: does the diff actually
  deliver what each EARS criterion requires?
- Flag any comprehension-gate triggers in the diff: new abstraction (G1),
  crypto/signing path in `trust/` (G4), large test rewrite (G8), security
  boundary (G3), architecture change (G7).

**Human gate:** Triage findings. Accept, request changes, or reject. For any
G1/G4/G8/G3/G7 trigger, the human must satisfy the **forced-engagement gate**
(v2 plan 2.2): answer in their own words, *before* the agent reveals its
account — (1) what does this change do and why; (2) name the load-bearing
line; (3) what's the one assumption most likely to be wrong.

**Loop-back:** Re-enter Stage 6 (implementation) for fixable findings. Re-enter
Stage 5 (replan) if a finding invalidates a task. Advance to Stage 8 with
review-approved diff.

**Harness instrumentation:**
- **Today:** `meta/code_reviewer.py` + `codeReviewer` prompt; `review-bugbot`
  skill; `security-review` subagent; `governance-trace-audit` skill for
  telemetry-touching changes.
- **[v2-P2]:** `SubagentStop`-gated `code-reviewer` subagent that grades
  output and sends it back with `decision: block` + `reason` if quality
  below threshold — the deterministic gate the playbook names (M9).
- **[v2-P2]:** G3 (security) and G7 (architecture) re-added as
  forced-engagement gates with rotated wording in `docs/adr/GATES.md`.

---

### Stage 8 — Test  *(the repo's executable gates)*

**Initiation (human):** Hand the review-approved diff to the test stage.

**Agent work:**
- Run `make check` (lint + format-check + typecheck + test) — the canonical
  read-only pre-commit gate.
- Run `pytest tests/architecture/ -q` separately — the architecture invariants
  MUST pass; these are the executable constitution.
- For any `trust/` change: run the G4 surface tests explicitly.
- For any model-swap or evaluator change: run the A/B gate (`make model-ab`,
  never in CI) + the judge validation (`python -m meta.judge_validation`).
- Paste the actual command output, not a summary (playbook: demand evidence,
  not assertions).

**Human gate:** All gates green? If yes, advance. If no, route to Stage 9.

**Loop-back:** Any red gate → Stage 9 (issue fixes). Architecture-test red is
the most serious — it means the constitution is violated; route to Stage 5
(replan) or Stage 2 (plan), not just Stage 9.

**Harness instrumentation:**
- **Today:** `make check`; `tests/architecture/` (14 test files / 106 test
  functions); `make model-ab`;
  `python -m meta.judge_validation`; `.pre-commit-config.yaml` (ruff +
  gitleaks); `.github/workflows/pre-commit.yml` (CI).
- **Today (resolved, Wave 0):** `.cursor/hooks.json` `afterFileEdit` kept
  `failClosed: false` *by design* — the post-edit ruff hook is advisory
  formatting (HOOK-1: an `afterFileEdit`/`PostToolUse` hook never blocks an
  edit), so a formatter hiccup must not block the edit. The safety gate
  `beforeShellExecution` stays `failClosed: true`. This is the deliberate
  scoped deviation from the v2 plan's blanket-`true` contract (H5), documented
  inline in the file and in `docs/adr/decisions.md`.
- **[v2-P3]:** mutation testing scoped to `trust/` (`make mutate-trust`) —
  the behaviour-harness partial fix the playbooks call "the elephant in the
  room."
- **[v2-P4]:** `tier: regression` corpus rows + `regression_floor_violations()`
  wired into a pre-merge gate so a drop below 1.0 on a frozen eval blocks
  merge.

---

### Stage 9 — Issue fixes / improvements  *(converge-classified gaps)*

**Initiation (human):** Hand the red gates / review findings / test failures
to the agent.

**Agent work:**
- **Classify each issue** using the `/speckit.converge` taxonomy:
  - `missing` — a planned item was not implemented.
  - `partial` — implemented but doesn't meet the acceptance criterion.
  - `contradicts` — implemented but conflicts with the spec/plan.
  - `unrequested` — implemented but not in the spec (scope creep / drift).
- **Append, don't rewrite** (converge semantics): add a `## Phase N —
  Convergence` section to `tasks.md` with the new tasks + source-ref +
  gap-type. Never rewrite existing tasks or modify code in this stage — only
  spawn fix tasks.
- For `contradicts`/`unrequested` findings: route back to Stage 5 (replan) —
  these are spec/plan problems, not implementation problems.

**Human gate:** Approve the classified fix list. Decide which fixes are
in-this-iteration vs. deferred to `tech-debt-tracker.md`.

**Loop-back:** Fixes → Stage 6 (implementation). Spec/plan problems → Stage 5
or Stage 2. Advance to Stage 10 when all in-this-iteration fixes are
implemented and green.

**Harness instrumentation:**
- **Today:** `docs/adr/decisions.md` (v2 plan 6.3, lightweight DECISIONS.md —
  landed Wave 0) for small decisions made during fixing.
- **[v2-P6.2]:** `docs/adr/tech-debt-tracker.md` (the 6.2 ledger) for deferred
  items — **not yet created** (6.2 is a deferred subsystem; until it lands,
  deferred items go in the iteration's plan doc).
- **[v2-P6.2]:** weekly janitor agent that sweeps the tracker and opens small
  PRs per category.
- **[v2-P6.2.1]:** `drift-dashboard.md` rendered from the tracker — the
  trend view that tells you whether entropy is being reduced or accumulating.

---

### Stage 10 — Refine: acceptable? → production, else repeat  *(the sign-off gate)*

**Initiation (human):** All in-this-iteration tasks green, all CRITICAL
findings resolved, all gates passing.

**Agent work:**
- Run `/speckit.converge` (or the repo-native equivalent): assess the
  codebase against spec + plan + tasks. Did it converge?
  - **Converged** = no `missing`/`partial`/`contradicts` gaps remain.
  - **Not converged** = converge appended new Phase N tasks → re-enter at
    Stage 6.
- Produce the convergence report: what was delivered, what was deferred (and
  logged to `tech-debt-tracker.md`), what ADRs were raised.

**Human gate — the sign-off:** This is the production-readiness call. The
human must satisfy **all** of:
1. `/speckit.converge` reports converged (or the repo-native equivalent: every
   EARS acceptance criterion has a passing test).
2. `make check` green; `tests/architecture/` green.
3. Every ADR trigger raised during the change has an ADR filed under
   `docs/adr/` with `index.md` + `log.md` entries (OKF bundle).
4. Every comprehension gate (G1/G4/G8, and [v2-P2] G3/G7) that fired has been
   answered in the human's own words (the forced-engagement preamble).
5. The change is recorded via `eval_capture.record()` with `user_id` +
   `task_id` for every LLM call.

**Loop-back / advance:**
- **Not converged** → re-enter Stage 6 with the new Phase N tasks.
- **Converged but a gate fails** → Stage 9 (issue fixes).
- **Converged + all gates green + sign-off** → **production**. Merge.

**Harness instrumentation:**
- **Today:** the ADR OKF bundle (`docs/adr/` template + index + log) is the
  intent-debt capture; G1/G4/G8 are prose triggers in `AGENTS.md`; the
  "honest enforcement limit" note (hooks can't capture typed answers) means
  the sign-off is convention + PR-review, not tool-enforced, for the
  *answer* part.
- **[v2-P2]:** `Stop`-hook ADR trigger enforces the *trigger* (block if an
  ADR seam was touched and no ADR file appeared); the *typed answer* stays
  prose (the honest limit).
- **[v2-P6.2.1]:** the drift-dashboard retirement threshold — if a category's
  open count stays at 0 for ≥8 consecutive janitor runs, retire the
  `AGENTS.md` rule that produced it (the Ratchet deletion direction).

---

## 4. The converge loop — the "repeat" mechanics

The "repeat the loop" in the operator's lifecycle is **not** a free re-run.
It is the `/speckit.converge` mechanics, made concrete:

1. After Stage 9 fixes are implemented (Stage 6) and tested (Stage 8), run
   converge (Stage 10).
2. Converge is **append-only**: it never rewrites existing tasks or modifies
   code. It appends a `## Phase N — Convergence` section to `tasks.md` with
   new tasks, each tagged with `source-ref` + `gap-type`
   (`missing`/`partial`/`contradicts`/`unrequested`).
3. If new tasks were appended → re-enter Stage 6, implement them, re-test,
   re-converge. Repeat.
4. The loop terminates when converge reports **no new tasks** = the feature
   has converged. Then the human sign-off (Stage 10) is the final gate to
   production.

**Bounded iteration (from the `spec-kit-loop` research):** the loop must have
a `max_iterations` hard ceiling. If convergence isn't reached within the
budget, **forced human review** — don't let the agent free-run. This is the
"safety and reviewable" discipline: a maker that never grades itself, an
independent checker, and a guard that won't let the loop call itself done
until a human signs off.

**`contradicts` and `unrequested` are not implementation bugs** — they are
spec/plan drift. Route them to Stage 5 (replan) or Stage 2 (plan), not Stage 6.
This is the 2026 best practice: *if requirements change, update the spec
before touching the code.*

---

## 5. Harness instrumentation crosswalk — what fires today vs. what's promised

| Stage | Fires today | Fires after v2 plan lands |
|---|---|---|
| 1 brainstorm | nested `AGENTS.md`, invariants, `tests/architecture/` | **[P5]** `explore` subagent (context firewall) |
| 2 plan | `AGENTS.md` Ask-first list, `tests/architecture/` | **[P2]** `Stop`-hook ADR trigger; **[P6.1b]** `/speckit.plan` constitution check |
| 3 task | human review only | **[P6.1b]** `/speckit.analyze` coverage check |
| 4 design | `tests/architecture/`, `make check` baseline, Ask-first list | **[P2]** `Stop`-hook ADR trigger; **[P6.1b]** `/speckit.analyze` + `make spec-check` |
| 5 replan | `tasks.md` / `docs/plan/*.plan.md` externalized state | **[P5]** scratchpad/progress-file convention |
| 6 implementation | `pre_bash_guard.py`, `post_edit_ruff.py`, `cursor_after_edit.py`, `cursor_before_shell.py`, `make check` | **[P3]** test-deletion/skip detector; **[P5]** `PostCompact` re-injection |
| 7 review | `meta/code_reviewer.py`, `review-bugbot`, `security-review`, `governance-trace-audit` | **[P2]** `SubagentStop`-gated reviewer; G3/G7 re-added with rotated wording in `GATES.md` |
| 8 test | `make check`, `tests/architecture/`, `make model-ab`, `judge_validation`, pre-commit + CI; `afterFileEdit failClosed:false` (resolved by design, W0) | **[P3]** mutation testing on `trust/`; **[P4]** regression tier + pass^k cadence |
| 9 issue fixes | `decisions.md` (small decisions, landed W0) | **[P6.2]** `tech-debt-tracker.md` ledger + janitor agent; **[P6.2.1]** drift-dashboard |
| 10 refine | ADR OKF bundle, G1/G4/G8 prose triggers | **[P2]** `Stop`-hook ADR trigger (the trigger, not the answer); **[P6.2.1]** retirement threshold |

> **Reading this table honestly:** today, the mechanically-enforced gates are
> `make check`, `tests/architecture/`, the 4 hook scripts, and pre-commit/CI.
> The comprehension gates (G1/G4/G8) and the sign-off are *convention +
> PR-review*, not tool-enforced — this is the repo's stated "honest enforcement
> limit." The v2 plan's Phase 2 closes the *trigger* half of that gap (the
> `Stop` hook can block on a missing ADR); the *typed-answer* half stays prose
> because hooks still can't capture free-form human text. The runbook is
> written to be executable today and to tighten as the v2 phases land.

---

## 6. When to skip this runbook (the vibe-coding carve-out)

The 2026 SDD consensus is explicit: **SDD is for production-grade, durable
work where intent clarity and alignment are critical.** It is *not* for
everything. From the research (DEV, BCMS, Microsoft):

- **Trivial changes** (typo, one-line fix, throwaway prototype) → skip the
  full runbook; use vibe coding. The constitution (`AGENTS.md` +
  `tests/architecture/` + `make check`) still applies — those are always on.
- **Exploratory / experimental code** that may be thrown away → brainstorm
  (Stage 1) + a light spec, skip the full plan/tasks/analyze chain.
- **Production-grade, durable changes** → full runbook. This is the default
  for this repo, which is a durable, human-curated codebase (the v2 plan's
  "spec-anchored, not spec-as-source" decision).

**Repo-specific trigger:** any change that touches an ADR seam
(`trust/models.py`, `orchestration/react_loop.py` adding a node, a new
horizontal service, a new abstraction, a `pyproject.toml` dependency) is
*by definition* non-trivial and must run the full runbook + raise an ADR.

---

## 7. External research sources (2026)

1. **GitHub Spec Kit v0.11.9 (2026-06-26)** — the high-assurance command spine
   `/speckit.constitution → specify → clarify → plan → checklist → tasks →
   analyze → implement → converge`; EARS acceptance criteria; constitution as
   mechanically-checked backdrop. → Stages 1–4, 6, 9, 10.
2. **Nexo Spec Kit Phase 0 (nsalvacao/spec-kit, 2026)** — the `IDEATE →
   SELECT → STRUCTURE → VALIDATE` ideation layer + `/speckit.brainstorm`
   before SDD. → Stage 1 (the deliberate addition Spec Kit upstream lacks).
3. **`sdd-brainstorm` skill (claudeskills.info, 2026)** — 6-solution
   generation (3 high-probability + 3 exploratory) with tradeoffs. → Stage 1
   agent work.
4. **`review-local-changes` skill (claudeskills.info, 2026)** — 6 parallel
   specialized review agents (security, bugs, quality, API contracts, test
   coverage, change history) with confidence scoring + false-positive
   filtering. → Stage 7.
5. **`spec-kit-loop` (formin, 2026)** — maker/checker split, independent
   adversarial checker in a fresh session, `max_iterations` hard ceiling,
   externalized state, comprehension-debt ledger, human sign-off gate. →
   Stages 6, 9, 10; the bounded-iteration discipline in §4.
6. **Spec Kit Agents (Taghavi & Bhavani, arXiv 2604.05278, 2026)** —
   discovery hooks (pre-phase, read-only repo probing) + validation hooks
   (post-phase, executable checks). Empirical: +0.15 quality on 1–5 composite
   judge score across 128 runs / 32 features; 99.7–100% test compatibility;
   58.2% SWE-bench Lite Pass@1. The core finding: front-load error detection
   to stop "context blindness" (hallucinated APIs, invalid paths,
   architectural violations) before code compounds them. → Stages 1, 4, 6
   (the grounding + validation pattern).
7. **Microsoft SDD for AI-native engineering (2026)** — Constitution →
   Specify → Clarify → Plan → Tasks → Implement → Validate; pilot →
   formalize → iterate → refine-and-scale. → §0 shaping principle, §6
   carve-out.
8. **BCMS / DEV / Allegro 2026 SDD guides** — EARS as de facto standard;
   spec-anchored as the sweet spot; "never skip spec → code"; "if
   requirements change, update the spec before touching the code"; review at
   every phase boundary. → Stages 2, 3, 4, 9.
9. **ASDLC Agent Constitution (2026)** — constitution as the agent's
   "Superego"; "before adding any rule to agents.md, ask: can a tool or
   runtime already enforce this?"; negative constraints are least reliable →
   back critical ones with deterministic gates. → §2, the repo's
   `tests/architecture/` as the deterministic backing.

---

## 8. Bottom line

This runbook takes the operator's lifecycle and makes it executable against
this repo's actual harness. The three load-bearing ideas from the research:

1. **The constitution is already here.** `AGENTS.md` invariants +
   `tests/architecture/` are a stronger constitution than a fresh Spec Kit
   install. The Spec Kit decision (v2 plan 6.1b) is whether the CLI earns its
   place over the repo-native template (6.1a) — *not* whether the repo needs a
   constitution.
2. **Every stage is a human↔agent micro-loop.** The agent is the workhorse;
   the human initiates, validates, accepts/rejects, and nudges. The runbook
   makes the initiate→do→gate→(re-enter|advance) shape explicit at all ten
   stages so it doesn't collapse into "hand the agent the spec and walk away."
3. **The loop is bounded, not free-running.** `/speckit.converge` is
   append-only and terminates on no-new-tasks; `spec-kit-loop` adds the
   `max_iterations` ceiling and the human sign-off gate. "Repeat the loop"
   means the converge mechanics in §4, not a free re-run.

The deliberate gap the operator flagged — **replan / sprint board (Stage 5)**
— is treated as first-class. Spec Kit has no native command for it; the
runbook makes it the loop-back hub that routes to Stage 2 (scope changed),
Stage 3 (re-ordering), or Stage 6 (re-prioritization only).
