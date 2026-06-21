---
type: review
title: 'Sprint 1 + Sprint 2 Explainability UI Recommendation Report'
description: 'This report evaluates the Sprint 1 and Sprint 2 explainability implementation against docs/explainability/EXPLAINABILITY_UI_SPRINT_BOARD.md, repository architecture rules, and the'
tags: [explainability]
---

# Sprint 1 + Sprint 2 Explainability UI Recommendation Report

This report evaluates the Sprint 1 and Sprint 2 explainability implementation against `docs/explainability/EXPLAINABILITY_UI_SPRINT_BOARD.md`, repository architecture rules, and the structured analysis protocol in `research/pyramid_react_system_prompt.md`.

```yaml
analysis_output:

  problem_definition:
    original_statement: "Validate Sprint 1 and Sprint 2 implementation quality, identify gaps, and create a recommendation report."
    restated_question: "Do Sprint 1 and Sprint 2 of the explainability dashboard meet their functional, architectural, security/trust, and testing acceptance criteria, and what implementation gaps should be corrected before the next sprint or merge?"
    problem_type: "evaluation"
    scope_boundaries: "In scope: Sprint 1 Trace Timeline, Decision Audit, Dashboard; Sprint 2 Guardrail Monitor and Agent Registry; backend service/API/wire implementation; frontend wire/port/adapter/translators/routes/components; focused tests and architecture gates. Out of scope: Sprints 3-4 feature implementation, live LLM/runtime behavior, unrelated middleware and agent_ui_adapter branch failures except as merge-readiness risks."
    success_criteria: "Sprint 1 and Sprint 2 ACs are functionally satisfied, explainability-specific architecture tests pass, frontend/backed focused test suites pass, wire drift is controlled, and all material quality gaps are documented with actionable recommendations."

  issue_tree:
    root_question: "Are Sprint 1 and Sprint 2 implementation quality and readiness sufficient for continuation into Sprint 3?"
    ordering_type: "structural"
    branches:
      - id: "branch_1"
        label: "Functionality"
        question: "Do the delivered modules satisfy the Sprint 1 and Sprint 2 feature ACs?"
        hypothesis: "All Sprint 1 and Sprint 2 modules are functionally complete for the local-only MVP."
        hypothesis_status: "confirmed_with_gaps"
        evidence_ids: ["ev_1", "ev_2", "ev_3", "ev_4", "ev_5", "ev_6", "ev_7"]
        sub_branches: []
      - id: "branch_2"
        label: "Architecture"
        question: "Does the implementation preserve backend/frontend layering, read-only semantics, and wire isolation?"
        hypothesis: "The explainability stack remains properly layered and decoupled from the live agent runtime."
        hypothesis_status: "confirmed_with_low_medium_gaps"
        evidence_ids: ["ev_8", "ev_9", "ev_10", "ev_11", "ev_12", "ev_13"]
        sub_branches: []
      - id: "branch_3"
        label: "Testing"
        question: "Are the changes tested in the failure-first and contract-driven style required by the sprint board?"
        hypothesis: "Focused backend and frontend tests provide strong coverage and pass deterministically."
        hypothesis_status: "confirmed_with_gaps"
        evidence_ids: ["ev_14", "ev_15", "ev_16", "ev_17", "ev_18", "ev_19"]
        sub_branches: []
      - id: "branch_4"
        label: "Risks"
        question: "What gaps, operational risks, and merge blockers remain?"
        hypothesis: "Remaining issues are mostly hardening and merge-readiness items, not blockers for local MVP use."
        hypothesis_status: "confirmed"
        evidence_ids: ["ev_20", "ev_21", "ev_22", "ev_23", "ev_24", "ev_25"]
        sub_branches: []

  governing_thought:
    statement: "Sprint 1 and Sprint 2 are strong enough to continue into Sprint 3: the explainability stack is functionally complete for the scoped local MVP, well tested, and architecturally isolated, but it should not be merged without addressing several medium-severity hardening gaps around query propagation, error handling consistency, dev-secret semantics, style-rule drift, and unrelated repository architecture failures."
    confidence: 0.89

  key_arguments:
    - id: "arg_1"
      statement: "The Sprint 1 and Sprint 2 user-facing modules are substantially complete against the board's acceptance criteria."
      dimension: "Functionality"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_1", "ev_2", "ev_3", "ev_4", "ev_5", "ev_6", "ev_7"]
      confidence: 0.92
      so_what_chain:
        - level: "fact"
          statement: "Trace events, decisions, dashboard metrics, guardrail summary, and agent registry data all have backend service methods, HTTP endpoints, Zod wire shapes, adapter methods, and UI routes/components."
        - level: "impact"
          statement: "Users can inspect timeline integrity, reasoning decisions, aggregate KPIs, validation behavior, and registered identities through the new dashboard."
        - level: "implication"
          statement: "The implementation meets the core MVP explainability objective: making governance artifacts inspectable without invoking the live runtime."
        - level: "connection"
          statement: "This supports continuing into Sprint 3 while treating the remaining issues as targeted hardening."

    - id: "arg_2"
      statement: "The explainability-specific architecture holds, but a few design choices create avoidable brittleness."
      dimension: "Architecture"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_8", "ev_9", "ev_10", "ev_11", "ev_12", "ev_13"]
      confidence: 0.84
      so_what_chain:
        - level: "fact"
          statement: "Explainability layering tests and frontend architecture tests pass, and the agents router is proven read-only by reflection."
        - level: "impact"
          statement: "The new stack does not import orchestration/runtime code, and the browser still talks only through the typed client port."
        - level: "implication"
          statement: "The main layering goal is achieved, but private registry-field access, dev-secret fallback behavior, and a server query mismatch should be cleaned up."
        - level: "connection"
          statement: "Architecture quality is good enough for MVP, but not perfect enough to leave untracked."

    - id: "arg_3"
      statement: "Test coverage is broad and failure-oriented, but some acceptance wording is not matched exactly."
      dimension: "Testing"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_14", "ev_15", "ev_16", "ev_17", "ev_18", "ev_19"]
      confidence: 0.88
      so_what_chain:
        - level: "fact"
          statement: "Focused backend tests pass 67/67, frontend tests pass 168/168, and lint/typecheck/frontend architecture gates are clean."
        - level: "impact"
          statement: "Regression confidence is high for implemented contracts."
        - level: "implication"
          statement: "Residual testing gaps are mostly strictness issues: Hypothesis was requested but approximated, snapshots are behavioral render tests, and some 500 paths are not directly exercised."
        - level: "connection"
          statement: "Quality is strong, but the test suite should be tightened before relying on it as a formal AC audit trail."

    - id: "arg_4"
      statement: "Remaining risks are manageable if addressed before merge or during the next hardening pass."
      dimension: "Risks"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_20", "ev_21", "ev_22", "ev_23", "ev_24", "ev_25"]
      confidence: 0.82
      so_what_chain:
        - level: "fact"
          statement: "The full repository architecture suite still fails due to unrelated middleware and adapter-radius issues, and the explainability implementation inherits the Sprint 1 O(N) filesystem scan model."
        - level: "impact"
          statement: "Merge readiness is blocked at the repository level even though focused explainability gates pass."
        - level: "implication"
          statement: "The next action should split true explainability follow-ups from unrelated branch cleanup."
        - level: "connection"
          statement: "The sprint is implementation-ready but not branch-merge-ready until repository-level gates are handled."

  evidence:
    - id: "ev_1"
      fact: "Sprint 1 service methods exist for workflow events, decisions, and dashboard metrics: get_workflow_events(), get_workflow_decisions(), and get_dashboard_metrics()."
      source: "services/explainability_service.py source inspection"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 1.0
    - id: "ev_2"
      fact: "Sprint 1 endpoints exist for /api/v1/workflows/{wf_id}/events, /api/v1/workflows/{wf_id}/decisions, and /api/v1/dashboard/metrics."
      source: "explainability_app/server.py source inspection"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 1.0
    - id: "ev_3"
      fact: "Sprint 1 frontend has Trace Timeline, Decision Audit, Dashboard routes/components and translators, including eventsToTimeline() covering all nine EventType values."
      source: "frontend-explainability app/components/lib inspection"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 0.95
    - id: "ev_4"
      fact: "Sprint 2 Guardrail Monitor is implemented end-to-end: service get_guardrail_summary(), endpoint /api/v1/guardrails/summary, GuardrailsPage, ValidatorTable, ActionDistributionPie, RecentFailuresTable, and pure action_distribution translator."
      source: "services/explainability_service.py, explainability_app/server.py, frontend-explainability/app/guardrails/page.tsx, frontend-explainability/components/guardrails/*"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 1.0
    - id: "ev_5"
      fact: "Sprint 2 Agent Registry is implemented end-to-end: list_agents(), get_agent_card(), get_agent_audit(), three GET endpoints, /agents catalog route, /agents/[agent_id] detail route, IdentityCard, AgentCatalog, and AuditTimeline."
      source: "services/explainability_service.py, explainability_app/server.py, frontend-explainability/app/agents/*, frontend-explainability/components/agents/*"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 1.0
    - id: "ev_6"
      fact: "AgentCard intentionally excludes signature_hash and exposes signature_truncated plus signature_verified computed server-side."
      source: "services/explainability_service.py AgentCard/get_agent_card and tests/services/test_explainability_service.py"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 1.0
    - id: "ev_7"
      fact: "Dev seed now registers cli-agent and dev-agent so the local Agent Registry page can show sample identities."
      source: "explainability_app/dev_seed.py and tests/explainability_app/test_dev_seed.py"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 0.95
    - id: "ev_8"
      fact: "tests/architecture/test_explainability_layering.py passed, confirming services/explainability_service.py has no forbidden imports from components, orchestration, middleware, agent_ui_adapter, or frontend projects."
      source: "pytest tests/architecture/test_explainability_layering.py tests/architecture/test_agents_router_read_only.py -v"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 1.0
    - id: "ev_9"
      fact: "tests/architecture/test_agents_router_read_only.py passed and reflects on _build_agents_router() to assert zero POST/PUT/PATCH/DELETE routes."
      source: "pytest tests/architecture/test_agents_router_read_only.py"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 1.0
    - id: "ev_10"
      fact: "frontend-explainability test:arch passed 4/4 across no-cross-project imports, layering, and port conformance."
      source: "npm run test:arch"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 1.0
    - id: "ev_11"
      fact: "Wire drift test maps 11 Python Pydantic response shapes to Zod mirrors and passed 33 assertions."
      source: "frontend-explainability/lib/wire/baseline_drift.test.ts and npm test output"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 1.0
    - id: "ev_12"
      fact: "ExplainabilityService.list_agents() reaches into AgentFactsRegistry._storage_dir, a private implementation detail."
      source: "services/explainability_service.py source inspection"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 1.0
    - id: "ev_13"
      fact: "HttpExplainabilityClient.listWorkflows(since) sends a since query parameter, but the FastAPI /api/v1/workflows endpoint currently does not accept or forward since."
      source: "frontend-explainability/lib/adapters/http_explainability_client.ts and explainability_app/server.py source inspection"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 1.0
    - id: "ev_14"
      fact: "Focused backend Sprint 1/2 gates passed: 67 tests passed across services, explainability_app, explainability layering, and agents read-only architecture tests."
      source: "pytest tests/services/test_explainability_service.py tests/explainability_app/ tests/architecture/test_explainability_layering.py tests/architecture/test_agents_router_read_only.py -q"
      assigned_to: "arg_3"
      branch_id: "branch_3"
      confidence: 1.0
    - id: "ev_15"
      fact: "Frontend quality gates passed: typecheck, lint, test:arch, and 168 Vitest tests across 17 files."
      source: "cd frontend-explainability && npm run typecheck && npm run lint && npm run test:arch && npm test"
      assigned_to: "arg_3"
      branch_id: "branch_3"
      confidence: 1.0
    - id: "ev_16"
      fact: "Failure-first backend tests cover unknown workflow, tampered chain, empty decisions, zero dashboard metrics, zero guardrail events, corrupted guardrail JSONL, unknown agent, 405 mutation methods, and dev_seed idempotency."
      source: "tests/services/test_explainability_service.py, tests/explainability_app/test_server.py, tests/explainability_app/test_dev_seed.py"
      assigned_to: "arg_3"
      branch_id: "branch_3"
      confidence: 0.95
    - id: "ev_17"
      fact: "Frontend adapter tests cover 404, 500, network rejection, and Zod parse errors for the main client methods."
      source: "frontend-explainability/lib/adapters/http_explainability_client.test.ts"
      assigned_to: "arg_3"
      branch_id: "branch_3"
      confidence: 0.95
    - id: "ev_18"
      fact: "Sprint 2 guardrail property testing was implemented as a deterministic enumeration, not as a Hypothesis property test requested by the sprint board."
      source: "tests/services/test_explainability_service.py"
      assigned_to: "arg_3"
      branch_id: "branch_3"
      confidence: 1.0
    - id: "ev_19"
      fact: "Some ACs that say 'snapshot test' are implemented as behavioral render assertions rather than actual snapshots."
      source: "frontend-explainability/components/agents/IdentityCard.test.tsx and related component tests"
      assigned_to: "arg_3"
      branch_id: "branch_3"
      confidence: 0.9
    - id: "ev_20"
      fact: "Full repository architecture suite failed 3 tests unrelated to the explainability stack: middleware imports components/orchestration and mphase2 swap-radius detects agent_ui_adapter files changed with service files."
      source: "pytest tests/architecture/ -q"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 1.0
    - id: "ev_21"
      fact: "ActionDistributionPie uses CSS variable fallbacks with hardcoded hex colors."
      source: "rg '#[0-9a-fA-F]{3,6}' frontend-explainability and frontend-explainability/components/guardrails/ActionDistributionPie.tsx"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 1.0
    - id: "ev_22"
      fact: "IdentityCard and several UI strings introduced non-ASCII glyphs such as check/cross marks and arrow symbols."
      source: "frontend-explainability/components/agents/IdentityCard.tsx and app routes source inspection"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 0.9
    - id: "ev_23"
      fact: "build_app() falls back to DEV_SEED_AGENT_FACTS_SECRET whenever cache/agent_facts exists and AGENT_FACTS_SECRET is absent."
      source: "explainability_app/server.py _try_build_agent_facts_registry"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 1.0
    - id: "ev_24"
      fact: "Sprint 1 and Sprint 2 aggregation methods continue the O(N) synchronous filesystem scan/re-hash pattern from Sprint 1."
      source: "services/explainability_service.py get_dashboard_metrics(), get_guardrail_summary(), list_agents()"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 1.0
    - id: "ev_25"
      fact: "Most server endpoints rely on the global exception handler for 500 behavior, while list_workflows and guardrails/summary have explicit structured 500 wrappers."
      source: "explainability_app/server.py source inspection"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 0.95

  gaps:
    untested_hypotheses:
      - branch_id: "branch_1"
        hypothesis: "Manual browser smoke testing confirms the rendered Sprint 1 and Sprint 2 pages behave correctly with live seeded data."
        reason: "This review did not launch the backend/frontend servers or perform browser-driven UI smoke testing."
        impact_on_confidence: "Medium: automated component and adapter tests are strong, but live browser layout/interaction was not revalidated."
      - branch_id: "branch_3"
        hypothesis: "All documented 'snapshot' ACs are literally implemented as snapshot tests."
        reason: "Tests verify behavior and DOM attributes, but some are not snapshot assertions."
        impact_on_confidence: "Low: behavioral assertions are often better than brittle snapshots, but the sprint-board wording is not strictly satisfied."
      - branch_id: "branch_3"
        hypothesis: "Guardrail pass/fail invariant is covered with Hypothesis as requested."
        reason: "The test uses deterministic enumeration instead of Hypothesis."
        impact_on_confidence: "Low to medium: the behavior is tested, but not with the requested property-test tool."
    missing_data:
      - description: "No performance benchmark over realistic cache sizes was run."
        would_affect: "Scalability risk severity for dashboard and guardrail aggregation."
      - description: "No bundle-size or first-load JS measurement was run for the additional Recharts pie component."
        would_affect: "Frontend performance recommendation for dynamic chart imports."
      - description: "No live browser accessibility scan was run."
        would_affect: "Confidence in FD4 accessibility compliance beyond static/component assertions."
    known_weaknesses:
      - description: "HttpExplainabilityClient.listWorkflows(since) sends a since parameter that the server does not read."
        severity: "medium"
      - description: "Sprint 1 Timeline uses a DOM bar list instead of the Visx waterfall named in the board."
        severity: "medium"
      - description: "get_workflow_decisions() reads phase-log JSONL directly instead of wrapping PhaseLogger.export_workflow_log(wf_id) as the board specifies."
        severity: "medium"
      - description: "Guardrail aggregation silently skips guardrail_checked events with missing or invalid timestamps."
        severity: "medium"
      - description: "Backend Pydantic wire models lack direct Protocol A valid/invalid schema tests."
        severity: "medium"
      - description: "ActionDistributionPie has hardcoded hex color fallbacks inside CSS variable expressions."
        severity: "medium"
      - description: "AgentFactsRegistry is accessed through its private _storage_dir field."
        severity: "medium"
      - description: "DEV_SEED_AGENT_FACTS_SECRET fallback can mislabel non-dev local registries as not verified when AGENT_FACTS_SECRET is absent."
        severity: "medium"
      - description: "frontend-explainability declares @tanstack/react-query but the current Sprint 1/2 UI does not import it."
        severity: "low"
      - description: "dev_seed.py hardcodes model names for seed data, which creates minor friction with the repository's H2 model-tier convention."
        severity: "low"
      - description: "Full repository architecture suite fails on unrelated branch changes."
        severity: "high_for_merge_readiness"
      - description: "O(N) synchronous filesystem scans and repeated hash-chain verification remain the main scaling risk."
        severity: "medium"

  cross_branch_interactions:
    - branches: ["branch_1", "branch_4"]
      interaction: "Functional success depends on read latency remaining acceptable; the same O(N) scan pattern that makes the MVP simple will eventually degrade Dashboard, Guardrails, and Agent Registry user experience."
    - branches: ["branch_2", "branch_3"]
      interaction: "Architecture is backed by tests, but some architectural expectations are only proven for explainability-specific paths; full-repo architecture failures still block merge-readiness."
    - branches: ["branch_2", "branch_4"]
      interaction: "The dev-secret fallback is a local usability improvement, but it also weakens trust semantics by conflating 'wrong or missing verification secret' with 'signature failed'."

  validation_log:
    - check: "completeness"
      result: "pass"
      details: "Functionality, architecture, testing, and risks cover the Sprint 1/2 quality decision."
    - check: "non_overlap"
      result: "pass"
      details: "Evidence was partitioned by primary implication: feature completeness, structural compliance, test quality, or residual risk."
    - check: "item_placement"
      result: "pass"
      details: "ev_13 fits architecture contract mismatch; ev_18 fits test-quality gap; ev_21 fits residual frontend style/security risk."
    - check: "so_what"
      result: "pass"
      details: "Each evidence item chains to either readiness, architectural confidence, testing confidence, or hardening recommendations."
    - check: "vertical_logic"
      result: "pass"
      details: "The four arguments directly answer whether Sprint 1/2 are ready and what remains."
    - check: "remove_one"
      result: "pass"
      details: "Removing functionality, architecture, testing, or risk weakens the conclusion, but the remaining arguments still support continuing with targeted remediation."
    - check: "never_one"
      result: "pass"
      details: "Issue tree has four peer branches and no single-child branches."
    - check: "mathematical"
      result: "pass"
      details: "Test counts and pass/fail totals cited from command outputs; no independent arithmetic model beyond those counts."

  metadata:
    problem_scope: "Sprint 1 + Sprint 2 explainability UI implementation quality review."
    tools_used: ["ReadFile", "Shell", "rg", "Subagent"]
    iteration_count: 1
    reasoning_trace_summary: "Decomposed the review into Functionality, Architecture, Testing, and Risks. Focused gates confirmed explainability implementation quality; static inspection identified medium-severity hardening gaps. Full architecture suite failure was separated as an unrelated branch-level merge blocker."
    communication_tone: "standard"
    presentation_notes:
      - "Overall implementation quality is high; most recommendations are cleanup/hardening, not feature blockers."
      - "The most important pre-merge risk is outside Sprint 1/2: full repository architecture tests still fail due to unrelated middleware and adapter-radius changes."
      - "The highest-value explainability fix is the listWorkflows(since) server mismatch because it is an actual client/server contract drift."
```

