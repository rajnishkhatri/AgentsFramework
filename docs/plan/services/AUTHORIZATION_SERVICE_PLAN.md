# AUTHORIZATION_SERVICE_PLAN.md — `services/authorization_service.py` Implementation Plan

> **Status**: design sub-plan for sprint S1 of [AGENT_UI_ADAPTER_SPRINTS.md](../adapter/sprints/AGENT_UI_ADAPTER_SPRINTS.md). Implements the Runtime Trust Gate from [docs/FOUR_LAYER_ARCHITECTURE.md](../../FOUR_LAYER_ARCHITECTURE.md) lines 599–664.
>
> **TDD Protocol**: B (Contract-driven, decision matrix) per [research/tdd_agentic_systems_prompt.md](../../../research/tdd_agentic_systems_prompt.md) §Protocol B + §B2 + §Pattern 11 (Failure Mode Matrix).
>
> **Boundary**: horizontal service per [AGENTS.md](../../../AGENTS.md). Receives `AgentFacts` as a parameter (Critical Design Rule, [docs/FOUR_LAYER_ARCHITECTURE.md](../../FOUR_LAYER_ARCHITECTURE.md) lines 641–661). Anti-pattern AP-2 strictly enforced.

---

## 1. Purpose & Boundaries

### 1.1 What it does

