# Docs — knowledge bundle index

The top of the `docs/` knowledge plane, organized as OKF bundles. Each bundle has its
own `index.md` (catalog) + `log.md` (history); every Concept carries `type` frontmatter.
See the convention in [CONVENTIONS_OKF.md](CONVENTIONS_OKF.md); the whole tree is linted
by [`scripts/okf_lint.py`](../scripts/okf_lint.py).

## Knowledge & architecture

- **[Architecture documents](Architectures/index.md)** — four-layer architecture, ports/adapters deep dives, cloud deployment, trust framework, NAIC narrative.
- **[Style guides](style-guides/index.md)** — backend four-layer + frontend-ring + design-patterns style guides (the canonical code-review references).
- **[Structured reasoning](StructuredReasoning/index.md)** — Pyramid agent end-to-end sequence diagrams.
- **[Vision (mission & soul)](vision/index.md)** — the strategic mission and conviction docs.

## Guides, handbooks & contributing

- **[Developer & user guides](guides/index.md)** — developer guide, user manual, frontend validation, workspace restart.
- **[Handbooks](handbooks/index.md)** — how-to handbooks (e.g. adding an eval probe).
- **[Contributor handbooks](contributing/index.md)** — contributor-facing handbooks (e.g. adding an adapter).

## Recipes (sub-bundled)

- **[Recipes](recipes/index.md)** — the recipes bundle-of-bundles: GCP runbooks, governance (BlackBox→Langfuse), guardrails, GoalJudge, memory-extractor, plus cross-cutting recipes.

## Plans & roadmaps

- **[Project plans registry](plans/index.md)** — the flat registry of individual `.plan.md` sprint boards and design specs.
- **[Roadmap & layered plans](plan/index.md)** — high-level roadmap (PLAN / PLAN_v2) + per-layer plan sub-bundles (adapter / frontend / services / sprint / trust).

## Validation, reviews & analysis

- **[GoalJudge validation walkthroughs](walk-through/index.md)** — step-by-step manual validation procedures.
- **[Deployment walkthroughs](deploy/index.md)** — authenticated deploy + memory-run walkthroughs.
- **[Explainability UI & tracing](explainability/index.md)** — end-to-end tracing guides + UI sprint reviews.
- **[Code reviews & governance audits](reviews/index.md)** — phase code reviews, AGENTS.md reviews, and governance-audit artifacts.
- **[Analyses & reports](analysis/index.md)** — pyramid analyses, cloud comparison, AGENTS.md research, marketing/DD report.

## Out of scope (generated / evidence)

The following are generated or ephemeral artifacts, **not** authored knowledge bundles, and
are intentionally left out of the OKF convention (see the EXCLUDED section in
[CONVENTIONS_OKF.md](CONVENTIONS_OKF.md)): `docs/research/`, `docs/reports/`,
`docs/test-reports/`, `docs/IAA/`, `docs/amp/`, `docs/drift/`.

> The `research/` design-prompt bundle that **is** declared lives at the repo root
> (`research/`), not under `docs/`.
