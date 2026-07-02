# Skills bundle index

OKF bundle of repo skills. Each entry is a `type: skill` Concept (a `SKILL.md`).
See the convention in [CONVENTIONS_OKF.md](../CONVENTIONS_OKF.md).

- [agentsframework-eval-probe](agentsframework-eval-probe/SKILL.md) — add and operate a continuous-evaluation PROBE on any LLM-call seam in this repo (open coding → taxonomy → rubric → judge → registered probe + drift loop).
- [code-review](code-review/SKILL.md) — run the unified, context-routed code reviewer (v3) over the current branch's changed files: routes each path to its folder's `REVIEW.md`, runs the deterministic AST/TS validators first (D1/D4/D5 + TAP-2/TAP-4 + ADR.1 + FD2/FD3), then the v3 LLM reviewer with the routed `REVIEW.md` injected.
- [agentsframework-open-coding](agentsframework-open-coding/SKILL.md) — run a hands-on open-coding session over agent traces: local HTML coder → JSONL → Langfuse dataset for human review.
- [agentsframework-playwright](agentsframework-playwright/SKILL.md) — concrete Playwright E2E playbook for this repo (WorkOS auth, T1/T2/T3 tiers, Cloud Run, GoalJudge batch, exact commands/selectors).
- [gcp-live-smoke](gcp-live-smoke/SKILL.md) — Phase 2 live GCP smoke test: one real browser run against the deployed Cloud Run frontend proving the pipeline end-to-end.
- [governance-trace-audit](governance-trace-audit/SKILL.md) — audit a Langfuse trace against the governance four pillars (Recording / Identity / Validation / Reasoning) and emit a per-pillar scorecard.
- [agentsframework-okf-curator](agentsframework-okf-curator/SKILL.md) — keep the OKF knowledge plane (docs/ + research/) in sync with code: document features as recipes, file research, run a code↔docs drift check, keep the tree typed/catalogued/lint-green.
- [llm-eval-grounded-theory](llm-eval-grounded-theory/SKILL.md) — the qualitative-to-quantitative LLM eval pipeline: open/axial coding, strata coverage, rubric design, gold sets, judge calibration, monitoring.
- [playwright-agentic-e2e](playwright-agentic-e2e/SKILL.md) — provider-agnostic methodology for E2E testing streaming/agentic chat apps with Playwright (auth via storageState, SSE assertions, cloud runs).
- [memory-compaction](memory-compaction/SKILL.md) — compact Claude Code's always-loaded memory index (MEMORY.md) when it grows past ~15 KB: re-hook-first lossless rewrite (detail stays in topic files), with analyze/verify scripts and a SessionStart auto-trigger.
- [sdd-lifecycle](sdd-lifecycle/SKILL.md) — route a production-grade change through the 10-stage SDD lifecycle: which sdd-* sibling owns each stage, the constitution-is-AGENTS.md rule, the vibe-coding carve-out.
- [sdd-brainstorm](sdd-brainstorm/SKILL.md) — SDD Stage 1: expand a problem into ~6 candidate directions (3 conventional + 3 exploratory) and validate every hypothesis against repo evidence before specifying.
- [sdd-spec](sdd-spec/SKILL.md) — SDD Stages 2–4 (keystone): EARS spec from `_spec_template.md` → clarify pass → plan → tasks → cross-artifact analyze + constitution/grounding check. Never skip spec → code.
- [sdd-replan](sdd-replan/SKILL.md) — SDD Stage 5: the mid-flight loop-back hub — externalize state to the plan doc, route scope-change→spec / re-order→tasks / re-prioritize→implementation.
- [sdd-implement](sdd-implement/SKILL.md) — SDD Stage 6: execute the approved task list with red/green TDD + per-task EARS verification, bounded by the spec; surfaces the write/commit/merge-time sensors.
- [sdd-converge](sdd-converge/SKILL.md) — SDD Stages 9–10: classify gaps (missing/partial/contradicts/unrequested), append Phase-N fix tasks, run the 5-point production sign-off; bounded iteration.