## Recommendation Backlog

### P0 — Merge Readiness

1. Resolve the full repository architecture failures before merging:
  - `middleware/__main__.py imports components`
  - `middleware/__main__.py imports orchestration`
  - `test_mphase2_swap_radius.py` detects changed `agent_ui_adapter/` files alongside service files

These are outside the explainability implementation, but they block a clean repository-level quality gate.

### P1 — Explainability Contract Corrections

1. Add `since: datetime | None = Query(None)` to `GET /api/v1/workflows` and pass it through to `service.list_workflows(since=since)`.
  - Why: the frontend adapter already supports `listWorkflows(since)`, but the backend ignores the query parameter.
  - Add an HTTP test that `since` filters out older workflows.
2. Either implement the Visx waterfall named in S1.1.2 or amend the sprint board to accept the current DOM bar-list timeline.
  - Why: the current `Timeline` implementation is functional and tested, but the written AC explicitly says Visx waterfall.
  - If the DOM timeline is the intended lean MVP, make that a documented product decision instead of an implicit spec drift.
3. Align `get_workflow_decisions()` with `PhaseLogger.export_workflow_log(wf_id)`.
  - Why: the sprint board says the service should wrap the PhaseLogger export method.
  - Recommended fix: call `PhaseLogger(...).export_workflow_log(wf_id)` and then map dicts into `DecisionRecord`, or document the current direct JSONL parser as an intentional extension that adds corrupted-line resilience.
