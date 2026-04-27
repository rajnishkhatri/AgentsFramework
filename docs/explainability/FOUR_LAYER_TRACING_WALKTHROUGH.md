# Four-Layer Tracing Walkthrough

> Hands-on, step-by-step guide to exercising JWT authentication, tool ACL authorization, observability logging, and tamper-proof black box recording in the ReAct agent framework.

Companion to [END_TO_END_TRACING_GUIDE.md](END_TO_END_TRACING_GUIDE.md), which covers the five trace planes and `trace_id` correlation. This guide walks you through **running** each layer and **inspecting** the artifacts it produces.

---

## Prerequisites

```bash
# 1. Copy env template and fill in OPENAI_API_KEY
cp .env.example .env

# 2. Install the project with dev dependencies
pip install -e ".[dev]"

# 3. Clean artifact directories for an isolated session
rm -rf cache/ logs/ && mkdir -p cache logs
```

---

## Step 1 -- JWT Authentication: Dev Middleware

The dev middleware (`middleware/__main__.py`) accepts **any** bearer token string and maps it to a fixed `dev-agent` identity. This lets you develop without real WorkOS credentials.

**Start the middleware:**

```bash
python -m middleware
```

**Test authenticated vs unauthenticated requests:**

```bash
# Health check (no auth required)
curl -s http://localhost:8000/healthz
# → {"status":"ok","profile":"dev","runtime":"langgraph"}

# With bearer token (any string works in dev mode) → 200
curl -s -w "\nHTTP %{http_code}\n" -X POST http://localhost:8000/threads \
  -H "Authorization: Bearer my-dev-token-123" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo-user"}'
# → {"thread_id":"t-32600fb6ae47","user_id":"demo-user",...}
# → HTTP 200

# Without bearer token → 401
curl -s -w "\nHTTP %{http_code}\n" -X POST http://localhost:8000/threads \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo-user"}'
# → {"detail":"missing bearer token"}
# → HTTP 401
```

Stop the middleware (`Ctrl+C`) before proceeding.

---

## Step 2 -- JWT Authentication: Production Verification

The production path (`middleware/adapters/auth/workos_jwt_verifier.py`) validates RS256 signatures via JWKS. The test suite exercises all rejection paths using **in-process RSA keys** with no network calls.

```bash
pytest tests/middleware/adapters/auth/test_workos_jwt_verifier.py -v
```

**Expected output -- 12 tests, all pass:**

```
TestRejectionPaths::test_R1_missing_token_raises_missing_token_error     PASSED
TestRejectionPaths::test_R2_expired_token_raises_expired_token_error     PASSED
TestRejectionPaths::test_R3_wrong_issuer_raises_invalid_issuer_error     PASSED
TestRejectionPaths::test_R4_wrong_client_id_raises_invalid_client_id_error PASSED
TestRejectionPaths::test_R5_wrong_token_use_raises_invalid_token_use_error PASSED
TestRejectionPaths::test_signature_tampering_raises_invalid_token_error  PASSED
TestRejectionPaths::test_unknown_kid_raises_invalid_token_error          PASSED
TestRejectionPaths::test_malformed_token_raises_invalid_token_error      PASSED
TestAcceptancePath::test_A1_valid_token_returns_normalized_claims        PASSED
TestBehavioralContract::test_verifier_satisfies_jwt_verifier_protocol   PASSED
TestBehavioralContract::test_verify_is_idempotent                        PASSED
TestBehavioralContract::test_verifier_returns_no_sdk_types               PASSED
```

| Category | Tests | What they prove |
|---|---|---|
| Rejection (R1-R5 + 3) | 8 | Missing, expired, wrong issuer/client_id/token_use, tampered signature, unknown kid, malformed JWT |
| Acceptance (A1) | 1 | Valid token returns normalized `JwtClaims` |
| Behavioral contract | 3 | Satisfies Protocol, idempotent, no SDK type leakage |

---

## Step 3 -- Tool ACL: Role-Based Access Matrix

The `WorkOSRoleAcl` adapter enforces a default-deny, fail-closed policy. Only `admin` gets `shell` access.

```bash
pytest tests/middleware/adapters/acl/test_workos_role_acl.py -v
```

**Expected output -- 12 tests, all pass:**

