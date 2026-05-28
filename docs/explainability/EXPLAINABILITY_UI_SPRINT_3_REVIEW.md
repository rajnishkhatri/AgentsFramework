# Sprint 3 Explainability UI Implementation Review

This review evaluates the Sprint 3 implementation against
`docs/explainability/EXPLAINABILITY_UI_SPRINT_BOARD.md` and uses the structured
analysis protocol in `research/pyramid_react_system_prompt.md`.

## Findings

### F1 — JSON export is not a compliance bundle

**Severity:** High  
**Scope:** `frontend-explainability/components/compliance/ComplianceExportButtons.tsx`,
`frontend-explainability/app/compliance/page.tsx`

The `/compliance` page renders an `Export JSON Bundle` button, but the exported
JSON only contains workflow summaries plus integrity reports:

```ts
{
  generated_at,
  bundle_type: "compliance_summary",
  workflow_count,
  workflows: rows.map(({ workflow, report }) => ({
    workflow_summary: workflow,
    integrity: report,
  })),
}
```

Sprint 3's backend added a true `ComplianceBundle` with events, identity cards,
audit trails, phase decisions, and correlation health. The export label implies
that artifact, but the browser downloads a summary that omits most of the
evidence an auditor would expect.

**Risk:** Operators may believe they exported the complete four-pillar audit
bundle when they only exported a shallow summary.

**Recommendation:** Rename the current button to `Export Summary JSON`, or
preferably fetch `getWorkflowCompliance(wf_id)` for the selected/all workflows
and export the real `ComplianceBundle` payloads. Add a test asserting exported
JSON includes `correlation_health`, `events`, `identity_cards`, and
`phase_decisions`.

### F2 — "Across all workflows in range" is not implemented

**Severity:** Medium  
**Scope:** `frontend-explainability/app/compliance/page.tsx`,
`frontend-explainability/lib/ports/explainability_client.ts`,
`explainability_app/server.py`

S3.2.1 asks for "Integrity status across all workflows in range", but the page
always calls:

```ts
explainabilityClient.listWorkflows()
explainabilityClient.getGuardrailSummary()
```

No `since` / `until` values are accepted by the route, passed to the client, or
applied to integrity status. The guardrail endpoint already supports range
parameters, and `listWorkflows(since)` exists, but Compliance Center has no UI
or route-level contract to use them, and there is no `until` support for
workflow list filtering.

**Risk:** Compliance views and exports can silently include workflows outside
the intended audit window.

**Recommendation:** Add `searchParams` support to `/compliance`, a lightweight
date-range form, and client/backend support for both `since` and `until` on
workflow listing. Pass the same window to `getGuardrailSummary`. Add tests for
range inclusion/exclusion and URL query propagation.

### F3 — Compliance home introduces an N+1 hash verification path

**Severity:** Medium  
**Scope:** `frontend-explainability/app/compliance/page.tsx`,
`services/explainability_service.py`, `services/governance/black_box.py`

The page calls `listWorkflows()` once and then calls
`getWorkflowIntegrity(wf_id)` once per row. Each integrity call delegates to
`BlackBoxRecorder.export()`, which reads and re-hashes the full workflow trace.

**Risk:** The known O(N) filesystem scan risk from Sprint 1 becomes O(workflows
× trace-size) plus N HTTP requests on the Compliance home. The MVP may be fine
for small seed data, but the page will degrade quickly with large caches.

**Recommendation:** Add a batch read path such as
`GET /api/v1/compliance/summary?since=&until=` or
`service.list_workflow_integrity(...)` that computes workflow summaries and
integrity reports in one pass. Cache per-workflow integrity keyed by trace file
mtime/size if the dataset grows beyond seed scale.

### F4 — Deep-dive omits the break location from the Recording quadrant

**Severity:** Medium  
**Scope:** `services/explainability_service.py`,
`explainability_app/wire/responses.py`,
`frontend-explainability/components/compliance/WorkflowDeepDive.tsx`