4. Decide and test the missing-timestamp rule for guardrail events.
  - Current behavior: `_aggregate_guardrails_window()` skips a `guardrail_checked` event entirely if its timestamp is missing or invalid.
  - Recommended fix: either include it in all-time aggregations with `timestamp=None`, or keep skipping but add an explicit failure-path test and report note.
5. Standardize endpoint 500 handling.
  - Why: `list_workflows` and `guardrails/summary` explicitly return structured 500s; several other endpoints rely on the global handler.
  - Add failure-first HTTP tests for `events`, `decisions`, `dashboard/metrics`, and `agents` service exceptions.
6. Replace private `AgentFactsRegistry._storage_dir` access with a public read API.
  - Preferred fix: add a `list_agent_ids()` or `list_all()` method to `AgentFactsRegistry`.
  - Alternative: pass `agent_facts_dir` explicitly into `ExplainabilityService` instead of introspecting the registry object.

### P1 — Trust and Security Semantics

1. Refine dev-seed secret fallback.
  - Current behavior: if `cache/agent_facts/` exists and `AGENT_FACTS_SECRET` is absent, the API uses `DEV_SEED_AGENT_FACTS_SECRET`.
  - Risk: real local facts signed with another secret will be reported as not verified instead of "verification unavailable due missing secret."
  - Recommended fix: write/read a dev-seed marker file, or require an explicit `EXPLAINABILITY_ALLOW_DEV_SEED_SECRET=1`.
