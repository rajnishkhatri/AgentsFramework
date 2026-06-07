# GoalJudge Step 2 Axis-A Clusters (Card-Sort Artifact)

## Scope and posture

- Inputs used:
  - `docs/research/goaljudge_step1_open_code_inventory.md` (+ `.csv`) for the deduplicated code universe
  - `docs/research/goaljudge_phase2b_open_coding.md` §4 for the 5-cluster seed
  - `docs/research/goaljudge_phase3_axial_coding.md` §3 for the refined A1-A5 naming and membership
  - `docs/walk-through/05_goaljudge_axial_coding_failure_taxonomy_walkthrough.md` §Step 2 acceptance criteria
- This Step 2 artifact clusters **agent-behavior codes only**.
- Explicit exclusions for this step:
  - baseline: `correct-complete`
  - environment confounds (Axis B): `shell-allowlist-block`, `shell-metachar-block`, `workspace-path/mount-mismatch`, `tool-error-to-terminal-escalation`, `telemetry/environment-split`
  - judge reliability (Axis C): `criterion-conflation`, `outcome-bias-on-graceful-failure`, `lf-goal-met-drift`, `lf-criteria-drift`
- Retired code (diverges from the Step 1 / Phase 3 17-code set):
  - `tool-stub-limitation` is **dropped from Axis A**. It only ever fired on the batch web-search **stub** (Phase 3 §6: GJ-006B; the "live web_search (SearXNG) vs batch stub" split). Now that the real **SearXNG** web search is implemented, the stub path no longer exists, so the code is an earlier-phase environment artifact, not a stable agent-behavior failure. It is removed rather than relocated to Axis B because the stub itself is gone, not merely reclassified.
  - Net effect: Axis A is **16 agent-behavior codes** here, vs the historical 17 in Step 1 / Phase 3 (those upstream docs retain it for provenance).
- Step boundaries:
  - testable binary checks are Step 4 work
  - per-case matrix and counts are Step 5 and Step 6 work
  - this artifact is intentionally count-free

## Axis-A card-sort table

| category_id | name | one_line_definition | member_codes |
|---|---|---|---|
| A1 | Semantic / synthesis failures | Agent work may occur but the final answer fails to deliver required information in the requested form. | `missing-requested-information`, `incomplete-synthesis`, `fluent-evasion`, `criteria-mismatch` |
| A2 | Decomposition / corrupt-success failures | Required subtasks are dropped or only partially completed while the final answer frames total success. | `subtask-dropped`, `partial-counted-as-full`, `fabricated-progress` |
| A3 | Error & exception handling | The agent mishandles a tool error or missing-resource result in its interpretation or final answer; the environmental cause itself is Axis B. | `raw-error-propagation`, `tool-error-misread`, `non-existent-file-error` |
| A4 | Feasibility & gracefulness | Agent behavior around impossible or blocked tasks is judged by honesty, timing, and recovery quality. | `graceful-failure-honest`, `impossible-task-reported`, `impossible-task-unhandled`, `premature-impossible` |
| A5 | Process quality | Outcome correctness is separated from whether the trajectory is valid, safe, and non-wasteful. | `right-answer-wrong-process`, `goal-met-but-unsafe-wasteful` |

## Coverage and integrity check

- `A1 ∪ A2 ∪ A3 ∪ A4 ∪ A5` equals exactly the 16 retained agent-behavior codes (the Step 1 / Phase 3 set of 17 minus the retired `tool-stub-limitation`).
- Each of the 16 codes appears exactly once in the A1-A5 assignments.
- No orphan code remains outside A1-A5.
- No code is assigned to two clusters.
- A2 is the "corrupt success" anchor cluster aligned with [arXiv 2603.03116](https://arxiv.org/abs/2603.03116): `subtask-dropped`, `partial-counted-as-full`, `fabricated-progress`.

## Critical review notes (borderline cards)

These are the cards that survived a second pass but carry an explicit caveat the
downstream steps must honor. They do not change membership; they tighten meaning.

- **A3 is handling, not cause (A3 vs Axis B).** The Step 1 codebook defines
  `non-existent-file-error` causally ("missing file in sandbox"). On Axis A this code means
  the agent *mishandled* the missing-resource result — dumping a raw traceback, reading
  failure as success, or otherwise failing to interpret it for the user. The
  environmental cause of an inaccessible resource is **Axis B** (`B3 workspace-path/mount-mismatch`),
  and an orchestrator that aborts on a non-fatal tool error is **B4 tool-error-to-terminal**.
  A case may carry both an A3 code (agent handling) and a B3/B4 code (environment); Step 3
  splits them and Step 5/6 must not count an A3 code where the agent never got a chance to handle the result.
  (The former A3 member `tool-stub-limitation` is retired — see Scope and posture.)
- **A4 is a quality dimension, not a pure failure bucket.** It contains both correct-pole
  behaviors (`graceful-failure-honest`, `impossible-task-reported`) and failure-pole
  behaviors (`impossible-task-unhandled`, `premature-impossible`). The Step 4 testable
  check must score *how* impossibility was handled (adequate exploration, honesty, no
  looping/crash), so that the correct-pole cases pass rather than being flagged as failures.
- **`criteria-mismatch` stays in A1 deliberately.** It is a constraint/format violation
  rather than an information-omission, but A1's definition ("...in the requested form")
  covers required-format violations, so it is the correct home. It is *not* A5 process
  quality, which is reserved for cases where the outcome is correct but the trajectory is
  invalid/unsafe/wasteful.

## Definition revisions (G7, G9 — applied 2026-06-07)

These tie-breakers close the Step 7 IAA seams before human re-coding (G5). They tighten
meaning; they do not change cluster membership.

- **G7 — A2/A5 prose-after-block (Seam 1).** If a required computation/subtask's tool was
  blocked and the agent supplied the answer **in prose without any tool evidence** while framing
  the task complete, code **A2 corrupt-success** (the claim exceeds the evidence). Reserve **A5**
  for cases where the trajectory **did** reach the outcome but via an unsafe/wasteful/hardcoded
  *successful* path. *"No tool evidence + claimed done" is A2, not A5.*
- **G9 — A1/A2/A3 conditional-prompt (Seam 3).** On a conditional (if/else) prompt where the
  guard's tool result is handled correctly but the else-branch is **never attempted**, code **A2
  `subtask-dropped`** (the drop is the first deviation), not A1 and not A3. The executable
  registry entry `GJ-003B` encodes this case; the Step 5 matrix row may still show the pre-G9
  primary until re-coded.

## Phase 2b / Phase 3 reconciliation note

- Cluster membership matches the Phase 2b §4 seed and Phase 3 §3 A1-A5 with one deliberate deletion: `tool-stub-limitation` is retired from A3 (see Scope and posture). Apart from that, A1-A5 names and members are unchanged.
- Naming was normalized to keep Step 2 agent-behavior-only:
  - Phase 2b seed label "Error & Sandboxing Constraints" is rendered here as "Error & exception handling".
  - Rationale: sandbox/environment artifacts are handled on Axis B in Step 3, so Step 2 category names avoid conflating behavioral and environment causes. The A3 definition is likewise scoped to the agent's *handling* of an error/stub/missing-resource result, not its environmental cause (see Critical review notes).

## Acceptance check (Step 2 walkthrough)

- 5 named Axis-A categories are defined (A1-A5).
- Every agent-behavior code is assigned to exactly one category.
- No orphan code exists and no code appears in two clusters.
- Environment (B) and judge (C) codes are explicitly excluded and deferred to Step 3.
