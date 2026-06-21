---
type: plan
title: 'Dataset Adaptation Plan for Deep-Agent Benchmark'
description: 'This plan defines how to adapt external and internal sources into a stable, reproducible benchmark fixture for deep-agent capability evaluation.'
tags: [plan]
---

# Dataset Adaptation Plan for Deep-Agent Benchmark

This plan defines how to adapt external and internal sources into a stable, reproducible benchmark fixture for deep-agent capability evaluation.

## Objective

- Build a starter benchmark pack with 12 adapted cases:
  - 4 easy
  - 4 medium
  - 4 hard
- Preserve the runtime fixture schema used by synthetic end-to-end tests (`id`, `task_input`, `llm_script`, `expectations`).
- Make case selection auditable with source-level provenance and deterministic criteria.

## Target Fixture Schema

Every adapted case must include:

- `id`: stable, unique slug
- `task_input`: user-facing objective prompt
- `llm_script`: deterministic scripted model/tool trajectory
- `expectations`: assertions on planning depth, todo/file outcomes, and offload behavior
- `metadata`: adaptation metadata (difficulty, source, tags, rationale, risk flags)

## Source-by-Source Mapping


| Source                                                       | Why Included                                           | Raw Pattern                                                | Adapted Pattern in Fixture                                                                                | Main Risks                             | Mitigation                                                        |
| ------------------------------------------------------------ | ------------------------------------------------------ | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | -------------------------------------- | ----------------------------------------------------------------- |
| Internal synthetic traces (`deep_agent_synthetic_e2e_cases`) | Known-good baseline and schema anchor                  | Multi-turn tool trajectories with deterministic tool calls | Reuse shape directly; add `metadata` and broaden task domains                                             | Overfitting to current tool API        | Keep source-mix quotas and add non-identical phrasing             |
| GAIA-style agent tasks (public benchmark pattern)            | Strong decomposition and multi-step planning prompts   | Open-ended tasks requiring retrieval and synthesis         | Convert to offline scripted tool calls (`state_todo`, `state_file`, `emit_large`) with pre-baked outcomes | Hidden dependency on live web context  | Remove live retrieval dependency; bake context into task text     |
| Hotpot/2-hop QA style prompts                                | Good for compositional reasoning under compact context | Multi-hop question + synthesis                             | Translate into "analyze + summarize + constraint check" tasks that require todo progression               | Too QA-specific and shallow tool usage | Require at least one state transition (todo/file) in adapted case |
| Arena-style coding review prompts (internal/meta)            | Captures review and trade-off reasoning                | Compare alternatives, produce justified recommendation     | Adapt to architecture/design synthesis tasks with explicit constraints and deliverables                   | Subjective grading                     | Encode objective expectation checks in `expectations`             |
| Long-context summarization prompts (internal docs)           | Exercises offload/compaction pathways                  | Large artifacts and condensed final answer                 | Use `emit_large` scripted calls to enforce offload threshold behavior                                     | Artificial artifact size               | Mark as stress case and keep balanced with normal-sized cases     |


## Selection Criteria

A candidate source item is selected only if all required criteria pass.

### Required Criteria

1. Deterministic trajectory can be scripted with available test tools.
2. Case can be validated with objective assertions in `expectations`.
3. Prompt avoids live network, credentials, or environment-specific data.
4. Adapted task maps to one primary capability and at most two secondary capabilities.
5. Language is clear enough for reproducible model/tool behavior in CI.

### Exclusion Criteria

- Requires external APIs or web browsing to succeed.
- Depends on private data not committed in repository fixtures.
- Only tests stylistic writing quality with no observable state/tool effects.
- Duplicates an existing case capability pattern without adding new signal.

## Difficulty Rubric

Difficulty is assigned using deterministic rules:

- **Easy**
  - 1-2 tool calls in first scripted turn
  - Single objective with direct success criteria
  - No offload expected
  - Planning depth target: `L0` or de-escalation to `L0`
- **Medium**
  - 2-4 tool calls with at least one state transition (`in_progress` -> `completed`)
  - 2 linked objectives (for example: compare + summarize)
  - Optional file artifact
  - Usually starts at `L1`, may finish `L0`
- **Hard**
  - 3+ tool calls and at least one of: large-output offload, multi-artifact production, or explicit constraint reconciliation
  - Requires structured sequencing (todo + file + synthesis)
  - Offload expected in at least half of hard cases
  - Planning depth starts at `L1` or `L2`

## Capability Coverage Matrix

Each adapted case should map to one primary capability:

- C1: Planning depth selection
- C2: Todo lifecycle management
- C3: File artifact persistence
- C4: Offload/compaction behavior
- C5: Constraint-aware synthesis

Starter pack target coverage (12 cases):

- C1: 3 cases
- C2: 3 cases
- C3: 2 cases
- C4: 2 cases
- C5: 2 cases

## Sampling and Balance Rules

- Difficulty balance must be exactly `4/4/4` (easy/medium/hard).
- No source contributes more than 50% of the starter pack.
- At least 3 distinct source families must appear.
- At least 2 hard cases must assert `expect_offload = true`.

## Adaptation Workflow

1. Candidate intake
  - Gather source tasks and register provisional source tags.
2. Normalization
  - Rewrite prompts into repo-safe, deterministic task inputs.
3. Script synthesis
  - Create `llm_script` tool call sequence using available test tools.
4. Assertion design
  - Encode expected state deltas in `expectations`.
5. Difficulty tagging
  - Apply rubric and verify quota constraints.
6. Fixture validation
  - JSON lint + targeted test execution.
7. Review and freeze
  - Record adaptation notes; freeze case IDs for benchmark stability.

## Quality Gates Before Merge

- Schema validity: fixture parses as JSON array of case objects.
- Determinism: repeated test runs produce identical outcomes.
- Architecture safety: no new cross-layer imports introduced by benchmark wiring.
- Coverage check: quotas for source diversity and capability matrix pass.

## Starter Pack Notes

The initial 12-case file (`tests/fixtures/deep_agent_benchmark_adapted_cases.json`) is intentionally conservative:

- Uses existing deterministic tools and expectations schema.
- Adds adaptation `metadata` for future analysis without breaking existing loaders.
- Provides a baseline for later expansion to larger benchmark tiers.

