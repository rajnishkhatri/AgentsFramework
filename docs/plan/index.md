# Roadmap & layered plans — bundle index

OKF bundle. Each entry is a typed Concept. See the convention in [CONVENTIONS_OKF.md](../CONVENTIONS_OKF.md).

## Roadmap documents

- [ReAct Agent with Dynamic Model Selection](PLAN.md) — The system is organized as a three-layer grid following the composable layering architecture.
- [ReAct Agent with Dynamic Model Selection -- v2](PLAN_v2.md) — The system is organized as a four-layer grid.
- [Trust framework and governance](TRUST_FRAMEWORK_AND_GOVERNANCE.md) — The seven-layer trust framework and its governance model.

## Subject-Coach program (brainstorm → spec → implementation plan)

- [Subject-Coach agent brainstorm](subject-coach-agent.brainstorm.md) — divergence/convergence record behind the governed ReAct coach.
- [Subject-Coach agent spec](subject-coach-agent.spec.md) — FR-1..28, the testable *what* of the coach + judges plane.
- [Subject-Coach implementation plan](subject-coach-agent.plan.md) — 6-phase build order (§11) with TDD-pyramid binding, per-phase review gates, and the living status ledger.
- [Coach Test Mode governed plane spec](coach-test-mode-governed-plane.spec.md) — Phase 6: authors FR-23..27 in EARS (test-item cascade with the solver key gate, TestBlueprint + deterministic seeded assembler, seed importer, reviewed-only selection); pairs with [ADR-0015](../adr/0015-subject-coach-test-item-bank-blueprint-read-seam.md).
- [Coach learning-analytics brainstorm](coach-learning-analytics.brainstorm.md) — Stage-1: a third signal plane (learner behavior/experience/feedback events) for coach + test mode, RL-trajectory-ready; premise audit, D0 `elapsed_ms` defect, directions D1–D6, gate CLOSED.
- [Coach learning-analytics spec (D1)](coach-learning-analytics.spec.md) — Stage-2 (rev-2): EARS spec for the `learning_event` table + 12th engine port (`LearningEventRepo`, append+scoped-read) + three-call-site emit + episode boundaries; C1 resolved (`run_ref`=`trace_id` + offline crosswalk), C3 corrected (applies `AttemptRepo` precedent). Review B1–B3/H1–H5/M1–M6 applied (subject OCP col, discriminated payload, step_index, minting authority). D0 out-of-scope (landed). Raises ADR-0016.
- [Coach learning-analytics plan (D1)](coach-learning-analytics.plan.md) — Stage-3: architecture plan + 16 file-level touchpoints (T1–T16) mirroring the `AttemptRepo` vertical slice (wire→schema both dialects→`EngineDb` two impls→port→repo→composition→conformance→3 emit sites + server `task_id` crosswalk); dependency-ordered build; surfaces R1 (coach client hardcodes `trace_id:"no-trace"` — blocking for coach attribution). plan→tasks gate pending.

## Layer sub-bundles

- [Adapter layer](adapter/index.md) — agent_ui_adapter plans, sprints, and implementation review.
- [Frontend layer](frontend/index.md) — frontend plans (v1–v3), sprint board/runbook, and spike reports.
- [Services layer](services/index.md) — authorization, long-term memory, and trace service plans.
- [Sprint](sprint/index.md) — phase-level sprint plans.
- [Trust layer](trust/index.md) — trust-foundation protocols plan and review.