`get_workflow_integrity()` exposes `broken_at_event_id`, `expected_hash`, and
`actual_hash`, but `ComplianceBundleResponse` only includes
`hash_chain_valid`. The `/compliance/[wf_id]` Recording quadrant can say
"tampered" but cannot name the broken event or show hash evidence.

**Risk:** The detail page is weaker than the home table for tampered workflows,
even though the deep dive is where an operator expects the strongest evidence.

**Recommendation:** Embed an `integrity: IntegrityReportResponse` object in
`ComplianceBundleResponse`, or add the three break-location fields directly to
the bundle. Render `broken_at_event_id` and truncated expected/actual hashes in
the Recording quadrant. Add a tampered deep-dive component test.

### F5 — Frontend component owns validation aggregation logic

**Severity:** Medium  
**Scope:** `frontend-explainability/components/compliance/WorkflowDeepDive.tsx`

`WorkflowDeepDive` derives guardrail pass/fail counts from raw events in the
React component. That is domain/data-transformation logic:

```ts
function countGuardrails(bundle: ComplianceBundle): GuardrailCounts {
  // walks bundle.events and interprets details.accepted
}
```

The frontend architecture rules prefer domain derivations outside React
components (translator/pure helper layer), keeping components presentational.

**Risk:** Behavior becomes harder to test exhaustively and easier to duplicate
when more compliance summaries are added.

**Recommendation:** Move compliance derivations into
`frontend-explainability/lib/translators/compliance_bundle.ts` with table-driven
tests: no guardrails, all pass, mixed pass/fail, malformed `accepted`, and
missing details. Keep `WorkflowDeepDive` as a renderer of translated view-models.

### F6 — A stale comment claims `Promise.allSettled` but implementation uses `Promise.all`

**Severity:** Low  
**Scope:** `frontend-explainability/app/compliance/page.tsx`

The route comment says per-workflow integrity is fetched with
`Promise.allSettled`, but the code uses `Promise.all` plus an internal
`ExplainabilityClientError` catch. That distinction matters: unexpected errors
still fail the page, and the comment overstates resilience.

**Risk:** Future maintainers may rely on a fault-isolation behavior the code
does not actually provide.

**Recommendation:** Either update the comment or switch to real
`Promise.allSettled` and preserve per-workflow failure metadata for the table
and export.

## Recommendations by Priority

1. **Fix export semantics first.** Either rename the current JSON export or
  export true `ComplianceBundle` payloads. This is the highest user-facing
   mismatch.
2. **Add range support.** Introduce `since`/`until` query handling for
  Compliance Center, wire it into workflow listing and guardrail summary, and
   test inclusion/exclusion.
3. **Batch integrity reads.** Replace the per-row N+1 endpoint calls with one
  service/API method before seed data grows.
4. **Promote compliance derivations into translators.** Move guardrail
  aggregation and any future quadrant summaries out of React components.
5. **Strengthen tamper evidence on the deep dive.** Surface break event and
  hash mismatch evidence where the operator drills in.
6. **Clean stale comments and test route-level behavior.** Add a mocked-client
  route test for `/compliance` and `/compliance/[wf_id]` if the current test
   harness supports RSC route rendering.

## Structured Analysis Output

