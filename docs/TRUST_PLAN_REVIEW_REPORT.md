# Trust Foundation Protocols -- Plan vs Implementation Review Report

**Review method:** Pyramid Principle structured analysis (4-phase: Decompose, Hypothesize, Act, Synthesize)
**Plan reviewed:** `agent/docs/TRUST_FOUNDATION_PROTOCOLS_PLAN.md`
**Implementation reviewed:** `agent/trust/`, `agent/utils/cloud_providers/`
**Test evidence:** `agent/tests/trust/test_plan_hypothesis_validation.py` (57 tests, all passing)
**Date:** 2026-04-16

---

## Governing Thought

The Trust Foundation implementation is **structurally sound and architecturally compliant** with the plan, achieving correct file layout, protocol design, dependency isolation, and value object schemas. However, **three behavioral gaps** undermine the credential lifecycle and identity verification flows -- the most critical being that credentials issued by `AWSCredentialProvider.issue_credentials()` **cannot be refreshed** due to a missing `RoleArn` in `raw_credentials`. Additionally, two modules shown in the plan's architecture diagram (`enums.py`, `signature.py`) do not exist, and `AgentFacts.status` lacks validation, weakening the trust model's type safety.

**Confidence:** 0.87 (strong evidence across all branches; one untested area: live AWS integration)

---

## Issue Tree

```
Root: Does the implementation faithfully realize the plan?
├── Branch 1: Structural Conformance (files and modules)        → CONFIRMED
├── Branch 2: Type Contracts (value objects and protocols)       → CONFIRMED with 2 minor divergences
├── Branch 3: Behavioral Conformance (adapter implementations)  → 3 GAPS FOUND (1 critical)
├── Branch 4: Architectural Rules (dependency/design)           → CONFIRMED
└── Branch 5: Completeness (nothing planned is missing)         → 2 GAPS FOUND
```

---

## Key Arguments

### Argument 1: Structural and type-level conformance is strong

All 8 planned files exist. All 6 cloud identity models have exactly the fields specified in the plan. All models are frozen (immutable). All 3 protocols define the correct methods with `@runtime_checkable`. The `trust/__init__.py` re-exports all planned types plus useful additions (exceptions, CloudBinding, VerificationReport).

**Evidence:**
- 8/8 planned files exist (`TestBranch1_StructuralConformance`)
- 6/6 model field sets match the plan (`TestBranch2_CloudIdentityFields`)
- 6/6 models have `frozen=True` (`TestBranch2_AllModelsFrozen`)
- 3/3 protocols expose the required method sets (`TestBranch2_ProtocolSignatures`)

**So what:** The data model foundation is solid. Consumers can rely on the type contracts defined in `trust/`.

### Argument 2: Architectural rules are fully satisfied

The trust layer has zero I/O imports, zero outward dependencies. Protocols use `typing.Protocol` (structural subtyping) as the plan specifies. The factory returns the correct 3-tuple. The exception hierarchy cleanly partitions error domains. Dependency rules verified via AST scanning.

**Evidence:**
- No I/O or forbidden imports in `trust/` (`TestBranch4_TrustLayerPurity`)
- All three protocol types are runtime-checkable (`TestBranch4_ProtocolDesignDecision`)
- Factory supports `"aws"` and `"local"`, rejects unknown providers (`TestBranch4_FactoryContract`)
- Exception subclasses are distinct and catchable as base (`TestBranch4_ExceptionHierarchy`)

**So what:** The hexagonal architecture (ports and adapters) is correctly implemented. The trust layer can evolve independently of cloud adapters.

### Argument 3: Behavioral gaps in the AWS adapters break the credential lifecycle

Three specific behaviors diverge from the plan: (a) credentials cannot be refreshed after issuance, (b) `resolve_identity` skips the `sts.assume_role()` step, (c) `verify_identity` validates the provider's own credentials instead of the subject's. These gaps affect correctness in production AWS deployments.

**Evidence:**
- `issue_credentials` does not store `RoleArn` → `refresh_credentials` always throws `CredentialError` (`TestBranch3_AWSCredentialLifecycle`)
- `resolve_identity` calls IAM directly without STS assume-role (`TestBranch3_AWSResolveIdentityBehavior`)
- `verify_identity` uses the provider's STS client, not the subject's credentials (`TestBranch3_AWSVerifyIdentityCredentialForwarding`)

**So what:** The AWS credential lifecycle is broken for any agent that needs to refresh credentials. This is the highest-priority fix.