2. Distinguish verification states in `AgentCard`.
  - Current field: `signature_verified: bool`.
  - Recommended field: `signature_verification_status: "verified" | "failed" | "unavailable"`.
  - Keep `signature_verified` if needed for UI convenience, but do not collapse "wrong secret", "missing secret", and "tampered signature" into the same boolean.

### P2 — Frontend Style and Accessibility Hardening

1. Remove or wire up the unused `@tanstack/react-query` dependency.
  - Why: it is declared in `frontend-explainability/package.json` but not imported in the Sprint 1/2 implementation.
  - This is low severity but useful cleanup for the "minimal allowlist" intent.
2. Remove hardcoded hex color fallbacks from `ActionDistributionPie`.
  - Current pattern: `var(--color-kpi-red, #dc2626)`.
  - Recommended pattern: use only theme tokens or CSS variables without hardcoded fallback.
3. Replace non-ASCII glyph text with ASCII text or accessible icon components.
  - Current examples: check/cross verification marks and arrow glyphs.
  - This is a low-severity style consistency issue, but the workspace editing convention defaults to ASCII unless clearly justified.
4. Correct stale component comments.
  - Example: `Timeline.tsx` describes itself as a Server Component, but it is consumed under a client boundary.
  - This is not a runtime bug, but it can mislead future architecture reviews.