Given an `AgentFacts` (the agent's identity card), an `action` (the operation requested), and a `context` (free-form details: tool name, args, target resource), returns a `PolicyDecision` (`allow` / `deny` / `require_approval` / `throttle`). On every decision, emits a `TrustTraceRecord` to the configured `TraceService`.

### 1.2 What it does NOT do

- **Does NOT fetch identity** — `AgentFacts` arrives as a parameter. The service never calls `AgentFactsRegistry.get(...)` itself. (AP-2 enforcement; [docs/FOUR_LAYER_ARCHITECTURE.md](../../FOUR_LAYER_ARCHITECTURE.md) Critical Design Rule.)
- **Does NOT verify signatures** — that's `services/governance/agent_facts_registry.py`'s job; the orchestrator calls verify FIRST, then passes verified facts here
- **Does NOT log directly to a file** — emits a `TrustTraceRecord` to the trace service, which decides routing
- **Does NOT mutate state** — pure decision function (plus a side effect: trace emission)
- **Does NOT make HTTP calls** to OPA/Cedar in v1 — embedded policy evaluation only; external policy backends are a v1.5 add via the `PolicyBackend` Protocol below

### 1.3 Why it exists

[AGENT_UI_ADAPTER_PLAN.md](../adapter/AGENT_UI_ADAPTER_PLAN.md) §5.3 mandates a dual-PEP design. The adapter does a cheap pre-flight check (JWT validity), but the in-graph PEP (per-action policy) needs a horizontal service so that any orchestrator (LangGraph today, CrewAI tomorrow) reuses the same decision logic.

---

## 2. Public Interface

```python
# services/authorization_service.py

from typing import Protocol, runtime_checkable, Any
from trust.models import AgentFacts, PolicyDecision, TrustTraceRecord

@runtime_checkable
class PolicyBackend(Protocol):
    """External policy backend Protocol. Implementations: EmbeddedPolicyBackend (v1),
    OpaPolicyBackend (v1.5), CedarPolicyBackend (v1.5)."""
    def evaluate(
        self,
        facts: AgentFacts,
        action: str,
        context: dict,
    ) -> PolicyDecision: ...


class AuthorizationService:
    def __init__(
        self,
        embedded_backend: PolicyBackend,         # Layer A: signed embedded policies (always evaluated first)
        external_backend: PolicyBackend | None = None,  # Layer B: OPA/Cedar/YAML (v1.5)
        trace_emit: callable | None = None,      # function passed by composition root, e.g. trace_service.emit
    ) -> None:
        ...

    def authorize(
        self,
        facts: AgentFacts,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Pure-ish: evaluates embedded policies, then external if any. Embedded deny short-circuits.
        Side effect: emits a TrustTraceRecord via trace_emit (if provided).
        """
        ...
```

### 2.1 Built-in backend

- `EmbeddedPolicyBackend` — evaluates `facts.policies` and `facts.capabilities` directly. Pure function. No I/O.

External backends live in `services/policy_backends/<name>.py` and are wired by the composition root.

---

## 3. Decision Matrix (B2-style)

Per TDD Protocol B §B2 (Authorization Service Tests). Every row below is a test.

| # | AgentFacts state | Capabilities | Embedded policies | External policies | Expected decision |
|---|---|---|---|---|---|
| 1 | `status=ACTIVE`, `valid_until` future | matches action | none | none | `allow` |
| 2 | `status=ACTIVE`, `valid_until` PAST | matches action | none | none | `deny` (reason: "expired identity") |
| 3 | `status=SUSPENDED` | matches action | none | none | `deny` (reason: "suspended identity") |
| 4 | `status=REVOKED` | matches action | none | none | `deny` (reason: "revoked identity") |
| 5 | `status=ACTIVE` | does NOT match action | none | none | `deny` (reason: "missing capability") |
| 6 | `status=ACTIVE` | matches | embedded `deny` | external `allow` | `deny` (embedded wins per [docs/FOUR_LAYER_ARCHITECTURE.md](../../FOUR_LAYER_ARCHITECTURE.md) precedence) |
| 7 | `status=ACTIVE` | matches | embedded `allow` | external `deny` | `deny` (any deny denies) |
| 8 | `status=ACTIVE` | matches | embedded `allow` | external `allow` | `allow` |
| 9 | `status=ACTIVE` | matches | embedded `require_approval` | n/a | `require_approval` |
| 10 | `status=ACTIVE` | matches | embedded `throttle` | n/a | `throttle` |

Each row → one test in `tests/services/test_authorization_service.py`. Pattern 11 (failure mode matrix).

---

## 4. Test Plan (failure paths first)

Per Protocol B. Test file: `tests/services/test_authorization_service.py`.

### 4.1 Failure path tests (write FIRST — rows 2, 3, 4, 5, 6, 7 above all reject)

These 6 tests precede the 4 acceptance tests (rows 1, 8, 9, 10), satisfying TAP-4.

### 4.2 Trace emission tests

- `test_authorize_emits_trace_on_allow` — given `trace_emit=mock`, after a successful `authorize()`, mock received exactly one `TrustTraceRecord` with `outcome="pass"` and `event_type="access_granted"`
- `test_authorize_emits_trace_on_deny` — same with `outcome="fail"` and `event_type="access_denied"`
- `test_authorize_works_without_trace_emit` — `trace_emit=None` does NOT raise; decision still returned

### 4.3 Boundary tests

- `test_authorize_rejects_none_facts` — raises `TypeError`
- `test_authorize_rejects_empty_action` — raises `ValueError`
- `test_authorize_does_not_call_registry` — given a mock `AgentFactsRegistry` that explodes if called, `authorize()` succeeds (proves AP-2 isolation: facts come in via parameter, registry is never imported)

### 4.4 Architecture tests

- `test_authorization_service_does_not_import_other_services` — AST scan; only `trust.*`, stdlib, `pydantic`
- `test_authorization_service_does_not_import_registry` — explicit assertion that `services.governance.agent_facts_registry` is NOT imported

### 4.5 Property-based test

- `test_embedded_deny_always_wins` — Hypothesis generates `(facts, embedded_decision, external_decision)` triples; whenever `embedded_decision.enforcement == "deny"`, the result is always `deny` regardless of external

### 4.6 Test budget

Full file <15s. Decision matrix (10 rows) + 3 trace tests + 3 boundary tests + 2 arch tests + 1 property = 19 tests.

---

## 5. Logging

Add to [logging.json](../../../logging.json):

```json
"services.authorization": {
  "handlers": ["console", "authorization_file"],
  "level": "INFO",
  "propagate": false
}
```

Logs at INFO: every decision (action, agent_id, outcome, reason). Trace records carry the structured form; the log line is for human ops.

**Sensitive-data invariant**: never log `context` values verbatim if they may contain user PII. Log `context` keys but not values.

---

## 6. Dependencies

- **Internal**: `trust.models.AgentFacts`, `trust.models.PolicyDecision`, `trust.models.TrustTraceRecord`, `trust.enums.IdentityStatus` only
- **External**: stdlib + `pydantic`
- **Test deps**: `pytest`, `hypothesis`, `freezegun` (for `valid_until` PAST tests)

NO new `pyproject.toml` dependencies in v1. OPA/Cedar SDKs come with their respective backends in v1.5.

---

## 7. Open Questions / Deferred

- **Q-A1**: External `PolicyBackend` implementations (OPA, Cedar) — deferred to v1.5; v1 ships with `EmbeddedPolicyBackend` only
- **Q-A2**: Caching `authorize()` results — deferred; latency is L2 budget (<5ms typical), no cache pressure expected
- **Q-A3**: Per-decision audit trail beyond the trace record — `AgentFactsRegistry` already maintains an audit trail for identity changes; per-action audit is the trace record's job
- **Q-A4**: `throttle` enforcement — the decision is returned; the orchestrator implements the rate limit. The service does not own a token bucket
- **Q-A5**: Capability-action matching algorithm — v1 uses exact-string match on `Capability.name == action`. If glob/wildcard matching becomes necessary, add a `MatchStrategy` Protocol

---

## 8. Acceptance Sign-Off

S1 sprint considers US-1.3 done when:

- All 19 tests in §4 are green
- Decision matrix in §3 is fully covered (10 rows = 10 tests)
- Architecture tests prove no `services/*` imports (AP-2) and no registry import
- `tests/services/test_authorization_service.py` runs in <15s
- `logging.json` updated and validated
- The traceability row in [AGENT_UI_ADAPTER_SPRINTS.md](../adapter/sprints/AGENT_UI_ADAPTER_SPRINTS.md) §5 for US-1.3 is updated with the commit SHA