```
TestRejectionPaths::test_R1_beta_user_denied_shell                      PASSED
TestRejectionPaths::test_R2_unknown_role_denied                          PASSED
TestRejectionPaths::test_R3_viewer_denied_all_tools                      PASSED
TestRejectionPaths::test_R4_unknown_tool_denied_for_admin                PASSED
TestRejectionPaths::test_R5_empty_roles_denied                           PASSED
TestAcceptancePaths::test_A1_admin_allowed_shell                         PASSED
TestAcceptancePaths::test_A2_beta_allowed_file_io                        PASSED
TestAcceptancePaths::test_A3_beta_allowed_web_search                     PASSED
TestBehavioralContract::test_provider_satisfies_protocol                 PASSED
TestBehavioralContract::test_decide_is_idempotent                        PASSED
TestBehavioralContract::test_decide_never_raises                         PASSED
TestBehavioralContract::test_first_role_wins_for_audit_trace             PASSED
```

**Policy table (from `middleware/composition.py`):**

| Role | `shell` | `file_io` | `web_search` |
|---|---|---|---|
| `admin` | Allowed | Allowed | Allowed |
| `beta` | **Denied** | Allowed | Allowed |
| `viewer` | Denied | Denied | Denied |
| `member` | Denied | Denied | Denied |
| Unknown role | Denied | Denied | Denied |

---

## Step 4 -- Tool ACL: Integrated HTTP Endpoint

The server tests boot a full `FastAPI` `TestClient` and exercise JWT + ACL through the actual `/acl/decide` route.

```bash
pytest tests/middleware/test_server.py -v
```

**Expected output -- 13 tests, all pass:**

```
TestLiveness::test_healthz_returns_200_without_token                     PASSED
TestAuthRejectionPaths::test_missing_bearer_returns_401                  PASSED
TestAuthRejectionPaths::test_malformed_authorization_header_returns_401  PASSED
TestAuthRejectionPaths::test_invalid_token_returns_401                   PASSED
TestAuthRejectionPaths::test_expired_token_returns_401                   PASSED
TestAuthRejectionPaths::test_wrong_issuer_returns_401                    PASSED
TestAuthAcceptance::test_valid_token_returns_subject                     PASSED
TestToolAclEnforcement::test_beta_calling_shell_returns_403              PASSED
TestToolAclEnforcement::test_admin_calling_shell_returns_200             PASSED
TestToolAclEnforcement::test_beta_calling_file_io_returns_200            PASSED
TestToolAclEnforcement::test_unknown_role_calling_anything_returns_403   PASSED
TestLangGraphConfig::test_langgraph_json_exists                          PASSED
TestLangGraphConfig::test_langgraph_json_references_react_loop           PASSED
```

The `/acl/decide` endpoint returns `200` with `allowed: true` on success, or `403` with an audit-quality denial reason on rejection.

---

## Step 5 -- Run a CLI Agent Session

This runs the full ReAct graph with a real LLM call, generating all observability and governance artifacts.

```bash
# Source .env so the API key is available
set -a && source .env && set +a

python cli.py "What is the capital of France?"
```

**Example output:**

```
Task: What is the capital of France?
workflow_id=wf-21b731f5 task_id=task-2e51b196

services.governance.black_box INFO Recorded task_started for workflow wf-21b731f5
services.governance.black_box INFO Recorded guardrail_checked for workflow wf-21b731f5
services.prompt_service INFO Rendered template input_guardrail.j2
services.llm_config INFO Invoking gpt-4o-mini (fast tier)
services.guardrails INFO Guardrail prompt_injection: accepted
services.governance.black_box INFO Recorded guardrail_checked for workflow wf-21b731f5
services.governance.phase_logger INFO Decision [routing]: Selected gpt-4o
services.governance.black_box INFO Recorded model_selected for workflow wf-21b731f5
services.prompt_service INFO Rendered template system_prompt.j2
services.llm_config INFO Invoking gpt-4o (capable tier) with 2 messages, 3 tools
services.governance.black_box INFO Recorded step_executed for workflow wf-21b731f5
services.governance.phase_logger INFO Decision [evaluation]: Outcome: success

╭──────────────────────────────── Final Answer ────────────────────────────────╮
│ FINAL ANSWER: Paris                                                          │
╰──────────────────────────────────────────────────────────────────────────────╯
Steps: 1 | Cost: $0.0024
```

**Artifacts created:**