5. Add a lightweight accessibility smoke pass for Sprint 2 pages.
  - Suggested scope: `/guardrails`, `/agents`, `/agents/[agent_id]`.
  - Focus: label association, keyboard focus, table semantics, and chart fallback text.

### P2 — Test Alignment

1. Convert the guardrail invariant test to Hypothesis.
  - The deterministic enumeration is useful, but the sprint board explicitly requested Hypothesis for `pass_rate + fail_rate ≈ 1`.
2. Add direct Pydantic wire-model tests for `explainability_app/wire/responses.py`.
  - Why: the sprint board calls for Protocol A valid/invalid shape tests on the Python wire kernel.
  - Current coverage is strong through endpoint tests and frontend drift checks, but not direct L1 schema tests.
3. Decide whether "snapshot" ACs require literal snapshots.
  - If yes, add snapshots for identity statuses and KPI threshold states.
  - If no, amend the sprint board convention to allow deterministic render assertions as an equivalent signal.
4. Add a server-side regression test for `list_workflows(since)`.
  - This should accompany the P1 contract correction.
5. Reconcile the CORS acceptance wording.
  - The board says disallowed origins return 403, while Starlette CORS behavior generally omits `Access-Control-Allow-Origin` rather than returning 403.
  - Either add explicit origin-rejection middleware if 403 is required, or amend the board to match standard CORS semantics.

