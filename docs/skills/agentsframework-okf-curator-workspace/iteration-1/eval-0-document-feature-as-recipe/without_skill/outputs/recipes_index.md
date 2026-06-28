# Recipes — knowledge bundle index

The recipes knowledge plane, organized as OKF sub-bundles. See the convention in [CONVENTIONS_OKF.md](../CONVENTIONS_OKF.md).

## Sub-bundles

- **[GCP deployment runbooks](gcp/index.md)** — 16 runbooks: adapters → foundations → data → containerize → Cloud Run → observability → cleanup, plus live-deploy + log-pipeline guides.
- **[Governance — BlackBox → Langfuse](governance/index.md)** — 9 Concepts: the flight-recorder overview, outbox-relay / event-mapping / compliance-dataset specs, and end-to-end validation walkthroughs.
- **[Guardrails — 5-rail safety](guardrails/index.md)** — 10 Concepts: the dimension-space and prompt/pre-check specs, the synthetic-dataset + classifier + CI-gate recipes, and validation walkthroughs.
- **[GoalJudge evaluation](goaljudge/index.md)** — 3 Concepts: grounded-judging overview, the axial-coding failure taxonomy, and the Stage 4 A2 rubric.
- **[Memory extractor evaluation](memory_extractor/index.md)** — 4 Concepts: failure taxonomy, gold-set spec, the autocapture enable-policy, and the calibration runbook.

## Cross-cutting recipes

Session-spanning fixes that don't belong to a single topic sub-bundle.

- [Recipe 11 — Outcome Correctness, Real Span Nesting, and TDD Hardening](11_outcome_correctness_tdd_hardening.md) — Teach the evaluator real outcome-correctness, fix real span nesting, and harden with TDD.
- [Recipe 12 — Goal-Judge Semantics, Deterministic Span Ordering, and At-Least-Once Dedup](12_eval_judge_span_order_and_dedup.md) — Goal-Judge semantics, deterministic span ordering, and at-least-once dedup.
- [Recipe 12b — Localhost Validation Walkthrough (I2 / I6 / I8)](12b_localhost_validation_walkthrough.md) — Manually validate the I2 / I6 / I8 fixes against a localhost run.
- [Recipe 13 — The Gate That Only Ever Says Yes](13_negative_path_traces_and_schema_versioning.md) — Close trace-gap items G4/G7/G8 — negative-path traces and bundle schema versioning.
- [Recipe 14 — The Recording With No Chapters](14_phaselogger_reasoning_pillar_wiring.md) — Wire the PhaseLogger Reasoning pillar so the black box records a timeline of reasoning phases.
- [Recipe 15 — The Posture Nobody Could Flip](15_goaljudge_runtime_config_toggle.md) — Give operators a true runtime toggle for the GoalJudge evaluation posture.
- [Recipe 16 — Adding and Linting an OKF Knowledge Bundle](16_okf_bundle_lint.md) — Declare a directory as an OKF knowledge bundle and keep the docs tree linting clean.
