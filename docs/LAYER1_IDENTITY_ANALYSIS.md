# Layer 1: Identity and Authentication -- Structured Analysis

**Analysis method:** Pyramid Principle with MECE decomposition  
**Source documents:**
- `agent/TrustFrameworkAnd Governance.md` (Seven-Layer Agent Trust Framework)
- `agent/governanaceTriangle/03_agentfacts_governance.md` (AgentFacts tutorial)
- `agent/PLAN.md` (ReAct agent architecture)
- `agent/research/pyramid_react_system_prompt.md` (analysis protocol)

---

## Problem Definition

**Original statement:** Understand Layer 1 (Identity and Authentication) of the Seven-Layer Agent Trust Framework, as it maps to the AgentFacts pillar of the Governance Triangle, for the purpose of designing the AgentFacts framework implementation.

**Restated question:** What are the complete, non-overlapping dimensions of agent identity and authentication that the AgentFacts framework must implement to satisfy Layer 1 of the trust framework, and for each dimension, what is the specific design requirement?

**Problem type:** Design

**Scope boundaries:**
- *In scope:* Layer 1 only -- identity, authentication, registration, credential lifecycle, delegation, scaling, monitoring.
- *Out of scope:* Layer 2 (authorization enforcement), Layer 3 (purpose/policy enforcement), Layers 4-7 (observability, certification, lifecycle governance -- these consume identity but don't define it).

**Success criteria:** A MECE issue tree where every requirement from the trust framework's Layer 1 section maps to exactly one branch, every branch has a falsifiable hypothesis about the design approach, and the synthesis produces a governing thought that answers "what must AgentFacts implement for Layer 1?"

---

## Issue Tree

**Ordering type:** Structural/Process (follows the natural lifecycle of an agent identity: created, verified, evolved, delegated, scaled, monitored)

```
Root: What are the dimensions of agent identity that AgentFacts must implement?
│
├── Branch 1: Identity Establishment
│   (How is an agent's identity created and what constitutes it?)
│   ├── 1a: Unique Identification
│   │   (What uniquely identifies an agent across the fleet?)
│   └── 1b: Organizational Binding
│       (How is identity linked to ownership, team, and governance structures?)
│
├── Branch 2: Cryptographic Integrity
│   (How is identity made tamper-proof and verifiable?)
│   ├── 2a: Signature Computation
│   │   (How are identity cards signed and what fields are covered?)
│   ├── 2b: Verification Protocol
│   │   (How does a receiving system validate an identity card?)
│   └── 2c: Supply Chain Attestation
│       (How is the provenance of the agent's code/build verified?)
│
├── Branch 3: Credential Lifecycle
│   (How do credentials change over time without breaking trust?)
│   ├── 3a: Rotation and Renewal
│   │   (How are signatures and credentials refreshed on schedule?)
│   ├── 3b: Revocation
│   │   (How is a compromised or decommissioned identity invalidated?)
│   └── 3c: Expiry
│       (How are short-lived or time-bounded identities enforced?)
│
├── Branch 4: Delegated Authority
│   (How does one agent act on behalf of another without privilege escalation?)
│   ├── 4a: Delegation Tokens
│   │   (What is the scoped, time-bounded credential for delegated action?)
│   └── 4b: Chain of Trust
│       (How is the delegation chain auditable back to the root authority?)
│
├── Branch 5: Multi-Tenancy and Scaling
│   (How does identity work across organizational boundaries and dynamic fleets?)
│   ├── 5a: Namespace Isolation
│   │   (How are identities partitioned by team/tenant/organization?)
│   └── 5b: Dynamic Provisioning
│       (How are identities issued and torn down rapidly for ephemeral agents?)
│
└── Branch 6: Identity Observability
    (How is identity usage monitored, audited, and defended against drift?)
    ├── 6a: Audit Trail
    │   (What is recorded for every identity operation?)
    └── 6b: Drift and Anomaly Detection
        (How is unauthorized reuse, orphaning, or identity drift detected?)
```

### MECE Validation

| # | Test | Result | Details |
|---|------|--------|---------|
| 1 | **Completeness** | Pass | Every paragraph from the trust framework's Layer 1 section maps to one branch. Identity establishment (paras 1-2), cryptographic integrity (paras 3-4 on mTLS/certificates + supply chain attestation), credential lifecycle (para on rotation/renewal/revocation), delegated authority (para on delegation and scoped permissions), multi-tenancy/scaling (para on multitenancy and elasticity), identity observability (final paras on monitoring and drift). |
| 2 | **Non-Overlap** | Pass | Establishment (what the identity *is*) vs. Integrity (how it's *verified*) vs. Lifecycle (how it *changes*) vs. Delegation (how it's *shared*) vs. Scaling (how it *multiplies*) vs. Observability (how it's *monitored*). Each is a distinct phase/concern. |
| 3 | **Item Placement** | Pass | "Agent signature hash" fits Branch 2a only. "OAuth2 access token for child agent" fits Branch 4a only. "Namespace partitioned by tenant" fits Branch 5a only. |
| 4 | **Mathematical** | N/A | Non-quantitative decomposition. |
| 5 | **"Other" Bucket** | Pass | No residual items. Every trust framework Layer 1 requirement maps to a branch. |
| 6 | **Boundary** | Pass | Key boundary: "organizational binding" (1b) vs. "namespace isolation" (5a). Convention: 1b covers the *data model* (owner field, team_email, cost_center). 5a covers the *registry architecture* (how the storage layer partitions by tenant). |

---

## Hypotheses and Resolutions

### Branch 1: Identity Establishment

#### H1a: Unique Identification

**Hypothesis:** A composite key of `namespace + agent_id + version` is sufficient for global uniqueness across a fleet. A bare `agent_id` alone is insufficient because two spokes could independently choose the same name.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_1 | The tutorial uses bare `agent_id` strings like `"invoice-extractor-v2"` with a separate `version` field (`"2.1.0"`). The ID is the *identity*; the version is the *state*. | Tutorial lines 95-100 |
| ev_2 | The trust framework says "identity namespaces *may* need to be partitioned by tenant" -- conditional language tied to scale. | Trust framework line 66 |
| ev_3 | The tutorial's `find_by_owner("finance-team")` provides logical partitioning without namespacing the ID itself. Registration rejects duplicates. | Tutorial lines 127-129 |
| ev_4 | The PLAN.md has no namespace concept in the existing architecture. | PLAN.md lines 164-174 |

**Status: Confirmed with revision.**

The composite key `namespace:agent_id` is the correct *eventual* design, but for Phase 1 a flat `agent_id` with registration-time uniqueness enforcement is sufficient. Namespacing is an additive feature for Phase 2 when multi-spoke isolation is needed.

**Design decision:** `agent_id: str` (required, unique at registration), `version: str` (required, semantic), `namespace: str | None = None` (optional, Phase 2).

---

#### H1b: Organizational Binding

**Hypothesis:** Organizational binding requires at minimum `owner`, `contact`, and `cost_center` as top-level fields.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_5 | The tutorial puts `team_email` and `cost_center` in `metadata`, not as top-level fields. Every example follows this pattern. | Tutorial lines 101-105 |
| ev_6 | The trust framework says "each agent should have a designated owner accountable for ensuring compliance" -- only `owner` is called out as required. | Trust framework line 268 |
| ev_7 | The tutorial's `owner` field is used for registry queries (`find_by_owner`); `team_email` and `cost_center` are never used in any registry operation. | Tutorial lines 127, 134-139 |

**Status: Killed (partially).**

Only `owner` is a governance-grade identity field that the registry needs to operate on. `contact` and `cost_center` are operational metadata that belong in the extensible `metadata` dict. Promoting every operational attribute to a top-level field would bloat the model and create signature churn.

**Design decision:** `owner: str` (required, top-level, in signature). `contact`, `cost_center`, `data_classification` stay in `metadata: dict[str, Any]`.

---

### Branch 2: Cryptographic Integrity

#### H2a: Signature Computation

**Hypothesis:** The signature must cover all governance-relevant fields but exclude operational state. The boundary is: anything that, if changed, would alter what the agent is *authorized* to do must be in the signature.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_8 | The tutorial's `compute_signature` includes `metadata` in the hash. Tutorial examples put *both* governance data (`compliance_frameworks`) and operational data (`last_security_review`, `baseline_accuracy`) in the same `metadata` dict. | Tutorial lines 898-916, 1455-1479 |
| ev_9 | The healthcare case study's metadata includes `deployment_environment` and `incident_response_contact`. If a security contact email changes, the signature breaks -- an operational change, not a governance change. | Tutorial lines 1467-1470 |
| ev_10 | The trust framework treats identity as governance-grade: "no higher-level trust mechanism can operate without certainty about the identity of each agent." The signature should protect what determines *authorization*, not what's *informational*. | Trust framework line 50 |

**Status: Confirmed with critical refinement.**

The current tutorial design has a flaw: `metadata` is a mixed bag of governance and operational data, and including all of it in the signature creates unnecessary churn. The metadata must be split.

**Design decision:** Split into `signed_metadata: dict` (included in signature hash -- compliance_frameworks, model_version, data_classification) and `metadata: dict` (excluded from signature hash -- team_email, cost_center, last_security_review, deployment_environment, baseline_accuracy).

---

#### H2b: Verification Protocol

**Hypothesis:** Verification must be synchronous and blocking at execution time. Asynchronous or periodic verification is insufficient because a tampered agent could execute between checks.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_11 | The tutorial's "Best Practice: Verify Before Execute" is explicit: `if not registry.verify(agent_id): raise SecurityError(...)` -- synchronous, blocking. | Tutorial lines 1028-1052 |
| ev_12 | The trust framework's zero-trust principle: "Never trust, always verify. Each agent interaction... must be explicitly authorized and independently verified." | Trust framework line 90 |
| ev_13 | SHA256 on a ~2-5KB JSON payload takes ~0.001ms. Even at 100 verifications/second, the overhead is negligible. | SHA256 performance characteristics |
| ev_14 | The real latency is disk I/O (~1-5ms for SSD), not SHA256 computation. An in-memory cache with TTL eliminates repeated I/O while preserving the synchronous API. | Tutorial storage design |

**Status: Confirmed.**

Synchronous verification is correct and performant. Disk I/O is the real bottleneck, solvable with an LRU cache.

**Design decision:** `registry.verify(agent_id) -> bool` is synchronous. The registry may use an internal LRU cache with configurable TTL. The cache is an implementation detail, not part of the API contract.

---

#### H2c: Supply Chain Attestation

**Hypothesis:** Supply chain attestation (build signatures, code provenance) can be deferred to Phase 2. It is additive, not foundational.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_15 | The trust framework says attestation is "an additional trust layer *beyond* authentication" -- additive language. | Trust framework line 58 |
| ev_16 | Attestation mechanisms (build attestations, code signatures, HSMs) are infrastructure-heavy and require CI/CD integration. | Trust framework line 58 |
| ev_17 | The tutorial makes no mention of supply chain attestation. Its threat model covers tamper-detection, not provenance. | Tutorial lines 1020-1027 |
| ev_18 | The `signed_metadata` approach provides a natural extension point: build hashes and code signatures go into `signed_metadata` when added. | Derived from H2a resolution |

**Status: Confirmed (defer to Phase 2).**

**Design decision:** No attestation fields in Phase 1. Document `signed_metadata` as the extension point. Add `build_hash`, `code_signature`, `provenance_uri` in Phase 2.

---

### Branch 3: Credential Lifecycle

#### H3a: Rotation and Renewal

**Hypothesis:** Signature rotation is a meaningful registry operation that recomputes the signature periodically.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_19 | SHA256 is a hash function, not a signing key. `compute_signature` is deterministic: given the same fields, it always produces the same hash. There is nothing to "rotate." | Tutorial lines 888-922 |
| ev_20 | The trust framework's rotation language refers to *cryptographic keys* (mTLS, certificates, SPIFFE/SPIRE), not hash functions. The trust framework assumes a key-based model; the tutorial implements a hash-based model. | Trust framework lines 50, 56 |
| ev_21 | Rotation becomes meaningful only if asymmetric signing is introduced in Phase 2 (hub signs registrations with a private key). | Derived from architecture analysis |

**Status: Killed.**

SHA256 hashing has no key to rotate. Instead of rotation, Phase 1 needs *re-verification after schema change* -- if the signature computation algorithm changes, all agents must be re-signed via the registry's `update()` method.

**Design decision:** No `rotate_signature()` method. Add `registry.re_sign_all(reason: str, re_signed_by: str)` for schema migration scenarios. Each re-sign creates an audit entry.

---

#### H3b: Revocation

**Hypothesis:** Revocation must be an explicit, irreversible registry state. A revoked agent cannot be un-revoked.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_22 | The trust framework says "once an agent is decommissioned or compromised, its identity is *no longer* considered valid" -- permanence for decommission. | Trust framework line 56 |
| ev_23 | The trust framework also discusses *quarantine*: "agents attempting unauthorized operations can be denied, throttled, or *quarantined*." Quarantine implies a reversible state. | Trust framework lines 98, 253 |
| ev_24 | The lifecycle model includes active operational states and end states but no explicit suspension state. However, quarantine during Operations/Monitoring is implied. | Trust framework lines 276-302 |
| ev_25 | Financial services operations routinely need reversible suspension: an agent under investigation is suspended, investigated, and either restored or decommissioned. | Domain knowledge (Northern Trust context) |

**Status: Confirmed with two-state model.**

Two states are needed:
1. **Suspended** (reversible): agent fails `verify()`, can be restored after investigation.
2. **Revoked** (irreversible): agent permanently fails `verify()`, cannot be restored.

**Design decision:** Add `status: str` to `AgentFacts`: `"active" | "suspended" | "revoked"`. `verify()` returns `False` for any status other than `"active"`. `registry.suspend()` is reversible via `registry.restore()`. `registry.revoke()` is irreversible. All transitions create audit entries. `status` is NOT in the signature -- tamper detection and lifecycle state are orthogonal checks.

---

#### H3c: Expiry

**Hypothesis:** A `valid_until` timestamp forces periodic re-registration, preventing stale agents with outdated governance metadata.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_26 | The trust framework explicitly says "short-lived or ephemeral agent scenarios, certificates may be short-lived and automatically issued." | Trust framework line 56 |
| ev_27 | The trust framework says "certification is not a onetime event... certification must be treated as an ongoing process." | Trust framework line 237 |
| ev_28 | The PLAN.md includes both persistent agents and potentially ephemeral tool invocations that could become agents. | PLAN.md lines 520-539 |
| ev_29 | In the hub-and-spoke model, expiry forces spoke teams to re-register periodically, ensuring the hub has current metadata. | Hub-and-spoke architecture analysis |

**Status: Confirmed.**

`valid_until` serves two roles: (1) enforcing short lifetimes for ephemeral agents, and (2) forcing periodic re-registration for long-lived agents.

**Design decision:** `valid_until: datetime | None = None` (optional). If set, `verify()` returns `False` after this timestamp even if the signature is intact. If `None`, no expiry (but may still be suspended or revoked). `registry.renew(agent_id, new_valid_until, renewed_by)` extends the lifetime.

---

### Branch 4: Delegated Authority

#### H4a: Delegation Tokens

**Hypothesis:** A separate `DelegationToken` model is needed for scoped, time-bounded agent-to-agent delegation.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_30 | The trust framework describes delegation in terms of "OAuth2 access tokens or signed assertions with scoped permissions and limited lifetimes." This is a runtime authorization concern, not an identity registration concern. | Trust framework line 62 |
| ev_31 | The tutorial's `parent_agent_id` records the relationship but does not carry scope or time bounds. | Tutorial line 914 |
| ev_32 | The PLAN.md does not include agent-to-agent delegation. The ReAct agent calls tools, not other agents. Multi-agent orchestration is not in the Phase 1-4 plan. | PLAN.md full file |
| ev_33 | In the hub-and-spoke model, the primary delegation is: hub authorizes spoke, spoke registers agent. This is one-hop, captured by `parent_agent_id` and `registered_by`. | Hub-and-spoke architecture analysis |

**Status: Killed for Phase 1. Confirmed as Phase 2.**

`parent_agent_id` is sufficient to record the delegation relationship. A `DelegationToken` model becomes necessary when multi-agent orchestration exists and delegation scope needs to be dynamic.

**Design decision:** Keep `parent_agent_id: str | None = None` as a relationship marker. No `DelegationToken` in Phase 1. Document as Phase 2 extension.

---

#### H4b: Chain of Trust

**Hypothesis:** Delegation chains must be traversable (A -> B -> C back to root) with broken-link verification.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_34 | With H4a killed for Phase 1, chain traversal is moot. No multi-hop delegation in the current architecture. | Derived from ev_32, ev_33 |
| ev_35 | The hub-and-spoke model is two levels: hub -> spoke agent. The hub is the registry itself, not an agent with its own `AgentFacts`. The "chain" is always depth 1. | Hub-and-spoke architecture analysis |
| ev_36 | The trust framework says "agents often act on behalf of users *or other agents*" but the multi-agent case requires infrastructure from H4a. | Trust framework line 62 |

**Status: Killed for Phase 1.**

Single-hop `parent_agent_id` is sufficient. Chain traversal becomes relevant when multi-hop delegation exists.

**Design decision:** `parent_agent_id` is a simple string reference, not a validated foreign key. The registry does not enforce referential integrity. Phase 2 adds referential integrity when delegation chains become real.

---

### Branch 5: Multi-Tenancy and Scaling

#### H5a: Namespace Isolation

**Hypothesis:** Each spoke gets a namespace; fully qualified identity is `{namespace}:{agent_id}`.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_37 | The trust framework uses conditional language: "identity namespaces *may* need to be partitioned by tenant." | Trust framework line 66 |
| ev_38 | The tutorial operates in a flat namespace. `find_by_owner` provides logical partitioning without namespacing. | Tutorial lines 92-129 |
| ev_39 | At expected fleet size (dozens to hundreds per spoke across 4 spokes), naming collisions are manageable through conventions. | Hub-and-spoke fleet sizing |
| ev_40 | Namespace support is cheap to add later if `agent_id` is treated as opaque by the registry. | Registry architecture analysis |

**Status: Confirmed as Phase 2. Flat namespace for Phase 1.**

**Design decision:** `agent_id: str` is opaque to the registry. No namespace field in Phase 1. Convention-based naming (e.g., `{spoke}-{agent}-v{n}`). Phase 2 adds `namespace: str | None = None` and partitioned storage.

---

#### H5b: Dynamic Provisioning

**Hypothesis:** The registry must support rapid automated registration for ephemeral agents.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_41 | The trust framework says "rapid automated issuance and teardown of identities without human intervention." | Trust framework line 66 |
| ev_42 | Registration is two file writes (JSON + JSONL append). On SSD: ~5-15ms total. Already fast enough for ephemeral agents. | Registry storage design analysis |
| ev_43 | The PLAN.md's tool executors are stateless and could become agents in a multi-agent expansion, requiring fast registration. | PLAN.md lines 488-519 |
| ev_44 | Deregistration (teardown) is not in the current tutorial API. Ephemeral agents need register -> execute -> deregister. | Tutorial API analysis (gap) |

**Status: Confirmed. Achievable without special optimization.**

The current file-based design already meets latency requirements. The missing piece is `deregister()`.

**Design decision:** Add `registry.deregister(agent_id, reason, deregistered_by)` that creates a final audit entry, archives the agent JSON (for compliance retention), and removes it from the active registry. `valid_until` (from H3c) provides automatic expiry as a safety net.

---

### Branch 6: Identity Observability

#### H6a: Audit Trail

**Hypothesis:** Per-agent JSONL files with `{timestamp, action, agent_id, changed_by, changes, previous_signature, new_signature}`.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_45 | The tutorial defines exactly this structure in `AuditEntry`. | Tutorial lines 1073-1101 |
| ev_46 | The trust framework says "all authenticated activity should be recorded with identity-aware logs, allowing system administrators to trace behaviors back to specific agents." | Trust framework line 70 |
| ev_47 | The tutorial's `export_for_audit()` combines per-agent trails into a single compliance export. Per-agent files are storage; cross-fleet queries are via the export function. | Tutorial lines 1108-1163 |
| ev_48 | The PLAN.md uses per-concern log files. Per-agent audit trail files follow the same pattern. | PLAN.md lines 586-598 |
| ev_49 | Cross-fleet query ("all registrations in last 24 hours") via `list_all()` + filtering is O(n) in agents -- acceptable for fleet sizes in the hundreds. | Performance analysis |

**Status: Confirmed.**

**Design decision:** `audit_trails/{agent_id}_audit.jsonl` -- one file per agent, append-only JSONL. `AuditEntry` matches the tutorial's design. Phase 2 adds centralized `registry_events.jsonl` for time-range queries.

---

#### H6b: Drift and Anomaly Detection

**Hypothesis:** Identity drift detection requires both periodic bulk verification and orphan detection.

**Evidence:**

| ID | Fact | Source |
|----|------|--------|
| ev_50 | The trust framework explicitly calls out both: "prevent orphaned agents" (orphan detection) and "unexpected behavior by a known agent may signal compromise" (anomaly detection). | Trust framework lines 70-74 |
| ev_51 | Execution-time verification (H2b) does not catch dormant agents, agents whose owner team dissolved, or agents whose parent was revoked. | Verification gap analysis |
| ev_52 | The tutorial's healthcare case study includes a `daily_compliance_check` that iterates all agents -- bulk periodic verification in practice. | Tutorial lines 1492-1546 |

**Status: Confirmed.**

Both mechanisms are needed:
1. **Bulk verification:** `registry.verify_all()` -- iterates all agents, returns pass/fail/expired report.
2. **Orphan detection:** `registry.find_orphans(known_owners)` -- finds agents whose owner is unknown, parent is revoked, or status is active past `valid_until`.

**Design decision:** Add `registry.verify_all() -> VerificationReport` and `registry.find_orphans(known_owners: list[str]) -> list[str]` as batch operations for the hub's compliance dashboard.

---

## Cross-Branch Interactions

| Branches | Interaction | Resolution |
|----------|-------------|------------|
| 2a <-> 3a | Signature computation determines whether rotation is meaningful. | Resolved: rotation killed because SHA256 has no key. Interaction disappears. |
| 1a <-> 5a | Unique ID design depends on whether namespaces exist. | Resolved: flat namespace Phase 1. No interaction until namespace introduced. |
| 3b <-> 4b | Revoking an agent must cascade to its delegation chain. | Partially resolved: revocation exists (3b confirmed), chain doesn't (4b killed). Document cascade as Phase 2 requirement. |
| 5b <-> 6a | Dynamic provisioning at high frequency creates audit volume. | Resolved: registration ~5-15ms, JSONL append ~1ms. No bottleneck. |
| 2b <-> 5b | Synchronous verification must not degrade under registration load. | Resolved: SHA256 is sub-millisecond. No degradation. |
| 2a <-> 1b | `owner` is signed; `cost_center` is unsigned metadata. Changing `cost_center` silently could be a governance gap. | Convention: unsigned metadata changes still go through `registry.update()` which creates audit entries. Audit trail catches the change even though signature doesn't protect it. |

---

## Governing Thought

**"AgentFacts implements Layer 1 of the trust framework through six mechanisms -- a unique identity card with governance-grade owner binding, SHA256 tamper detection over split signed/unsigned metadata, a two-state credential lifecycle (suspended/revoked) with optional expiry, single-hop delegation via parent reference, flat namespace with convention-based partitioning, and per-agent append-only audit trails with bulk verification -- where the foundational design principle is: every field that determines what an agent is *authorized* to do is in the signature, and everything else is not."**

**Confidence: 0.88**

| Factor | Score | Notes |
|--------|-------|-------|
| Branches 1, 2, 3, 6 evidence strength | 0.90 | Confirmed from three independent sources |
| Branches 4, 5 (deferred features) | 0.85 | Confirmed as deferred; architecture accommodates future addition |
| Signed/unsigned metadata split | 0.75 | Architecturally sound but untested in tutorial examples |

---

## Hypothesis Resolution Summary

| Branch | Hypothesis | Status | Design Outcome |
|--------|-----------|--------|----------------|
| 1a | Composite `namespace:agent_id:version` key | **Confirmed with revision** | Flat `agent_id` Phase 1; namespace Phase 2 |
| 1b | `owner`, `contact`, `cost_center` as top-level fields | **Killed** | Only `owner` is top-level; rest is metadata |
| 2a | Signature covers governance fields, excludes operational | **Confirmed with refinement** | Split `signed_metadata` / `metadata` |
| 2b | Synchronous verify-before-execute | **Confirmed** | Synchronous with optional LRU cache |
| 2c | Supply chain attestation deferred | **Confirmed** | `signed_metadata` as Phase 2 extension point |
| 3a | Signature rotation as registry operation | **Killed** | SHA256 has no key; `re_sign_all()` for migrations |
| 3b | Irreversible revocation | **Confirmed with two-state** | `suspended` (reversible) + `revoked` (irreversible) |
| 3c | `valid_until` expiry timestamp | **Confirmed** | Optional field; `registry.renew()` extends lifetime |
| 4a | Separate `DelegationToken` model | **Killed (Phase 1)** | `parent_agent_id` sufficient; tokens Phase 2 |
| 4b | Traversable delegation chains | **Killed (Phase 1)** | Single-hop reference; chain traversal Phase 2 |
| 5a | Namespace isolation per spoke | **Confirmed (Phase 2)** | Flat namespace Phase 1; partitioned Phase 2 |
| 5b | Rapid automated registration | **Confirmed** | Already fast enough; add `deregister()` |
| 6a | Per-agent JSONL audit trail | **Confirmed** | Matches tutorial design; centralized index Phase 2 |
| 6b | Bulk verification + orphan detection | **Confirmed** | `verify_all()` + `find_orphans()` batch methods |

---

## Gaps

| Gap | Severity | Mitigation |
|-----|----------|------------|
| Signed/unsigned metadata boundary -- which specific keys go in which section | Medium | Define convention: anything referenced by compliance frameworks, model version, or data classification is signed. Everything else unsigned. |
| Phase 2 cascade behavior when delegation chains + revocation interact | Low | Documented as future requirement. No impact on Phase 1. |
| Whether `status` field should be in the signature | Medium | Recommendation: `status` NOT in signature. `verify()` checks signature validity AND status independently. Tamper detection and lifecycle state are orthogonal. |

---

## Resulting AgentFacts Data Model (Phase 1)

Based on the resolved hypotheses, the `AgentFacts` model contains:

| Field | Type | In Signature | Source |
|-------|------|-------------|--------|
| `agent_id` | `str` | Yes | H1a |
| `agent_name` | `str` | Yes | Tutorial |
| `owner` | `str` | Yes | H1b |
| `version` | `str` | Yes | H1a |
| `description` | `str` | Yes | Tutorial |
| `capabilities` | `list[Capability]` | Yes | Tutorial |
| `policies` | `list[Policy]` | Yes | Tutorial |
| `signed_metadata` | `dict[str, Any]` | Yes | H2a |
| `metadata` | `dict[str, Any]` | No | H2a |
| `status` | `str` | No | H3b |
| `valid_until` | `datetime \| None` | No | H3c |
| `parent_agent_id` | `str \| None` | Yes | H4a |
| `signature_hash` | `str` | No (self-referential) | Tutorial |
| `created_at` | `datetime` | Yes | Tutorial |
| `updated_at` | `datetime` | Yes | Tutorial |

### Registry API (Phase 1)

| Method | Branch | Description |
|--------|--------|-------------|
| `register(facts, registered_by)` | 1a | Create agent, compute signature, write to disk, audit entry |
| `get(agent_id)` | 1a | Load from disk |
| `update(agent_id, updates, updated_by)` | 1a | Apply changes, recompute signature, audit entry |
| `verify(agent_id)` | 2b | Recompute signature + check status + check expiry |
| `suspend(agent_id, reason, suspended_by)` | 3b | Set status to suspended, audit entry |
| `restore(agent_id, reason, restored_by)` | 3b | Set status to active (only from suspended), audit entry |
| `revoke(agent_id, reason, revoked_by)` | 3b | Set status to revoked (irreversible), audit entry |
| `renew(agent_id, new_valid_until, renewed_by)` | 3c | Extend expiry, audit entry |
| `deregister(agent_id, reason, deregistered_by)` | 5b | Archive and remove, final audit entry |
| `list_all()` | 5a | All registered agent IDs |
| `find_by_owner(owner)` | 1b | Filter by owner |
| `find_by_capability(name)` | Tutorial | Find agents with a specific capability |
| `audit_trail(agent_id)` | 6a | Ordered change history |
| `export_for_audit(agent_ids, filepath)` | 6a | Compliance-ready JSON export |
| `verify_all()` | 6b | Bulk verification report |
| `find_orphans(known_owners)` | 6b | Find agents with no governance anchor |
| `re_sign_all(reason, re_signed_by)` | 3a | Re-compute all signatures after schema migration |
