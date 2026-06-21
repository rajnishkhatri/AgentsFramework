---
type: review
title: 'Sprint 4 Explainability UI Implementation Review'
description: 'This review evaluates the Sprint 4 implementation against'
tags: [explainability]
---

# Sprint 4 Explainability UI Implementation Review

This review evaluates the Sprint 4 implementation against
`docs/explainability/EXPLAINABILITY_UI_SPRINT_BOARD.md` and uses the structured
analysis protocol in `research/pyramid_react_system_prompt.md`.

## Findings

### F1 — `since` log filtering can 500 with the frontend's ISO timestamps

**Severity:** High  
**Scope:** `services/explainability_service.py`,
`explainability_app/server.py`, `frontend-explainability/lib/adapters/http_explainability_client.ts`

The frontend adapter sends `since` as `Date.toISOString()`, which includes a
UTC offset. FastAPI parses that into an offset-aware `datetime`, but
`_parse_log_timestamp()` creates offset-naive timestamps from Python logging's
`YYYY-MM-DD HH:MM:SS,mmm` format:

```python
base_dt = datetime.strptime(base, "%Y-%m-%d %H:%M:%S")
return base_dt.replace(microsecond=int(ms) * 1000)
```

`_row_matches()` then compares the naive row timestamp to the aware request
timestamp:

```python
if since is not None and row.timestamp is not None:
    if row.timestamp < since:
        return False
```

That raises `TypeError: can't compare offset-naive and offset-aware datetimes`,
which the `/api/v1/logs` route converts into a 500. The service test only uses a
naive cutoff, so it does not catch the real adapter/server path.

**Risk:** Any user- or UI-driven `since` filter can break the Log Viewer instead
of filtering rows.

**Recommendation:** Normalize all log timestamps and query bounds to one
timezone convention before comparison. The simplest fix is to attach `UTC` to
logging timestamps and convert incoming `since` to UTC before comparison. Add a
service test with `datetime(..., tzinfo=UTC)` and an endpoint test using
`since=2026-04-26T00:00:00+00:00` against the real service implementation, not
only a stub.

### F2 — Log `concerns` are unsanitized filesystem path segments

**Severity:** High  
**Scope:** `services/explainability_service.py`

`query_logs()` and `tail_logs()` accept arbitrary concern strings and build file
paths directly from them:

```python
wanted = list(concerns) if concerns else list(DEFAULT_LOG_CONCERNS)
log_file = self._logs_dir / f"{concern}.log"
```

The endpoint exposes `concerns` as user-controlled query params, but the service
does not restrict them to `DEFAULT_LOG_CONCERNS`, reject path separators, or
resolve-and-check that the final path remains under `logs/`.

**Risk:** A crafted local request can attempt path traversal to any readable
`*.log` path relative to `logs_dir` (for example `../some_dir/file` becomes
`logs/../some_dir/file.log`). This violates Sprint 4's "per-concern names from
logging.json" boundary and weakens the local-only security model.

**Recommendation:** Treat `DEFAULT_LOG_CONCERNS` as an allowlist. Drop or reject
unknown concerns before path construction, and add tests for `concerns=["../x"]`
and `concerns=["guards/../../x"]`. Apply the same allowlist to `tail_logs()`.

### F3 — `/logs` filters do not update the static log list

**Severity:** High  
**Scope:** `frontend-explainability/app/logs/page.tsx`,
`frontend-explainability/components/logs/LogViewer.tsx`

The route fetches initial rows once:

```tsx
initialRows = await explainabilityClient.queryLogs({
  concerns: concerns.length > 0 ? concerns : undefined,
  level,
  search: search.trim() || null,
  limit: DEFAULT_LIMIT,
});
```

`LogViewer` then stores filter UI state locally, but in non-tail mode it renders
the original `initialRows` unchanged:

```tsx
const [concerns, setConcerns] = useState<readonly string[]>(initialConcerns);
const [level, setLevel] = useState<LogLevel | null>(initialLevel);
const [search, setSearch] = useState<string>(initialSearch);
...
<LogTable rows={initialRows} />
```

