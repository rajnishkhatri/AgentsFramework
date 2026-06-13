# Cursor Agent Skills (docs mirror)

Documentation copies of Cursor/Claude skills installed under `.cursor/skills/` or
`~/.cursor/skills/`. This folder versions them with the repo so they're
discoverable and reviewable in PRs.

## LLM evaluation

| Skill | Scope | Start here |
| --- | --- | --- |
| [`llm-eval-grounded-theory`](llm-eval-grounded-theory/SKILL.md) | **Generic, portable.** Open coding → axial coding → synthetic strata → rubric → gold set → judge calibration → continuous monitoring. GoalJudge repo artifacts as worked example. | [SKILL.md](llm-eval-grounded-theory/SKILL.md) |

Implementation plan: [`docs/plans/llm_eval_pipeline_skill.plan.md`](../plans/llm_eval_pipeline_skill.plan.md).

Related research: [`goaljudge_evaluation_pipeline_open_axial_coding_rubric.md`](../research/goaljudge_evaluation_pipeline_open_axial_coding_rubric.md).

---

## Governance trace audit

| Skill | Scope | Start here |
| --- | --- | --- |
| [`governance-trace-audit`](governance-trace-audit/SKILL.md) | **This repo only.** Audit a production Langfuse trace against the governance-triangle intent — the four pillars (Recording / Identity / Validation / Reasoning) — and produce a verdict report with a per-pillar scorecard. Corrupt-success check always first; encodes the trace-explainability session's judgment (zero-carrier token seam, accepted-by-design limitations, short-form-for-clean-traces, one-line instrumentation-vs-run-honesty summary). Run it post-deploy or as a compliance/post-implementation review. | [SKILL.md](governance-trace-audit/SKILL.md) |

Benchmarked over two iterations vs no-skill baselines on real production trace
fixtures: **with-skill 26/27 (96%) vs baseline 11/27 (41%)** — baselines detect
the anomalies but misclassify caught corrupt-successes as instrumentation
failures and miss zero-carrier facts. `evals/` (3 real-trace fixtures + 27
assertions) is included here on purpose: the fixtures double as reference
traces for the check catalog. `governance-trace-audit.skill` is the packaged,
installable archive.

Origin/plan: [`docs/plans/trace_explainability_optimization.plan.md`](../plans/trace_explainability_optimization.plan.md)
(the trace-explainability work this skill enforces). Related:
[`governanaceTriangle/`](../../governanaceTriangle/) tutorial docs.

---

## Playwright E2E Skills

Two complementary skills for end-to-end testing this app's streaming agent UI with
Playwright. Installed copies live at `~/.claude/skills/` (Claude Code) and
`.cursor/skills/` where applicable. The `evals/` test scaffolding and license
files are intentionally omitted here.

## The two skills

| Skill | Scope | Start here |
| --- | --- | --- |
| [`playwright-agentic-e2e`](playwright-agentic-e2e/SKILL.md) | **Generic, portable.** The methodology for testing any streaming AI/agent chat app — configuring Playwright, auth via storageState, the tiered mock strategy, handling non-deterministic/streamed output, running against cloud-hosted targets, and server-side verification. Reusable across workspaces. | [SKILL.md](playwright-agentic-e2e/SKILL.md) |
| [`agentsframework-playwright`](agentsframework-playwright/SKILL.md) | **This repo only.** The binding layer: exact T1/T2/T3 commands, WorkOS env vars, Cloud Run URLs, real selectors, the GoalJudge batch, and the hard-won gotchas. Defers to the generic skill for the "why". | [SKILL.md](agentsframework-playwright/SKILL.md) |

The generic skill teaches *how streaming/auth/cloud testing works*; the workspace
skill gives *the exact commands and selectors for here*. Read them together.

## Relationship to the existing docs

These distill and operationalize the testing docs already in `docs/`:
- [`PLAYWRIGHT_TESTING_ARCHITECTURE.md`](../PLAYWRIGHT_TESTING_ARCHITECTURE.md) — the T1/T2/T3 architecture & rationale
- [`FRONTEND_VALIDATION.md`](../FRONTEND_VALIDATION.md) — the SS-numbered manual checklist the specs mirror
- [`frontend/e2e/README.md`](../../frontend/e2e/README.md) — the suite's own quick-start and layout

## Contents

### `playwright-agentic-e2e/` (generic)
- `SKILL.md` — cut-point model, a fill-in config block, the 5-step workflow
- `references/` — `configuration`, `authentication`, `streaming-and-agents`, `running-and-ci`, `cloud-and-verification`
- `assets/` — parameterized templates: `playwright.config`, `global-setup`, `auth.fixture`, `helpers`, `spec`
- `scripts/verify_run.py` — reconcile a full-stack capture artifact against backend logs/traces (stdlib-only)

### `agentsframework-playwright/` (this repo)
- `SKILL.md` — exact commands, env vars, URLs, selectors, headline gotchas
- `references/gotchas.md` — full gotcha catalog with fixes + the working `gcloud` query
- `references/goaljudge-batch.md` — the GoalJudge registry batch + verification playbook