| Path | Content |
|---|---|
| `cache/black_box_recordings/wf-21b731f5/trace.jsonl` | Tamper-proof event chain |
| `cache/phase_logs/wf-21b731f5/decisions.jsonl` | Routing + evaluation decisions |
| `cache/agent_facts/cli-agent.json` | Signed agent identity |
| `cache/checkpoints.db` | SQLite graph checkpoints |
| `logs/*.log` | Per-concern structured log files |

Note the `workflow_id` (`wf-21b731f5`) -- use it to query all artifacts in subsequent steps.

---

## Step 6 -- Observability: Structured Log Files

`logging.json` routes each service's logger to a dedicated file under `logs/`. After the CLI run, these files contain:

**`logs/identity.log`** -- Agent registration:
```
2026-04-26 07:13:57,558 services.governance.agent_facts INFO Registered agent cli-agent by cli-bootstrap
```

**`logs/guards.log`** -- Guardrail verdicts:
```
2026-04-26 07:14:11,896 services.guardrails INFO Guardrail prompt_injection: accepted
```

**`logs/prompts.log`** -- Template rendering:
```
2026-04-26 07:14:07,343 services.prompt_service INFO Rendered template input_guardrail.j2
2026-04-26 07:14:11,904 services.prompt_service INFO Rendered template system_prompt.j2
```

**`logs/black_box.log`** -- Recorder activity:
```
2026-04-26 07:14:07,341 services.governance.black_box INFO Recorded task_started for workflow wf-21b731f5
2026-04-26 07:14:07,342 services.governance.black_box INFO Recorded guardrail_checked for workflow wf-21b731f5
2026-04-26 07:14:11,896 services.governance.black_box INFO Recorded guardrail_checked for workflow wf-21b731f5
2026-04-26 07:14:11,900 services.governance.black_box INFO Recorded model_selected for workflow wf-21b731f5
2026-04-26 07:14:13,654 services.governance.black_box INFO Recorded step_executed for workflow wf-21b731f5
```

**`logs/phases.log`** -- Decision rationale:
```
2026-04-26 07:14:11,899 services.governance.phase_logger INFO Decision [routing]: Selected gpt-4o
2026-04-26 07:14:13,657 services.governance.phase_logger INFO Decision [evaluation]: Outcome: success
```

**`logs/evals.log`** -- Eval capture (LLM call records):
```
2026-04-26 07:14:11,897 services.eval_capture INFO AI Response
2026-04-26 07:14:13,654 services.eval_capture INFO AI Response
```

Each file isolates one concern, making it easy to debug a specific layer without wading through a monolithic log.

---

## Step 7 -- Black Box: The Tamper-Proof Event Chain

The black box recorder (`services/governance/black_box.py`) writes append-only JSONL with SHA-256 hash chaining. Each event's `integrity_hash` incorporates the previous event's hash, creating a linked chain.

```bash
cat cache/black_box_recordings/wf-21b731f5/trace.jsonl | python -m json.tool
```

**Events recorded for session `wf-21b731f5`:**

| # | Event | Details | Hash (truncated) |
|---|---|---|---|
| 1 | `task_started` | `task_input: "What is the capital of France?"` | `cc939ca626ca...` |
| 2 | `guardrail_checked` | `agent_facts` for `cli-agent`, `verified: true` | `ea8aec527ed5...` |
| 3 | `guardrail_checked` | `prompt_injection`, `accepted: true` | `664e96c990f1...` |
| 4 | `model_selected` | `model: gpt-4o`, `reason: capable-for-planning` | `f8219dbeb8a8...` |
| 5 | `step_executed` | `model: gpt-4o`, 469 tokens in, 6 out, $0.0024, 1750ms | `867f0154651a...` |

Each event contains: `event_id` (UUID), `workflow_id`, `event_type`, `timestamp`, `details`, and `integrity_hash`.

---

## Step 8 -- Black Box: Verify Hash Chain Integrity

The `BlackBoxRecorder.export()` method reads the JSONL file, recomputes each hash, and reports whether the chain is intact.

```python
from services.governance.black_box import BlackBoxRecorder
from pathlib import Path

recorder = BlackBoxRecorder(Path("cache/black_box_recordings"))
bundle = recorder.export("wf-21b731f5")
print(f"Chain valid: {bundle['hash_chain_valid']}")  # True
print(f"Events: {len(bundle['events'])}")             # 5
```