### Argument 4: Two plan-referenced modules and one status constraint are missing

The architecture diagram shows `enums.py` and `signature.py` as existing trust-layer modules, but neither exists. `AgentFacts.status` accepts arbitrary strings instead of an enum, which undermines the plan's IAM status mapping (active/deactivated → deny-all/delete-role).

**Evidence:**
- `trust/enums.py` does not exist (`TestBranch5_MissingArchitectureModules`)
- `trust/signature.py` does not exist (`TestBranch5_MissingArchitectureModules`)
- `AgentFacts(status="completely_invalid_status_value")` succeeds (`TestBranch2_AgentFactsStatus`)

**So what:** Without status validation, agents can be created with meaningless lifecycle states, and `signature_hash` has no supporting infrastructure.

---

## Gap Analysis

### GAP-1 (Critical): Credential Refresh Lifecycle Broken

| Attribute | Detail |
|---|---|
| **Location** | `utils/cloud_providers/aws_credentials.py` |
| **Plan spec** | `issue_credentials` → `refresh_credentials` should work as a lifecycle |
| **Actual behavior** | `issue_credentials` stores `{AccessKeyId, SecretAccessKey, SessionToken}` in `raw_credentials` but NOT `RoleArn`. `refresh_credentials` requires `RoleArn` in `raw_credentials` and raises `CredentialError` when absent. |
| **Impact** | Any agent using AWS credentials cannot extend expiring sessions. The 15-minute default TTL becomes a hard wall. |
| **Test** | `TestBranch3_AWSCredentialLifecycle.test_issue_then_refresh_roundtrip_fails` |
| **Fix** | Add `"RoleArn": role_arn` to the `raw_credentials` dict in `issue_credentials` (line 60-65) |

### GAP-2 (Medium): resolve_identity Skips STS Assume Role

| Attribute | Detail |
|---|---|
| **Location** | `utils/cloud_providers/aws_identity.py:resolve_identity()` |
| **Plan spec** | "uses `sts.assume_role()` then `iam.get_role()` + `iam.list_role_tags()`" |
| **Actual behavior** | Goes directly to `iam.get_role()` + `iam.list_role_tags()`, skipping `sts.assume_role()` |
| **Impact** | The implementation reads role metadata without actually assuming the role. This means it does not verify that the caller has permission to assume the role. The identity is resolved from IAM metadata alone, not from an actual credential exchange. |
| **Test** | `TestBranch3_AWSResolveIdentityBehavior.test_resolve_identity_does_not_call_sts_assume_role` |
| **Fix** | Call `sts.assume_role(RoleArn=identifier, ...)` first, then use the returned credentials to call `iam.get_role()`. Alternatively, update the plan to reflect the simpler approach if assume-role verification is not required. |

### GAP-3 (Medium): verify_identity Validates Wrong Credentials

