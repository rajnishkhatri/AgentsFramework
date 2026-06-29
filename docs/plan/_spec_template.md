# Spec — <feature / change name>

> **Copy this file** to `docs/plan/<short-name>.spec.md` for any non-trivial, durable
> change. The spec captures the *what* (testable acceptance criteria); the ADR captures
> the *why* (when an `⚠️ Ask first` trigger fires — see root `AGENTS.md`). Small changes
> need neither; the long tail of small decisions goes in `docs/adr/decisions.md`.
>
> Acceptance criteria use **EARS** (Easy Approach to Requirements Syntax) so each one is
> directly testable. The five EARS forms:
> - **Ubiquitous:** `THE SYSTEM SHALL <behavior>.`
> - **Event-driven:** `WHEN <trigger> THE SYSTEM SHALL <behavior>.`
> - **State-driven:** `WHILE <state> THE SYSTEM SHALL <behavior>.`
> - **Unwanted:** `IF <condition> THEN THE SYSTEM SHALL <behavior>.`
> - **Optional:** `WHERE <feature is present> THE SYSTEM SHALL <behavior>.`

**Status:** Draft | Approved | Implemented — YYYY-MM-DD
**Owner:** <name>
**Related:** <links to the plan/ADR/design docs this spec belongs to>

---

## 1. Goal

One or two sentences: the outcome this change delivers and who it is for. State the
problem, not the implementation.

## 2. Context

The forces in play — why now, what constraints, what this builds on. Link the playbook
item, prior plan, or failure that motivates it.

## 3. Functional requirements (EARS)

Numbered, testable, one behavior each. Each FR maps to at least one test in §8.

- **FR-1.** WHEN <trigger> THE SYSTEM SHALL <behavior>.
- **FR-2.** IF <unwanted condition> THEN THE SYSTEM SHALL <behavior> (failure path —
  write these first; cf. TAP-4 gap-blindness).
- **FR-3.** THE SYSTEM SHALL <invariant behavior>.

## 4. Data model / contracts

New or changed types, schemas, wire shapes, or file formats. For trust-kernel types,
note whether the change triggers re-signing (root `AGENTS.md` ⚠️ Ask first → ADR).

## 5. Invariants & security boundaries

Which Architecture Invariants (root `AGENTS.md` #1–#8) this touches, and how it stays
within them. Any security boundary (secrets, sandboxing, live-LLM-in-CI, trust purity).
A spec that touches an invariant must say *which* and *why it holds*.

## 6. Edge cases

The inputs/states that are easy to miss: empty, malformed, concurrent, undecidable
(return `None`, not a fabricated `0.0` — cf. AP-6). One bullet each.

## 7. Non-functional requirements

Latency / cost / determinism (L1 exact vs L2 sampled vs L3/L4 aggregate) / reversibility.
Note if any path runs live LLM calls (must stay off the CI hot path).

## 8. Test plan

Map each FR to its test and pyramid layer (L1 deterministic / L2 reproducible /
L3 probabilistic / L4 behavioral). Failure-path tests before happy-path. State which
run via `make check` (deterministic) vs cadence/on-demand (live).

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `tests/...::test_...` | L1 | yes |
| FR-2 | `tests/...::test_..._rejects_...` | L1 | yes |

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test that was *seen to fail first*.
- [ ] `make check` green (lint + format-check + pyright + test).
- [ ] Invariants in §5 unbroken (`tests/architecture/` green).
- [ ] ADR appended if an ⚠️ Ask first trigger fired; `decisions.md` entry if a small
      non-obvious choice was made.
- [ ] Actual command output pasted (not summarized) for the verification claims.