**Tamper detection demo:** Modifying even a single character in any event causes the chain to break:

| Action | `hash_chain_valid` |
|---|---|
| Original (untouched) | `True` |
| Changed event 1's `task_input` | `False` |
| Restored to original | `True` |

When tampering is detected, the export identifies the exact event where the chain broke.

---

## Step 9 -- Phase Logger: Routing and Evaluation Decisions

The phase logger (`services/governance/phase_logger.py`) records the rationale behind every routing and evaluation decision.

```bash
cat cache/phase_logs/wf-21b731f5/decisions.jsonl | python -m json.tool
```

**Decision 1 -- Routing:**

```json
{
  "timestamp": "2026-04-26T12:14:11.899690+00:00",
  "workflow_id": "wf-21b731f5",
  "phase": "routing",
  "description": "Selected gpt-4o",
  "alternatives": ["gpt-4o-mini"],
  "rationale": "capable-for-planning (step=0, errors=0, last_err=none, cost_usd=0.0000)",
  "confidence": 0.75
}
```

The router chose `gpt-4o` (capable tier) over `gpt-4o-mini` (fast tier) because this was the first step with no error history and budget was available.

**Decision 2 -- Evaluation:**

```json
{
  "timestamp": "2026-04-26T12:14:13.657334+00:00",
  "workflow_id": "wf-21b731f5",
  "phase": "evaluation",
  "description": "Outcome: success",
  "alternatives": ["retry", "escalate", "terminal"],
  "rationale": "Step completed successfully",
  "confidence": 1.0
}
```

The evaluator determined "Paris" was a satisfactory final answer with full confidence. No retry or escalation needed.

---

## Step 10 -- Compliance Export: Join Everything

The compliance export joins black box events, agent identity, and phase decisions into a single audit bundle.

```python
from services.governance.black_box import BlackBoxRecorder
from services.governance.phase_logger import PhaseLogger
from services.governance.agent_facts_registry import AgentFactsRegistry
from pathlib import Path

cache = Path("cache")
recorder = BlackBoxRecorder(cache / "black_box_recordings")
phase_logger = PhaseLogger(cache / "phase_logs")
registry = AgentFactsRegistry(
    cache / "agent_facts",
    secret="dev-secret-do-not-use-in-production",
)

bundle = recorder.export_for_compliance(
    "wf-21b731f5",
    agent_facts_registry=registry,
    phase_logger=phase_logger,
)
```

The bundle contains:

| Section | What it answers |
|---|---|
| `hash_chain_valid` | Has the audit trail been tampered with? |
| `events` | **What** happened during the session (tamper-proof) |
| `agent_facts` | **Who** ran the session (signed identity) |
| `phase_decisions` | **Why** each decision was made (rationale + confidence) |

---

## Summary

| Layer | Purpose | Key Files | Artifacts |
|---|---|---|---|
| **JWT Auth** | Prove identity | `middleware/ports/jwt_verifier.py`, `middleware/adapters/auth/workos_jwt_verifier.py` | HTTP 200/401 |
| **Tool ACL** | Authorize actions | `middleware/ports/tool_acl.py`, `middleware/adapters/acl/workos_role_acl.py` | HTTP 200/403 |
| **Observability** | Monitor operations | `services/observability.py`, `logging.json` | `logs/*.log` |
| **Black Box** | Audit compliance | `services/governance/black_box.py`, `services/governance/phase_logger.py` | `cache/black_box_recordings/`, `cache/phase_logs/` |

---

## Key Source Files

| File | Role |
|---|---|
| `middleware/__main__.py` | Dev entry point with permissive auth |
| `middleware/server.py` | Production app with WorkOS JWT + ACL |
| `middleware/composition.py` | Single wiring point for all adapters |
| `middleware/ports/jwt_verifier.py` | Vendor-neutral JWT verification contract |
| `middleware/ports/tool_acl.py` | Vendor-neutral tool ACL contract |
| `services/governance/black_box.py` | Append-only JSONL recorder with SHA-256 chain |
| `services/governance/phase_logger.py` | Per-decision routing/evaluation logs |
| `services/observability.py` | Logging setup + framework telemetry |
| `orchestration/react_loop.py` | Graph nodes that drive all four layers |
| `logging.json` | Per-concern log routing configuration |
| `tests/middleware/conftest.py` | In-process RSA keys + JWKS fixtures for testing |