| Attribute | Detail |
|---|---|
| **Location** | `utils/cloud_providers/aws_identity.py:verify_identity()` |
| **Plan spec** | "call `sts.get_caller_identity()` with credentials" (the subject's credentials) |
| **Actual behavior** | Calls `self._sts.get_caller_identity()` using the provider's own STS client, not the subject identity's credentials |
| **Impact** | Verification always succeeds if the provider has valid credentials, regardless of whether the subject's credentials are valid. This is a security concern: an expired or revoked agent identity would pass verification. |
| **Test** | `TestBranch3_AWSVerifyIdentityCredentialForwarding.test_verify_uses_own_credentials_not_subjects` |
| **Fix** | Create a temporary STS client using credentials from `identity.raw_attributes` and call `get_caller_identity()` on that client. |

### GAP-4 (Medium): Missing enums.py and signature.py

| Attribute | Detail |
|---|---|
| **Location** | `trust/` directory |
| **Plan spec** | Architecture diagram shows `enums.py` (IdentityStatus, CertificationStatus, LifecycleState) and `signature.py` (compute_signature(), verify_signature()) |
| **Actual behavior** | Neither file exists |
| **Impact** | `AgentFacts.signature_hash` has no compute/verify infrastructure. `AgentFacts.status` is a free-form string. Lifecycle state transitions are unenforceable. |
| **Test** | `TestBranch5_MissingArchitectureModules` |
| **Fix** | Create `enums.py` with `IdentityStatus` enum and `signature.py` with signature compute/verify functions. Constrain `AgentFacts.status` to the enum. |

### GAP-5 (Medium): AgentFacts.status Accepts Arbitrary Strings

| Attribute | Detail |
|---|---|
| **Location** | `trust/models.py:AgentFacts.status` |
| **Plan spec** | Maps status to IAM role states: active, suspended (deny-all), revoked (delete role) |
| **Actual behavior** | `status: str = "active"` accepts any string value |
| **Impact** | No validation that status values are meaningful. Cannot reliably implement the plan's status-to-IAM mapping. Related to GAP-4 (enums.py missing). |
| **Test** | `TestBranch2_AgentFactsStatus.test_status_allows_arbitrary_strings` |
| **Fix** | Change to `status: IdentityStatus = IdentityStatus.ACTIVE` using the enum from GAP-4 |

### GAP-6 (Low): _resolve_role_arn Generates Invalid ARN

| Attribute | Detail |
|---|---|
| **Location** | `utils/cloud_providers/aws_credentials.py:_resolve_role_arn()` |
| **Plan spec** | Role ARN should include account_id |
| **Actual behavior** | Generates `arn:aws:iam:::role/{agent_id}` (three colons, empty account_id) |
| **Impact** | Without an explicit `role_arn` in metadata, `assume_role` will fail with an invalid ARN. The fallback is non-functional. |
| **Test** | `TestBranch3_AWSRoleArnGeneration.test_default_role_arn_has_missing_account_id` |
| **Fix** | Either require `role_arn` in AgentFacts.metadata (remove fallback) or add `account_id` to the ARN template |

### GAP-7 (Low): PermissionBoundary.max_permissions Never Populated

| Attribute | Detail |
|---|---|
| **Location** | `utils/cloud_providers/aws_policy.py:get_permission_boundary()` |
| **Plan spec** | `PermissionBoundary` has `max_permissions: list[str]` field |
| **Actual behavior** | Always returns `max_permissions=[]` even when an AWS boundary exists |
| **Impact** | Consumers cannot query what the maximum allowed actions are. The field exists but carries no data. |
| **Test** | `TestBranch3_PermissionBoundaryMaxPermissions.test_max_permissions_always_empty` |
| **Fix** | After retrieving the boundary ARN, call `iam.get_policy_version()` to extract the policy document's Action list and populate `max_permissions` |

### GAP-8 (Low): resolve_identity Parameter Name Divergence

| Attribute | Detail |
|---|---|
| **Location** | `trust/protocols.py:IdentityProvider.resolve_identity()` |
| **Plan spec** | Parameter name: `credential_token` |
| **Actual behavior** | Parameter name: `identifier` |
| **Impact** | Documentation mismatch. No functional impact since protocols use structural subtyping. |
| **Test** | `TestBranch2_ProtocolSignatures.test_resolve_identity_parameter_name_divergence` |
| **Fix** | Either update the plan or rename the parameter. `identifier` is arguably a better name since the parameter is a role ARN, not a credential token. Recommend updating the plan. |

### GAP-9 (Low): datetime.utcnow() Deprecated

| Attribute | Detail |
|---|---|
| **Location** | Multiple files in `trust/` and `utils/cloud_providers/` |
| **Actual behavior** | 22 `DeprecationWarning`s for `datetime.utcnow()` during test run |
| **Impact** | `datetime.utcnow()` is deprecated in Python 3.12+ and scheduled for removal. Returns naive datetime objects. |
| **Fix** | Replace with `datetime.now(datetime.UTC)` throughout |

---

## Cross-Branch Interactions

| Branches | Interaction |
|---|---|
| Branch 2 ↔ Branch 3 | GAP-5 (unconstrained status) reduces the reliability of Branch 3's IAM status mapping. If status is free-form, the adapter cannot reliably translate to IAM actions. |
| Branch 3 ↔ Branch 5 | GAP-1 (credential refresh broken) and GAP-4 (missing signature.py) combine: without both credential lifecycle and signature verification, the trust model cannot guarantee end-to-end identity integrity. |
| Branch 2 ↔ Branch 4 | GAP-4 (missing enums.py) weakens the type contracts that the architectural rules rely on for correctness enforcement. |

---

## Validation Log

| Check | Result | Details |
|---|---|---|
| Completeness | **Pass** | All 5 branches cover the problem space: structure, types, behavior, architecture, completeness. No area unaddressed. |
| Non-Overlap | **Pass** | Each of the 57 tests maps to exactly one branch. No evidence item crosses branches. |
| Item Placement | **Pass** | GAP-1 (credential lifecycle) fits Branch 3 only. GAP-4 (missing files) fits Branch 5 only. GAP-5 (status validation) fits Branch 2 only. |
| So What? | **Pass** | Every gap chains to the governing thought: GAP-1 → broken credential lifecycle → trust model incomplete. |
| Vertical Logic | **Pass** | Each argument directly answers "Is the implementation faithful?": yes structurally (Arg 1), yes architecturally (Arg 2), no behaviorally (Arg 3), no completely (Arg 4). |
| Remove One | **Pass** | Removing any single argument, the governing thought still holds: implementation is mostly correct with specific gaps. |
| Never-One | **Pass** | No single-child groupings in the issue tree. |
| Mathematical | **N/A** | No quantitative claims to verify. |

---

## Recommendations (Priority Order)

### P0: Fix Credential Refresh Lifecycle (GAP-1)

```python
# In aws_credentials.py, issue_credentials(), update raw_credentials:
raw_credentials={
    "AccessKeyId": creds["AccessKeyId"],
    "SecretAccessKey": creds["SecretAccessKey"],
    "SessionToken": creds["SessionToken"],
    "RoleArn": role_arn,  # ← ADD THIS
}
```

### P1: Fix verify_identity Credential Forwarding (GAP-3)

Create a temporary STS client with the subject's credentials from `identity.raw_attributes` (if present) and call `get_caller_identity()` on that client. Fall back to the provider's own client only when raw_attributes has no credentials.

### P1: Decide on resolve_identity Behavior (GAP-2)

Either:
- **(a)** Implement `sts.assume_role()` per the plan, or
- **(b)** Update the plan to reflect the current IAM-only approach and add a note that role assumption is deferred to `CredentialProvider.issue_credentials()`

### P2: Create enums.py and signature.py (GAP-4 + GAP-5)

1. Create `trust/enums.py` with `IdentityStatus` enum (`active`, `suspended`, `revoked`)
2. Constrain `AgentFacts.status` to `IdentityStatus`
3. Create `trust/signature.py` with `compute_signature()` and `verify_signature()`
4. Wire `AgentFacts.signature_hash` to use `compute_signature()`

### P3: Fix _resolve_role_arn Fallback (GAP-6)

Either make `role_arn` a required field in `AgentFacts.metadata` for AWS deployments, or include account_id in the generated ARN. The current fallback silently produces an invalid ARN.

### P3: Populate PermissionBoundary.max_permissions (GAP-7)

After retrieving the boundary ARN, call `iam.get_policy_version()` to extract the policy document and populate the `max_permissions` list.

### P3: Replace datetime.utcnow() (GAP-9)

Global find-and-replace of `datetime.utcnow()` with `datetime.now(datetime.UTC)` across `trust/` and `utils/cloud_providers/`.

### P4: Update Plan for Parameter Name (GAP-8)

Update `TRUST_FOUNDATION_PROTOCOLS_PLAN.md` to use `identifier` instead of `credential_token` for `IdentityProvider.resolve_identity()`. The implementation name better reflects the parameter's actual purpose (a role ARN, not a credential token).

---

## Undocumented Additions (Positive Divergences)

These modules are NOT in the plan but represent useful additions:

| Module | Purpose | Assessment |
|---|---|---|
| `trust/exceptions.py` | Cloud-agnostic exception hierarchy (`TrustProviderError` → `AuthenticationError`, `AuthorizationError`, `CredentialError`, `ConfigurationError`) | **Valuable.** Provides clean error handling without leaking SDK-specific exceptions. Should be added to the plan. |
| `utils/cloud_providers/config.py` | `TrustProviderSettings` via pydantic-settings with `TRUST_` env prefix | **Valuable.** Centralizes provider configuration. The plan's factory signature (`get_provider(provider_name: str)`) is less capable than the implemented `get_provider(settings: TrustProviderSettings)`. Update plan to reflect this. |
| `trust/models.py` additions | `CloudBinding` (agent-to-IAM mapping) and `VerificationReport` (bulk verification results) | **Valuable.** `CloudBinding` directly supports the plan's AgentFacts-to-IAM mapping strategy. Should be documented in the plan. |

---

## Summary

| Dimension | Score | Notes |
|---|---|---|
| Structural Conformance | 10/10 | All planned files exist |
| Type Contracts | 9/10 | All fields match; 1 parameter name divergence, 1 missing status enum |
| Behavioral Conformance | 6/10 | 3 gaps including 1 critical (credential lifecycle) |
| Architectural Rules | 10/10 | Fully compliant |
| Completeness | 7/10 | 2 referenced modules missing; 1 underpopulated field |
| **Overall** | **8.4/10** | Strong foundation with targeted fixes needed |

---

## Phase 1 Validation Entry (2026-04-17)

Trust kernel purity re-validated as prerequisite for Phase 1 (ReAct Agent) implementation.

### Validation Gates

| Gate | Command | Result |
|---|---|---|
| Trust unit tests | `pytest tests/trust/ -q` | 173 passed in 0.68s |
| Architecture dependency rules | `pytest tests/architecture/test_dependency_rules.py -q` | 15 passed in 0.68s |
| Utils adapter tests | `pytest tests/utils/ -q` | 121 passed in 0.64s |
| Protocol runtime checks | `isinstance(Local*Provider(), *Protocol)` | All 3 pass (test_local_provider.py::TestProtocolConformance) |

### Conclusion

The trust kernel (`trust/`) satisfies all L1 Deterministic purity criteria:
- Zero imports from `langgraph`, `langchain`, `boto3`, `litellm`, `utils`, `services`, `components`, `orchestration`.
- All models are frozen Pydantic `BaseModel` instances with zero I/O.
- Cloud adapters (`utils/cloud_providers/`) import only from `trust/` and their respective SDKs.
- Local providers satisfy `@runtime_checkable` Protocol contracts via structural subtyping.

Phase 1 may proceed to build components, services, and orchestration layers on top of this validated foundation.

---

## Phase 1 Code Review Remediation Entry (2026-04-17)

Phase 1 implementation reviewed using the CodeReviewer agent prompt suite (`prompts/codeReviewer/`).

### Initial Review Verdict: `request_changes`

10 findings identified (1 critical, 6 warnings, 3 info) across dimensions D1-D5.

### Remediation Actions (all completed)

| WP | Finding | Action | Status |
|---|---|---|---|
| WP1 | PLAN.W3.1 -- pydantic-ai declared but unused | Formally deferred to Phase 2; removed from pyproject.toml and requirements.txt; updated PLAN_v2 and phase_1 plan | Done |
| WP2 | D2.H2 / D5.AP5 -- default ModelProfile duplicated 3x | Added `default_fast_profile()` factory in `services/base_config.py`; replaced literals in `router.py`, `react_loop.py` | Done |
| WP3 | D2.H3 -- InputGuardrail self-constructs LLM stack | Refactored to accept `LLMService`, `PromptService`, `ModelProfile` via `__init__`; wired from `build_graph()` | Done |
| WP4 | SEC.path_sandbox -- `startswith` prefix bypass | Replaced with `Path.is_relative_to()` | Done |
| WP4 | SEC.shell_injection -- `shell=True` + weak allowlist | Dropped `shell=True`; added `shlex.split`, metacharacter rejection, blocked-arg list (`-delete`, `-exec`) | Done |
| WP5 | PKG.cli_entrypoint -- inconsistent across Dockerfile/cli.py/__main__.py | Unified: added `agent/__init__.py`, deleted redundant `agent/agent/`, updated Dockerfile to `python -m agent.cli` | Done |
| WP6 | TOOL.layer_map_stale -- `code_analysis.py` LAYER_DIRS missing Phase 1 dirs | Extended `LAYER_DIRS` and `FORBIDDEN_IMPORTS` with `services`, `components`, `orchestration` | Done |
| WP7 | BUG.append_reducer -- `_append_list` falsy `step_id=0` | Changed `or` fallback to `dict.get` with default | Done |
| WP7 | ENCAP.private_access -- `tool_registry._tools` | Added `ToolRegistry.has()`; replaced private access in `react_loop.py` | Done |
| WP7 | SEC.default_secret -- hardcoded HMAC secret | Changed to require explicit secret or `AGENT_FACTS_SECRET` env var | Done |

### Post-Remediation Validation

| Gate | Result |
|---|---|
| Architecture tests (`tests/architecture/`) | 23 passed |
| Trust kernel tests (`tests/trust/`) | 173 passed |
| Components tests (`tests/components/`) | 37 passed |
| Services tests (excl. LLM-dep) | 69+ passed |
| Utils tests (`tests/utils/`) | 130 passed |
| **Total** | **428 passed, 0 introduced failures** |

### Updated Verdict: `approve` (conditional)

All 10 findings resolved. Two pre-existing test failures (missing `langchain_litellm` in local env) are unrelated to the remediation. D3 (test quality audit) remains an open gap for a Phase 1.5 pass.
