# Cursor Agent Skills (docs mirror)

Documentation copies of Cursor/Claude skills installed under `.cursor/skills/` or
`~/.cursor/skills/`. This folder versions them with the repo so they're
discoverable and reviewable in PRs.

## LLM evaluation

| Skill | Scope | Start here |
| --- | --- | --- |
| [`llm-eval-grounded-theory`](llm-eval-grounded-theory/SKILL.md) | **Generic, portable.** Open coding → axial coding → synthetic strata → rubric → gold set → judge calibration → continuous monitoring. GoalJudge repo artifacts as worked example. | [SKILL.md](llm-eval-grounded-theory/SKILL.md) |
| [`agentsframework-eval-probe`](agentsframework-eval-probe/SKILL.md) | **This repo only.** Add a continuous-evaluation PROBE to any LLM-call seam: open coding → taxonomy → rubric → judge → a registered probe (L1 deterministic 100% / L2 sampled judge / L3 drift / offline CI regression / per-component enable-gate). Tiered — a light Tier-A probe ships first; the gold-set + judge track is earned on-demand. Builds on `meta/drift.py`, `meta/judge.py`, `eval_capture`, and the guardrail/GoalJudge precedents. | [SKILL.md](agentsframework-eval-probe/SKILL.md) |

Implementation plans: [`docs/plans/llm_eval_pipeline_skill.plan.md`](../plans/llm_eval_pipeline_skill.plan.md) (binding layer), [`docs/plans/eval_probe_pipeline_skill.plan.md`](../plans/eval_probe_pipeline_skill.plan.md) (probe skill).
Engineer walkthrough: [`docs/handbooks/add_an_eval_probe.md`](../handbooks/add_an_eval_probe.md).
Trigger-prompt examples (how to phrase a request so the probe skill fires): [`agentsframework-eval-probe-TRIGGER-PROMPTS.md`](agentsframework-eval-probe-TRIGGER-PROMPTS.md).
Benchmarked over two skill-creator iterations vs no-skill baselines (3 test seams: plan_builder trace-altitude, summarizer Tier-A, seam-prioritizer): **with-skill 95.8% vs baseline 66.4%** at iteration 2, after folding the review feedback (altitude-as-decision, telemetry-publish, Phase-0 rigor, inline-vs-offline L1 split, pytest-replay CI gate).

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
- [`PLAYWRIGHT_TESTING_ARCHITECTURE.md`](../Architectures/PLAYWRIGHT_TESTING_ARCHITECTURE.md) — the T1/T2/T3 architecture & rationale
- [`FRONTEND_VALIDATION.md`](../guides/FRONTEND_VALIDATION.md) — the SS-numbered manual checklist the specs mirror
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

---

## Portable SDD lifecycle skills (workspace-neutral, multi-agent)

The six SDD lifecycle skills (`sdd-lifecycle`, `sdd-brainstorm`, `sdd-spec`,
`sdd-replan`, `sdd-implement`, `sdd-converge`) are **workspace-neutral**: their
bodies use `{{placeholder}}` tokens instead of any one repo's file paths or
commands, resolved at runtime from a **workspace binding** (ADR-0032).

### The binding contract — `_sdd/`
- [`binding.schema.md`](_sdd/binding.schema.md) — the 13-key vocabulary
  (`{{constitution}}`, `{{check_gate}}`, `{{test_gate}}`, `{{adr_home}}`, …), each
  with purpose + reference value + a first-run fill-prompt.
- [`binding.reference.toml`](_sdd/binding.reference.toml) — **this repo's** real
  values (the worked example; how the skills resolve when run here).
- [`binding.template.toml`](_sdd/binding.template.toml) — copy to
  `.sdd/binding.toml` in a foreign workspace and fill.
- [`FIRST_RUN.md`](_sdd/FIRST_RUN.md) — the first-run auto-adapt flow: the skill
  inspects the workspace ecosystem, **proposes** a filled binding, requires
  **human confirmation**, then persists it (never runs a guessed gate command).

### Multi-agent projection — `scripts/sync_skills.py`
The sync layer is an **adapter registry**; adding a coding agent is one entry.
Today: `claude` → `.claude/skills/` and `cursor` → `.cursor/skills/`
(byte-identical mirrors), plus `copilot` → thin
`.github/instructions/sdd-*.instructions.md` pointers (+ repo-wide
`.github/copilot-instructions.md`) that point back at the canonical `SKILL.md`,
never restating prose. Run `make skills-sync`; parity is guard-tested by
`tests/architecture/test_skills_mirror_parity.py`,
`test_sync_adapter_registry.py`, and `test_copilot_instructions_parity.py`.

### Export — `scripts/pack_skills.py`
`make skills-pack` emits `docs/skills/sdd-*.skill` — a self-contained zip per
skill (`<name>/SKILL.md` + the binding template/schema/FIRST_RUN) that drops into
any repo. `python scripts/pack_skills.py --check` guards the archives against
drift (`tests/architecture/test_skills_pack.py`).

Guards: `tests/architecture/test_sdd_portable_core.py` (no repo-token leak,
reference round-trip, skeleton preserved) + `test_sdd_binding_schema.py`
(schema↔reference complete).
