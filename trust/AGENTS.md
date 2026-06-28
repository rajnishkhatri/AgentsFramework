# trust/ — Trust Kernel

> Nested guide. Loads when Claude reads a file under `trust/`. The root
> `AGENTS.md` Architecture Invariants table is authoritative for inter-layer
> rules; this file adds the local detail for the kernel. `tests/trust/` is the
> hard enforcement layer — this file is guidance.

## What belongs here

A type belongs in `trust/` only if **ALL** criteria hold:

1. **Pure** — no I/O, no storage, no network, no logging.
2. **Shared** — consumed by 2+ layers above.
3. **Stable** — changes less frequently than its consumers.
4. **Dependency-free** — zero imports from `services/`, `components/`,
   `orchestration/`, or `meta/`. Stdlib + Pydantic only.

If any criterion fails, the type lives in the lowest layer that consumes it —
**not** here. Putting a service-specific type in `trust/` is anti-pattern AP-1.

Key types: `AgentFacts`, `Capability`, `Policy`, `AuditEntry`, `TrustTraceRecord`,
`PolicyDecision`, `CredentialRecord`.

## Signed vs unsigned fields

Signed fields determine authorization — **changing one triggers re-signing** and
is an `⚠️ Ask first` event. Unsigned fields are operational metadata. Field
classification: @../docs/Architectures/FOUR_LAYER_ARCHITECTURE.md §Signed vs Unsigned.

## G4 — Complex-algorithm comprehension gate (scoped to `trust/`)

The crypto / signing path is where a passing-but-not-understood diff is most
dangerous. Before changing signing, verification, or any kernel algorithm:
**write down — in the PR or the commit body — what the algorithm does and why
the change is correct, before reading or pasting the implementation back.** A
green test on a signing change you can't explain is not done. (This is a
convention, not a tool-enforced gate — hooks can't capture a typed answer.)

## L1 testing rules (trust/)

- **Zero flake tolerance** — any non-deterministic test in `trust/` is a bug in
  the test, not the code.
- **Pure TDD**, property-based, exact assertions. Every commit, <10s.
- **TAP-1 (tautological tests):** never reimplement the production algorithm in
  the test (e.g. computing SHA-256 in the test to compare against
  `compute_signature()`). Test behavioral properties ("sign then verify is
  True") or known test vectors — never the algorithm itself.
- **TAP-4 (gap blindness):** write the rejection test **before** the acceptance
  test. A gate that accepts everything is more dangerous than one that rejects
  everything.
- **Test import rule:** `tests/trust/` may import **only** from `trust/`.