```yaml
analysis_output:
  problem_definition:
    original_statement: "Review implementation of sprint 3 using research/pyramid_react_system_prompt.md; document identified gaps and recommendations to fix/improve."
    restated_question: "Does the Sprint 3 explainability implementation satisfy the compliance integrity, compliance bundle, Compliance Center, and Workflow Deep Dive acceptance criteria without material behavioral, architectural, or test gaps?"
    problem_type: "evaluation"
    scope_boundaries: "In scope: Sprint 3 backend service/endpoints/wire shapes, frontend compliance routes/components/client methods/tests, architecture and validation signals. Out of scope: implementing fixes, Sprint 4 features, authentication/RBAC, PDF export."
    success_criteria: "All Sprint 3 acceptance criteria are met, tests validate failure and acceptance paths, architecture invariants hold, and remaining gaps are non-material or explicitly documented."

  issue_tree:
    root_question: "Does Sprint 3 meet acceptance criteria and quality expectations?"
    ordering_type: "structural"
    branches:
      - id: "branch_1"
        label: "Contracts"
        question: "Do backend service methods, API endpoints, and wire schemas expose the required Sprint 3 data contracts?"
        hypothesis: "Core contracts exist and validate, but the compliance bundle omits integrity break-location details."
        hypothesis_status: "confirmed"
        evidence_ids: ["ev_1", "ev_2", "ev_3"]
        sub_branches: []
      - id: "branch_2"
        label: "Experiences"
        question: "Do the Compliance home and Workflow Deep Dive deliver the user-facing acceptance criteria?"
        hypothesis: "The views render the right broad structure, but export semantics and range filtering are incomplete."
        hypothesis_status: "confirmed"
        evidence_ids: ["ev_4", "ev_5", "ev_6"]
        sub_branches: []
      - id: "branch_3"
        label: "Architecture"
        question: "Does the implementation preserve frontend/backend layering and operational efficiency?"
        hypothesis: "Layering largely holds, but one component owns transformation logic and the page introduces N+1 integrity reads."
        hypothesis_status: "confirmed"
        evidence_ids: ["ev_7", "ev_8", "ev_9"]
        sub_branches: []
      - id: "branch_4"
        label: "Tests"
        question: "Do tests catch failure paths and acceptance behavior?"
        hypothesis: "Automated tests are green and broad, but route/export semantics leave important gaps."
        hypothesis_status: "confirmed"
        evidence_ids: ["ev_10", "ev_11", "ev_12"]
        sub_branches: []

  governing_thought:
    statement: "Sprint 3 is structurally implemented and test-green, but it should not be treated as audit-ready until export semantics, range filtering, batch integrity reads, and deep-dive tamper evidence are tightened."
    confidence: 0.84

  key_arguments:
    - id: "arg_1"
      statement: "The core backend and frontend contracts exist and pass validation, establishing a solid Sprint 3 foundation."
      dimension: "Contracts"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_1", "ev_2", "ev_10"]
      confidence: 0.92
      so_what_chain:
        - level: "fact"
          statement: "Integrity and compliance endpoints, Pydantic shapes, Zod mirrors, adapter methods, and port methods exist."
        - level: "impact"
          statement: "The frontend can fetch Sprint 3 data through the established wire/port/adapter boundary."
        - level: "implication"
          statement: "The implementation follows the intended read-only integration pattern."
        - level: "connection"
          statement: "This supports the view that Sprint 3 is substantially implemented."
    - id: "arg_2"
      statement: "The user-facing Compliance Center currently overstates audit completeness in export and range semantics."
      dimension: "User Experience"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_4", "ev_5", "ev_6"]
      confidence: 0.86
      so_what_chain:
        - level: "fact"
          statement: "The JSON export emits only summary rows, and the page has no since/until range flow."
        - level: "impact"
          statement: "Operators can export incomplete evidence and inspect workflows outside the intended audit window."
        - level: "implication"
          statement: "The Compliance Center is usable for exploration but not reliable as an audit artifact."
        - level: "connection"
          statement: "This is the highest-priority reason Sprint 3 needs follow-up fixes."
    - id: "arg_3"
      statement: "The implementation preserves most architecture constraints but has emerging scale and layering pressure."
      dimension: "Architecture"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_7", "ev_8", "ev_9"]
      confidence: 0.8
      so_what_chain:
        - level: "fact"
          statement: "Compliance home calls one integrity endpoint per workflow, and WorkflowDeepDive derives guardrail summaries inside a React component."
        - level: "impact"
          statement: "The page can degrade with workflow count and domain derivation can spread in UI code."
        - level: "implication"
          statement: "The design will be harder to scale and maintain unless batch reads and translators are introduced."
        - level: "connection"
          statement: "This supports targeted refactoring before Sprint 4 adds more advanced views."
    - id: "arg_4"
      statement: "Testing is strong enough to prove the happy path and major failure paths, but it does not yet lock the most audit-sensitive behavior."
      dimension: "Tests"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_10", "ev_11", "ev_12"]
      confidence: 0.78
      so_what_chain:
        - level: "fact"
          statement: "Backend and frontend suites pass, but tests assert the current shallow export shape and do not route-test range or tampered deep-dive evidence."
        - level: "impact"
          statement: "Critical mismatches can remain green."
        - level: "implication"
          statement: "The test suite needs a few contract-level assertions aligned to audit expectations."
        - level: "connection"
          statement: "This explains why green tests do not fully remove Sprint 3 residual risk."

  evidence:
    - id: "ev_1"
      fact: "`ExplainabilityService.get_workflow_integrity()` exposes chain validity and first broken hash details."
      source: "services/explainability_service.py"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 0.95
    - id: "ev_2"
      fact: "`GET /api/v1/workflows/{wf_id}/integrity` and `/compliance` are mounted as read-only FastAPI GET endpoints."
      source: "explainability_app/server.py"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 0.95
    - id: "ev_3"
      fact: "`ComplianceBundleResponse` carries events, identity cards, audit trails, phase decisions, and correlation health, but not integrity break-location fields."
      source: "explainability_app/wire/responses.py"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 0.9
    - id: "ev_4"
      fact: "`ComplianceExportButtons` labels the action `Export JSON Bundle` but serializes a `compliance_summary` containing only workflow summary and integrity report."
      source: "frontend-explainability/components/compliance/ComplianceExportButtons.tsx"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 0.95
    - id: "ev_5"
      fact: "`/compliance` calls `listWorkflows()` and `getGuardrailSummary()` without range parameters."
      source: "frontend-explainability/app/compliance/page.tsx"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 0.95
    - id: "ev_6"
      fact: "`/compliance/[wf_id]` renders a correlation badge and four quadrants, but the Recording quadrant only has `hash_chain_valid` from the compliance bundle."
      source: "frontend-explainability/app/compliance/[wf_id]/page.tsx and components/compliance/WorkflowDeepDive.tsx"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 0.9
    - id: "ev_7"
      fact: "`/compliance` performs one `getWorkflowIntegrity()` call per workflow."
      source: "frontend-explainability/app/compliance/page.tsx"
      assigned_to: "arg_3"
      branch_id: "branch_3"
      confidence: 0.95
    - id: "ev_8"
      fact: "`BlackBoxRecorder.export()` reads and re-hashes the full trace on each integrity call."
      source: "services/governance/black_box.py"
      assigned_to: "arg_3"
      branch_id: "branch_3"
      confidence: 0.95
    - id: "ev_9"
      fact: "`WorkflowDeepDive` walks `bundle.events` and interprets `details.accepted` inside the React component."
      source: "frontend-explainability/components/compliance/WorkflowDeepDive.tsx"
      assigned_to: "arg_3"
      branch_id: "branch_3"
      confidence: 0.85
    - id: "ev_10"
      fact: "Backend Sprint 3 regression suite passes: 82 tests."
      source: "pytest tests/services/test_explainability_service.py tests/explainability_app/ tests/architecture/test_explainability_layering.py tests/architecture/test_agents_router_read_only.py -q"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 1.0
    - id: "ev_11"
      fact: "Frontend Sprint 3 focused suite passes: 106 tests, including compliance components, adapter, and wire drift."
      source: "npm run test -- components/compliance lib/adapters/http_explainability_client.test.ts lib/wire/baseline_drift.test.ts"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 1.0
    - id: "ev_12"
      fact: "Typecheck, lint, and frontend architecture tests pass."
      source: "npm run typecheck && npm run lint && npm run test:arch"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 1.0

  gaps:
    untested_hypotheses:
      - branch_id: "branch_2"
        hypothesis: "Compliance Center respects a caller-selected audit window."
        reason: "No range UI or query propagation exists yet."
        impact_on_confidence: "Medium; affects audit correctness."
      - branch_id: "branch_2"
        hypothesis: "JSON export is a complete compliance audit bundle."
        reason: "Tests currently assert the shallow summary shape instead."
        impact_on_confidence: "High; affects audit artifact correctness."
    missing_data:
      - description: "No benchmark of Compliance home latency as workflow/event count grows."
        would_affect: "N+1 integrity-read severity and caching priority."
      - description: "No browser/manual accessibility pass for the new Compliance routes."
        would_affect: "Confidence in screen-reader and keyboard UX."
    known_weaknesses:
      - description: "The JSON export label and payload disagree."
        severity: "high"
      - description: "Compliance home lacks audit-window filtering."
        severity: "medium"
      - description: "Compliance home performs per-workflow integrity reads."
        severity: "medium"
      - description: "Deep dive does not show broken event/hash mismatch evidence."
        severity: "medium"
      - description: "A component owns guardrail aggregation logic."
        severity: "medium"
      - description: "A comment claims Promise.allSettled while the code uses Promise.all."
        severity: "low"

  cross_branch_interactions:
    - branches: ["branch_2", "branch_4"]
      interaction: "The export tests pass because they assert the current shallow summary shape, which hides the user-facing export mismatch."
    - branches: ["branch_2", "branch_3"]
      interaction: "Fixing export correctness by fetching every compliance bundle naively would worsen the existing N+1/scaling issue unless a batch endpoint is added."
    - branches: ["branch_1", "branch_2"]
      interaction: "Backend integrity break-location data exists, but the compliance bundle contract does not carry it into the deep-dive UI."

  validation_log:
    - check: "completeness"
      result: "pass"
      details: "Contracts, experiences, architecture, and tests cover the Sprint 3 review scope."
    - check: "non_overlap"
      result: "pass"
      details: "Each evidence item is assigned to one primary branch; interactions are listed separately."
    - check: "item_placement"
      result: "pass"
      details: "Export shape belongs to Experiences; N+1 calls belong to Architecture; passing suites belong to Tests."
    - check: "so_what"
      result: "pass"
      details: "Each finding connects to audit correctness, maintainability, scalability, or confidence."
    - check: "vertical_logic"
      result: "pass"
      details: "All key arguments directly answer whether Sprint 3 is complete and safe to rely on."
    - check: "remove_one"
      result: "pass"
      details: "Removing any one argument weakens but does not collapse the governing thought."
    - check: "never_one"
      result: "pass"
      details: "The issue tree has four independent branches and no single-child grouping."
    - check: "mathematical"
      result: "not_applicable"
      details: "No numerical total or calculated recommendation is central to this review."

  metadata:
    problem_scope: "Sprint 3 explainability compliance implementation review."
    tools_used:
      - "ReadFile"
      - "rg"
      - "Shell"
      - "Subagent"
    iteration_count: 1
    reasoning_trace_summary: "Decomposed the review into contracts, experiences, architecture, and tests. Confirmed that implementation is green and structurally present, then identified user-facing audit gaps and maintainability risks that tests do not currently catch."
    communication_tone: "direct"
    presentation_notes:
      - "Lead with the export mismatch because it is the most audit-sensitive gap."
      - "Tests are strong overall; recommendations target gaps that can stay green today."
```

## Validation Run

- Backend focused regression: `82 passed`
  - `pytest tests/services/test_explainability_service.py tests/explainability_app/ tests/architecture/test_explainability_layering.py tests/architecture/test_agents_router_read_only.py -q`
- Frontend Sprint 3 focused suite: `106 passed`
  - `npm run test -- components/compliance lib/adapters/http_explainability_client.test.ts lib/wire/baseline_drift.test.ts`
- Frontend type/lint/architecture: clean
  - `npm run typecheck && npm run lint && npm run test:arch`

