# Skills bundle index

OKF bundle of repo skills. Each entry is a `type: skill` Concept (a `SKILL.md`).
See the convention in [CONVENTIONS_OKF.md](../CONVENTIONS_OKF.md).

- [agentsframework-eval-probe](agentsframework-eval-probe/SKILL.md) — add and operate a continuous-evaluation PROBE on any LLM-call seam in this repo (open coding → taxonomy → rubric → judge → registered probe + drift loop).
- [agentsframework-open-coding](agentsframework-open-coding/SKILL.md) — run a hands-on open-coding session over agent traces: local HTML coder → JSONL → Langfuse dataset for human review.
- [agentsframework-playwright](agentsframework-playwright/SKILL.md) — concrete Playwright E2E playbook for this repo (WorkOS auth, T1/T2/T3 tiers, Cloud Run, GoalJudge batch, exact commands/selectors).
- [gcp-live-smoke](gcp-live-smoke/SKILL.md) — Phase 2 live GCP smoke test: one real browser run against the deployed Cloud Run frontend proving the pipeline end-to-end.
- [governance-trace-audit](governance-trace-audit/SKILL.md) — audit a Langfuse trace against the governance four pillars (Recording / Identity / Validation / Reasoning) and emit a per-pillar scorecard.
- [agentsframework-okf-curator](agentsframework-okf-curator/SKILL.md) — keep the OKF knowledge plane (docs/ + research/) in sync with code: document features as recipes, file research, run a code↔docs drift check, keep the tree typed/catalogued/lint-green.
- [llm-eval-grounded-theory](llm-eval-grounded-theory/SKILL.md) — the qualitative-to-quantitative LLM eval pipeline: open/axial coding, strata coverage, rubric design, gold sets, judge calibration, monitoring.
- [playwright-agentic-e2e](playwright-agentic-e2e/SKILL.md) — provider-agnostic methodology for E2E testing streaming/agentic chat apps with Playwright (auth via storageState, SSE assertions, cloud runs).
