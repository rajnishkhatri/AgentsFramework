# Roadmap & layered plans — bundle index

OKF bundle. Each entry is a typed Concept. See the convention in [CONVENTIONS_OKF.md](../CONVENTIONS_OKF.md).

## PreACT UI parity (Epic A + B)

- [Epic A + B post-merge review](epic-a-b-post-merge-review.md) — FR inventory + validation matrix for PR #140 / #141.
- [Epic A + B manual UI validation report](epic-a-b-manual-validation-report.md) — 2026-07-10 Steps 1–15 walkthrough results, A0 gap, FLAG-1/4/5/6.
- [Epic A/B continuity fixes spec](epic-ab-continuity-fixes.spec.md) — FLAG-1/4/6 + Reveal polish (FLAG-5 → Epic C0).
- [Epic A/B continuity fixes plan](epic-ab-continuity-fixes.plan.md) — Approved 2026-07-10.
- [Epic A/B continuity fixes tasks](epic-ab-continuity-fixes.tasks.md) — Stage 6 implement (P1–P9 / Groups A–E).

## Roadmap documents

- [ReAct Agent with Dynamic Model Selection](PLAN.md) — The system is organized as a three-layer grid following the composable layering architecture.
- [ReAct Agent with Dynamic Model Selection -- v2](PLAN_v2.md) — The system is organized as a four-layer grid.
- [Trust framework and governance](TRUST_FRAMEWORK_AND_GOVERNANCE.md) — The seven-layer trust framework and its governance model.

## Subject-Coach program (brainstorm → spec → implementation plan)

- [Subject-Coach agent brainstorm](subject-coach-agent.brainstorm.md) — divergence/convergence record behind the governed ReAct coach.
- [Subject-Coach agent spec](subject-coach-agent.spec.md) — FR-1..28, the testable *what* of the coach + judges plane.
- [Subject-Coach implementation plan](subject-coach-agent.plan.md) — 6-phase build order (§11) with TDD-pyramid binding, per-phase review gates, and the living status ledger.
- [Coach Test Mode governed plane spec](coach-test-mode-governed-plane.spec.md) — Phase 6: authors FR-23..27 in EARS (test-item cascade with the solver key gate, TestBlueprint + deterministic seeded assembler, seed importer, reviewed-only selection); pairs with [ADR-0015](../adr/0015-subject-coach-test-item-bank-blueprint-read-seam.md).
- [Coach gold set + enable-policy spec](coach-goldset-enable-policy.spec.md) — Phase 3: EARS spec for §12.1–12.6 (posture checker, coding export, human coding gates, rubric revision, `coach_goldset_v1`, `evaluate_coach_enable_gates`); closes ADR-0008 cond#1. Clarify CLOSED + critical review 2026-07-03 (C9–C12) + Stage-4 cross-check (6 missing tests + 3.7b deps). Pairs with [plan](coach-goldset-enable-policy.plan.md) + [tasks](coach-goldset-enable-policy.tasks.md).
- [Coach learning-analytics brainstorm](coach-learning-analytics.brainstorm.md) — Stage-1: a third signal plane (learner behavior/experience/feedback events) for coach + test mode, RL-trajectory-ready; premise audit, D0 `elapsed_ms` defect, directions D1–D6, gate CLOSED.
- [Coach learning-analytics spec (D1)](coach-learning-analytics.spec.md) — Stage-2 (rev-2): EARS spec for the `learning_event` table + 12th engine port (`LearningEventRepo`, append+scoped-read) + three-call-site emit + episode boundaries; C1 resolved (`run_ref`=`trace_id` + offline crosswalk), C3 corrected (applies `AttemptRepo` precedent). Review B1–B3/H1–H5/M1–M6 applied (subject OCP col, discriminated payload, step_index, minting authority). D0 out-of-scope (landed). Raises ADR-0016.
- [Coach learning-analytics plan (D1)](coach-learning-analytics.plan.md) — Stage-3: architecture plan + 16 file-level touchpoints (T1–T16) mirroring the `AttemptRepo` vertical slice (wire→schema both dialects→`EngineDb` two impls→port→repo→composition→conformance→3 emit sites + server `task_id` crosswalk); dependency-ordered build; surfaces R1 (coach client hardcodes `trace_id:"no-trace"` — blocking for coach attribution). plan→tasks gate CLOSED (R1 recommended approach confirmed).
- [Coach learning-analytics tasks (D1)](coach-learning-analytics.tasks.md) — Stage-3: red-first atomic checklist (Groups A–J) decomposing T1–T16 into failing-test-first units against real precedent signatures (`Attempt`/`AttemptInput`, `DrizzleAttemptRepo` deps, `EngineDb.insertAttempt`, `EnginePortBag`); R1 threaded into G4a (real coach `trace_id`, NULL `run_ref` never the sentinel). tasks→implement gate pending (ADR-0016 draft first).
- [Coach learning-analytics design (D1)](coach-learning-analytics.design.md) — the FR → realizing-structure → task-group map (was spec §10, split out): one row per FR-1.1..FR-4.1 binding each acceptance criterion to the concrete engine-plane structure (Zod entity, dialect tables, `EngineDb` methods, emit sites, `task_id` detail) + the precedent applied + touchpoint + task group; asserts no zero-coverage FR. The join between spec (`what`), plan (architecture T1–T16), and tasks (RED→GREEN A–J); governed by [ADR-0016](../adr/0016-subject-coach-learning-event-append-plane.md).

## Layer sub-bundles

- [Adapter layer](adapter/index.md) — agent_ui_adapter plans, sprints, and implementation review.
- [Frontend layer](frontend/index.md) — frontend plans (v1–v3), sprint board/runbook, and spike reports.
- [Services layer](services/index.md) — authorization, long-term memory, and trace service plans.
- [Sprint](sprint/index.md) — phase-level sprint plans.
- [Trust layer](trust/index.md) — trust-foundation protocols plan and review.