The updated filters only affect a new SSE connection when tailing is enabled.
They never re-query `/api/v1/logs`, update the URL, or filter the current rows
client-side.

**Risk:** The visible concern checkboxes, level buttons, and search box appear
to control the static log list but do nothing until Tail is started. Operators
can draw incorrect conclusions from stale rows.

**Recommendation:** Choose one contract and test it. Preferred: make filter
changes update URL search params and let the RSC route re-fetch `queryLogs()`.
Alternative: filter `initialRows` client-side for the static view and reserve
server-side filters for tailing. Add a `LogViewer` test that toggling `ERROR`,
unchecking a concern, and typing search changes the rendered rows.

### F4 — SSE parse-error handling does not meet the Sprint 4 TDD requirement

**Severity:** Medium  
**Scope:** `frontend-explainability/lib/transport/sse_client.ts`,
`frontend-explainability/components/logs/LogViewer.tsx`, tests

Sprint 4 asks for a failure-first test where "SSE Zod parse error synthesizes a
`RunErrorEvent`-shape error frame and surfaces a toast." The implementation
does parse `event: log` frames through Zod, but it only calls `onError(message)`:

```ts
const result = LogRowSchema.safeParse(raw);
if (!result.success) {
  opts.onError?.(`SSE log frame failed Zod parse: ${result.error.message}`);
  return;
}
```

`LogViewer` then renders a generic inline alert:

```tsx
<span role="alert">Stream error: {tailError}</span>
```

There is no RunErrorEvent-shaped object, no log-frame fallback row, no toast
abstraction, and no test around `openLogStream()` or `LogViewer` tail behavior.

**Risk:** The most important streaming failure path can regress without tests,
and parse failures are surfaced differently from the Sprint 4 acceptance
contract.

**Recommendation:** Define a small explainability log stream error frame shape
analogous to `RunErrorEvent` (or explicitly document why this MVP uses a simpler
shape). Add tests that stub `EventSource`, emit malformed JSON and schema-invalid
JSON, and assert the UI shows the expected error frame/toast while keeping the
connection lifecycle controllable.

### F5 — Replay architecture test does not enforce the stated invariant

**Severity:** Medium  
**Scope:** `frontend-explainability/tests/architecture/test_replay_no_runtime_calls.test.ts`

The Sprint 4 acceptance criterion says the Replay architecture test asserts
that no file under `frontend-explainability/app/traces/` imports anything that
reaches a runtime endpoint other than `/api/v1/workflows/{id}/events`.

The test currently allowlists multiple non-events client methods:

```ts
const ALLOWED_CLIENT_METHODS = new Set([
  "getWorkflowEvents",
  "getWorkflowDecisions",
  "getWorkflowIntegrity",
  "getWorkflowCompliance",
  "listWorkflows",
]);
```

It also only scans files under `app/traces/` and does not follow the import graph
into `components/traces/ReplayScrubber.tsx` or
`lib/translators/events_to_replay_frames.ts`, where replay logic actually lives.

**Risk:** A future Replay change could introduce a runtime replay endpoint or
another adapter call outside `app/traces/` and still pass the architecture test.

**Recommendation:** Tighten the test to the replay surface rather than the
whole trace module: resolve imports from `/traces/[wf_id]` into the Replay tab
and fail on any `fetch`, adapter call, `EventSource`, `orchestration`,
`langgraph`, or API string except the already-existing events fetch. If the
route-level scan remains, only allow `getWorkflowEvents` in the workflow detail
page and exclude the list page intentionally with a comment.

### F6 — `WARN` filter likely misses real Python warning rows

**Severity:** Medium  
**Scope:** `services/explainability_service.py`,
`frontend-explainability/lib/wire/responses.ts`,
`frontend-explainability/components/logs/LogViewer.tsx`

The UI exposes `WARN`, and `_row_matches()` compares exact uppercase levels:

```python
if level is not None and row.level != level.upper():
    return False
```

