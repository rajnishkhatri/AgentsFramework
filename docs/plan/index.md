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
- [Eng-coach GCP deploy tasks](eng-coach-gcp-deploy.tasks.md) — Stage-3 red-first task list (Groups A–F, 1:1 FR→test, no zero-coverage FR): **A** D7 seed (extracts a pure `planEngineSeed({isProd,seedMode})` helper so FR-1..5 need no `NODE_ENV` flip — the plan's flagged design risk, resolved), **B** web CTA `returnTo`, **C** `/learn` link, **D** marker + the ADR-0013-shaped tombstone (green today), **E** `/learn` smoke, **F** measure-`ANALYZE` + deploy. A–D parallel; E depends on A; F last. tasks→implement gate pending Stage-4 analyze + baseline.
- [Eng-coach GCP deploy plan](eng-coach-gcp-deploy.plan.md) — Stage-2 plan (spec→plan gate PASSED): file-level touchpoints **T1–T10** — T1 prod `fresh` seed sub-branch in `composition_engine_browser.ts` (mirror non-prod, static-vs-lazy per measured `ANALYZE=true`), T3/T4 root CTA `?returnTo=/learn` threaded through `getSignInUrl({returnTo})` (bare `handleAuth` + desktop untouched), T7 one `/learn` link in chat-shell header, T8 `smoke_gcp.sh` `/learn` 307-assertion, T9 the ADR-0013-shaped durability tombstone. Frontend-ring + 2 ops files only; no infra/secret/backend change. Raises [ADR-0033](../adr/0033-coach-prod-web-seed-fresh-mode.md) + [ADR-0034](../adr/0034-coach-marker-in-memory-until-threads-bind.md). One design risk flagged for tasks (prod `NODE_ENV` test hook → maybe an injectable `isProd` seam). Plan→tasks gate pending.
- [Eng-coach GCP deploy spec (usable `/learn` slice)](eng-coach-gcp-deploy.spec.md) — Stage-2: EARS FR-1..15 (failure-first) for **D7** seed reviewed prod web corpus in `fresh` mode (FR-1 never ships Garvit demo; FR-3 taxonomy+bank+hints+lessons; FR-4 empty progress) + **web CTA `returnTo:/learn`** (FR-6/7/8, desktop untouched) + **D2** one authed `/learn` link (FR-9) + **D3** fresh redeploy (FR-10) + **`/learn` deploy proof** (FR-11/12 curl 307-to-WorkOS; FR-13 manual authed render) + **Q3 in-memory marker** fail-closed (FR-14) with an **architecture-test tombstone** enforcing the D4 time-box (FR-15). Bundle static-vs-lazy = plan decision (measure `ANALYZE=true`). Raises 2 ADRs. Spec→plan human gate pending.
- [Eng-coach GCP deploy brainstorm](eng-coach-gcp-deploy.brainstorm.md) — Stage-1 **CLOSED**: deploy the coach to GCP dev + post-login `/learn` landing; premise audit REFUTES 3/4 premises (coach already ships in `agent-frontend`; dashboard = `/learn` not `/dashboard`; sign-in is a stricter guard, not a missing button). First close (D1+D5+D3) withdrawn after a devil's-advocate review ("good brainstorm, bad close") over the blocking D0-b empty-substrate miss (prod `/learn` renders empty; on-device SQLite unbuilt/Capacitor-only); re-closed with all 5 Qs answered. Deliverable = **D7** (seed reviewed prod web corpus in `fresh` mode, no Garvit mastery) **+ web CTA `returnTo:/learn`** (D1/D6 out) **+ D2** reachability **+ D3** redeploy **+ `/learn` render smoke**; **Q3 = defer** in-memory marker (D5 out — amends ADR-0012; D4 the in-scope closer). NEXT = sdd-spec (2 ADRs).

## Layer sub-bundles

- [Adapter layer](adapter/index.md) — agent_ui_adapter plans, sprints, and implementation review.
- [Frontend layer](frontend/index.md) — frontend plans (v1–v3), sprint board/runbook, and spike reports.
- [Services layer](services/index.md) — authorization, long-term memory, and trace service plans.
- [Sprint](sprint/index.md) — phase-level sprint plans.
- [Trust layer](trust/index.md) — trust-foundation protocols plan and review.