### P2 — Dev Seed Hygiene

1. Move seed-only model names behind an explicit seed constant or tier-derived helper.
  - `dev_seed.py` currently hardcodes model names for visual sample data.
  - Low severity because it is dev-only, but documenting the exception avoids H2 review friction.

### P2 — Performance and Scalability

1. Add a small benchmark or regression test for scan cost.
  - Scope: `get_dashboard_metrics`, `get_guardrail_summary`, and `list_agents`.
  - Target: document expected behavior at 100, 1,000, and 10,000 events.
2. Introduce a read-through cache only after measurement.
  - Cache should be keyed by file path + mtime + size so it remains local-only and does not introduce persistence concerns.
3. Consider deferring Recharts heavy imports with `next/dynamic` if bundle analysis shows first-load growth.
  - The board already flagged this as a v1.1 measurement item.

## Final Verdict

Sprint 1 and Sprint 2 are in good shape for local MVP usage and Sprint 3 continuation. The explainability implementation is feature-complete for the scoped stories, the key architecture boundaries are enforced, and the focused test suites are strong. The work should be hardened before merge by fixing the client/server `since` mismatch, tightening trust semantics around dev-seed verification, removing style-rule drift in the chart component, and resolving unrelated repository architecture failures that currently keep the full architecture suite red.