Python `logging` normally emits `WARNING` as `%(levelname)s`, not `WARN`. The
tests synthesize `WARN` lines, so they don't prove that real warning records
from the project's loggers are filterable.

**Risk:** Users selecting `WARN` may see zero rows even when the log files
contain warnings.

**Recommendation:** Normalize `WARN` and `WARNING` at the service boundary.
Either expose `WARNING` in the UI or map requested `WARN` to accepted levels
`{"WARN", "WARNING"}`. Add a test using an actual `logger.warning(...)` line or
at least a `WARNING` fixture.

### F7 — "Monaco-rendered list" is not implemented

**Severity:** Low  
**Scope:** `frontend-explainability/components/logs/LogTable.tsx`,
`frontend-explainability/package.json`

S4.3.3 specifies a "Monaco-rendered list with line numbers." The implementation
renders a custom table/list with line numbers, and there is no
`@monaco-editor/react` dependency in `frontend-explainability/package.json`.

**Risk:** This is mostly an acceptance/expectation mismatch, not a functional
bug. The custom list may be sufficient for MVP, but it should not be called
Monaco-rendered.

**Recommendation:** Either add `@monaco-editor/react` and dynamically render the
log list with Monaco, or amend the sprint board / review note to explicitly
accept the lighter DOM list for MVP.

## Recommended Fix Plan

### P0 — Fix correctness and boundary issues before relying on `/logs`

1. Normalize log timestamps and `since` bounds to a consistent timezone. Add
   aware-datetime service and endpoint tests.
2. Apply a concern allowlist in `query_logs()` and `tail_logs()`. Add traversal
   rejection/drop tests.
3. Normalize `WARN`/`WARNING` level handling and test with realistic warning
   rows.

### P1 — Make the Log Viewer controls truthful

1. Decide whether static filtering is server-driven (URL/searchParams) or
   client-side over the initial page.
2. Implement the chosen contract and add `LogViewer` interaction tests for
   concern, level, and search.
3. Add tail-toggle tests that stub `openLogStream()` and assert start, stop,
   and cleanup behavior.

### P2 — Tighten Sprint 4 safety tests

1. Strengthen `test_replay_no_runtime_calls.test.ts` to follow the Replay import
   graph or explicitly include `components/traces/ReplayScrubber.tsx` and the
   replay translator.
2. Add SSE parse-error tests around `openLogStream()`.
3. Add backend SSE tests for heartbeat emission and cancellation of an infinite
   stream, not only a finite stub stream.

### P3 — Resolve acceptance/documentation mismatches

1. Decide whether to ship Monaco in MVP. If yes, add the dependency and
   dynamically load the editor/list. If no, document the DOM list as the
   accepted MVP substitute.
2. Update the stale adapter header that still says `EventSource` is only allowed
   in the HTTP adapter; the new rule correctly places it in `lib/transport/`.

## Structured Analysis Output

```yaml
analysis_output:
  problem_definition:
    original_statement: "Review Sprint 4 implementation using research/pyramid_react_system_prompt.md; identify issues and gaps; create a plan with recommended fixes."
    restated_question: "Does the Sprint 4 explainability implementation satisfy the Advanced Views acceptance criteria without material correctness, architecture, or test gaps, and what fixes should be prioritized?"
    problem_type: "evaluation"
    scope_boundaries: "In scope: Sprint 4 Cascade, Replay, Log Viewer backend/API/SSE/frontend/tests/docs. Out of scope: implementing fixes, Sprint 3 residual fixes, unrelated middleware architecture failures."
    success_criteria: "Findings are evidence-backed, prioritized by user/operator risk, and paired with a concrete remediation plan."

  issue_tree:
    root_question: "Does Sprint 4 meet acceptance criteria and quality expectations?"
    ordering_type: "structural"
    branches:
      - id: "branch_1"
        label: "Contracts"
        question: "Do backend and frontend data contracts behave correctly for log queries and streams?"
        hypothesis: "Core endpoints exist, but edge-case filters and stream errors likely have correctness gaps."
        hypothesis_status: "confirmed"
        evidence_ids: ["ev_1", "ev_2", "ev_3", "ev_4"]
        sub_branches: []
      - id: "branch_2"
        label: "Experiences"
        question: "Do user-facing Sprint 4 views make the promised controls and advanced views usable?"
        hypothesis: "The views are present, but Log Viewer controls and Monaco rendering likely diverge from AC."
        hypothesis_status: "confirmed"
        evidence_ids: ["ev_5", "ev_6", "ev_7"]
        sub_branches: []
      - id: "branch_3"
        label: "Architecture"
        question: "Do replay and SSE preserve the no-runtime-call and transport-boundary invariants?"
        hypothesis: "Implementation mostly follows boundaries, but architecture tests under-enforce them."
        hypothesis_status: "confirmed"
        evidence_ids: ["ev_8", "ev_9"]
        sub_branches: []
      - id: "branch_4"
        label: "Tests"
        question: "Do tests catch the risky failure paths required by Sprint 4?"
        hypothesis: "Focused tests pass, but several Sprint-specific failure paths remain untested."
        hypothesis_status: "confirmed"
        evidence_ids: ["ev_10", "ev_11", "ev_12"]
        sub_branches: []

  governing_thought:
    statement: "Sprint 4 is structurally implemented, but the Log Viewer is not reliable yet: timezone filtering, concern path sanitization, static filter behavior, and streaming error tests need fixes before the sprint should be considered closed."
    confidence: 0.82

  key_arguments:
    - id: "arg_1"
      statement: "The log backend has correctness and boundary bugs that can produce 500s or read outside the intended concern set."
      dimension: "Contracts"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_1", "ev_2", "ev_3", "ev_4"]
      confidence: 0.9
      so_what_chain:
        - level: "fact"
          statement: "Aware ISO `since` values can be compared with naive log timestamps, and arbitrary concern strings become filesystem paths."
        - level: "impact"
          statement: "The API can error on normal frontend input and can attempt to read unexpected `*.log` paths."
        - level: "implication"
          statement: "The Log Viewer backend is not yet safe to rely on even in local-only mode."
        - level: "connection"
          statement: "This is the highest-priority reason Sprint 4 needs follow-up fixes."
    - id: "arg_2"
      statement: "The Log Viewer UI presents controls that do not affect the static rows, creating a misleading operator experience."
      dimension: "Experiences"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_5", "ev_6", "ev_7"]
      confidence: 0.86
      so_what_chain:
        - level: "fact"
          statement: "Filter state is local, but the non-tail table always renders `initialRows`."
        - level: "impact"
          statement: "Users can change concern/level/search controls and still see stale rows."
        - level: "implication"
          statement: "The route is present but does not satisfy the expected filter behavior."
        - level: "connection"
          statement: "This keeps S4.3.3 from being functionally complete."
    - id: "arg_3"
      statement: "Replay and SSE architecture boundaries are mostly respected in implementation but not fully protected by tests."
      dimension: "Architecture"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_8", "ev_9"]
      confidence: 0.76
      so_what_chain:
        - level: "fact"
          statement: "Replay runs over already-fetched events, but the architecture test allowlists non-events methods and does not follow imports."
        - level: "impact"
          statement: "A future runtime replay endpoint could be introduced in a component or translator without being caught."
        - level: "implication"
          statement: "The most important Sprint 4 invariant is weaker than it appears."
        - level: "connection"
          statement: "Test hardening is required to preserve the no-reexecution guarantee."
    - id: "arg_4"
      statement: "Test coverage is broad enough to prove happy paths, but misses several acceptance-critical failure paths."
      dimension: "Tests"
      reasoning_mode: "inductive"
      evidence_ids: ["ev_10", "ev_11", "ev_12"]
      confidence: 0.78
      so_what_chain:
        - level: "fact"
          statement: "Existing tests cover many rows and endpoint stubs, but omit aware `since`, path traversal, static filter interactions, SSE parse errors, heartbeat, and true cancellation."
        - level: "impact"
          statement: "Green tests do not prove the riskiest Sprint 4 behavior."
        - level: "implication"
          statement: "A few targeted failure tests would materially improve confidence."
        - level: "connection"
          statement: "This explains why the implementation can look complete while still having operator-facing gaps."

  evidence:
    - id: "ev_1"
      fact: "`HttpExplainabilityClient.queryLogs({ since })` sends `since` via `Date.toISOString()`, while `_parse_log_timestamp()` creates naive datetimes."
      source: "frontend-explainability/lib/adapters/http_explainability_client.ts; services/explainability_service.py"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 0.95
    - id: "ev_2"
      fact: "A direct service reproduction with aware `since` raises `TypeError: can't compare offset-naive and offset-aware datetimes`."
      source: "local Python check during review"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 1.0
    - id: "ev_3"
      fact: "`query_logs()` and `tail_logs()` build `logs_dir / f'{concern}.log'` from unvalidated query params."
      source: "services/explainability_service.py"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 0.95
    - id: "ev_4"
      fact: "`WARN` is exposed in the UI, but Python logging emits `WARNING` and service filtering is exact."
      source: "frontend-explainability/lib/wire/responses.ts; services/explainability_service.py"
      assigned_to: "arg_1"
      branch_id: "branch_1"
      confidence: 0.85
    - id: "ev_5"
      fact: "`LogViewer` stores concern, level, and search state but non-tail mode always renders unchanged `initialRows`."
      source: "frontend-explainability/components/logs/LogViewer.tsx"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 0.95
    - id: "ev_6"
      fact: "`/logs` fetches initial rows once from the route search params; the client controls do not update those params."
      source: "frontend-explainability/app/logs/page.tsx"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 0.9
    - id: "ev_7"
      fact: "The log list is a custom DOM list/table, not Monaco-rendered."
      source: "frontend-explainability/components/logs/LogTable.tsx; frontend-explainability/package.json"
      assigned_to: "arg_2"
      branch_id: "branch_2"
      confidence: 0.9
    - id: "ev_8"
      fact: "The replay route only fetches workflow events and computes timeline/cascade/replay from the same event payload."
      source: "frontend-explainability/app/traces/[wf_id]/page.tsx"
      assigned_to: "arg_3"
      branch_id: "branch_3"
      confidence: 0.9
    - id: "ev_9"
      fact: "`test_replay_no_runtime_calls` allowlists non-events client methods and only scans `app/traces/`, not the replay import graph."
      source: "frontend-explainability/tests/architecture/test_replay_no_runtime_calls.test.ts"
      assigned_to: "arg_3"
      branch_id: "branch_3"
      confidence: 0.95
    - id: "ev_10"
      fact: "Backend Sprint 4 focused suite passes 100 tests."
      source: "pytest tests/services/test_explainability_service.py tests/explainability_app/ tests/architecture/test_explainability_layering.py tests/architecture/test_agents_router_read_only.py -q"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 1.0
    - id: "ev_11"
      fact: "Frontend suite passes 233 tests with typecheck and lint clean."
      source: "npm run test && npm run test:arch && npm run typecheck && npm run lint"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 1.0
    - id: "ev_12"
      fact: "No tests cover `LogViewer` filter interactions, `openLogStream` malformed frames, heartbeat frames, or true infinite-stream cancellation."
      source: "test file inspection"
      assigned_to: "arg_4"
      branch_id: "branch_4"
      confidence: 0.9

  gaps:
    untested_hypotheses:
      - branch_id: "branch_1"
        hypothesis: "The `/api/v1/logs` endpoint handles frontend-generated ISO `since` params."
        reason: "Endpoint test uses a stub; service test uses a naive datetime."
        impact_on_confidence: "High; normal filter input can 500."
      - branch_id: "branch_2"
        hypothesis: "The `/logs` filter controls update the rendered rows."
        reason: "No `LogViewer` interaction test exists."
        impact_on_confidence: "High; visible controls can be nonfunctional."
      - branch_id: "branch_4"
        hypothesis: "SSE parse errors surface the required error frame/toast behavior."
        reason: "No EventSource/openLogStream tests exist."
        impact_on_confidence: "Medium; streaming failure path is unverified."
    missing_data:
      - description: "No browser/manual pass of SSE disconnect behavior against a running Uvicorn server."
        would_affect: "Confidence in cancellation and file-handle cleanup."
      - description: "No performance measurement for query_logs reading large log files."
        would_affect: "Whether full-file reads need immediate tail/reverse-read optimization."
    known_weaknesses:
      - description: "Aware `since` filter can crash log queries."
        severity: "high"
      - description: "Concern strings are not restricted to logging.json names."
        severity: "high"
      - description: "Static Log Viewer controls do not update rendered rows."
        severity: "high"
      - description: "Replay architecture guard is weaker than the invariant it documents."
        severity: "medium"
      - description: "SSE parse-error acceptance path is not implemented/tested as specified."
        severity: "medium"
      - description: "Monaco rendering is not implemented."
        severity: "low"

  cross_branch_interactions:
    - branches: ["branch_1", "branch_2"]
      interaction: "Fixing static filters by routing them through query params will immediately expose the aware/naive `since` backend bug if date range filters are later added."
    - branches: ["branch_3", "branch_4"]
      interaction: "The replay implementation currently honors the no-runtime-call rule, but weak architecture tests mean future test-green changes may violate it."
    - branches: ["branch_2", "branch_4"]
      interaction: "The lack of `LogViewer` interaction tests explains why nonfunctional static filters stayed green."

  validation_log:
    - check: "completeness"
      result: "pass"
      details: "Contracts, experiences, architecture, and tests cover Sprint 4 review scope."
    - check: "non_overlap"
      result: "pass"
      details: "Evidence items are assigned to a primary branch; cross-effects are listed separately."
    - check: "item_placement"
      result: "pass"
      details: "Aware timestamp crash belongs to Contracts; stale filter UI belongs to Experiences; replay allowlist belongs to Architecture."
    - check: "so_what"
      result: "pass"
      details: "Each finding connects to operator correctness, security boundary, architecture invariant, or test confidence."
    - check: "vertical_logic"
      result: "pass"
      details: "Each key argument directly answers whether Sprint 4 is complete and reliable."
    - check: "remove_one"
      result: "pass"
      details: "Removing any one argument weakens but does not collapse the governing thought."
    - check: "never_one"
      result: "pass"
      details: "Issue tree has four independent branches and no single-child groupings."
    - check: "mathematical"
      result: "not_applicable"
      details: "No quantitative total drives the recommendation."

  metadata:
    problem_scope: "Sprint 4 explainability advanced views implementation review."
    tools_used:
      - "ReadFile"
      - "rg"
      - "Shell"
      - "Subagent"
    iteration_count: 1
    reasoning_trace_summary: "Partitioned the review into contracts, experiences, architecture, and tests. Confirmed the implementation exists and tests are largely green, then identified correctness and coverage gaps that current tests miss."
    communication_tone: "direct"
    presentation_notes:
      - "Lead with the Log Viewer correctness bugs because they affect normal usage."
      - "Replay implementation appears safer than its architecture guard; fix the guard before future changes."
```

## Validation Run

- Backend Sprint 4 focused suite: `100 passed`
  - `pytest tests/services/test_explainability_service.py tests/explainability_app/ tests/architecture/test_explainability_layering.py tests/architecture/test_agents_router_read_only.py -q`
- Frontend suite: `233 passed`
  - `cd frontend-explainability && npm run test`
- Frontend architecture: `6 passed`
  - `cd frontend-explainability && npm run test:arch`
- Frontend typecheck and lint: clean
  - `cd frontend-explainability && npm run typecheck && npm run lint`
- Broader backend architecture excluding unrelated middleware failure: `65 passed, 2 skipped`
  - `pytest tests/architecture/ --ignore=tests/architecture/test_middleware_layer.py -q`
- Known unrelated validation issue: `tests/architecture/test_middleware_layer.py` still fails on pre-existing `middleware/__main__.py` imports from `components` / `orchestration`.
