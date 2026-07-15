---
type: decision-record
title: 'ADR-0032: Workspace-binding contract for portable, multi-agent SDD skills'
status: proposed
created: 2026-07-15
updated: 2026-07-15
owner: Rajnish Khatri
related: sdd-skills-portability-export.spec.md, sdd-skills-portability-export.brainstorm.md
tags: [decision-record]
---

# ADR-0032: Workspace-binding contract for portable, multi-agent SDD skills

**Status:** Proposed — 2026-07-15.
**Related:** [sdd-skills-portability-export.spec.md](../plan/sdd-skills-portability-export.spec.md), [sdd-skills-portability-export.brainstorm.md](../plan/sdd-skills-portability-export.brainstorm.md)
**Audience:** anyone changing the SDD skills, `scripts/sync_skills.py`, or exporting skills to another repo/agent.

---

## Context

The six SDD lifecycle skills are canonical in `docs/skills/<name>/SKILL.md` and
byte-mirrored to `.claude/skills/` + `.cursor/skills/`. Stage-1 grounding proved
they are welded to THIS repo: **9× `AGENTS.md`, 6× the runbook, 6× `make check`,
4× `pytest tests/architecture/ -q`, 3× `docs/adr/0000-template.md`**, plus
`eval_capture`, `scripts/hooks/*.py`, `ADR-OK:`/`G8-OK:` waivers, gates G1–G9,
and repo-specific *worked examples* (`components/router.py`,
`services/guardrails.py`, `middleware/app_prod.py`). We want these skills usable
in **any workspace** by **any coding agent** (add Copilot; keep Cursor + Claude),
then exported as `.skill` archives. That requires separating the portable
methodology from every repo/agent-specific value **without maintaining two copies
of each skill** (the failure the sync mirror already prevents for the copy step).

Two kinds of coupling exist, and they need different treatment:
1. **Binding tokens** — concrete strings with a per-workspace analog
   (`AGENTS.md` = "the constitution", `make check` = "the gate command").
   Mechanically substitutable.
2. **Repo-specific worked examples** — illustrations woven into the guidance
   (the router/guardrail demand-side cascade; the prod-vs-dev surface note).
   Not substitutable by a token; they must be genericized or relocated.

## Decision

Introduce a **workspace-binding contract**: a fixed placeholder vocabulary
(`{{constitution}}`, `{{check_gate}}`, `{{test_gate}}`, `{{adr_home}}`, …) that
the six portable SKILL.md bodies use in place of every this-repo binding token,
resolved **at runtime** from a per-workspace `.sdd/binding.toml` (THIS repo:
`docs/skills/_sdd/binding.reference.toml`). In a foreign workspace with no
binding, the skill's first-run preamble **inspects the ecosystem, proposes a
filled binding, and requires human confirmation** before persisting it
(propose→confirm→persist; AP-6 — never run a guessed gate command silently).
Repo-specific worked examples are **genericized in the portable body** and their
concrete instances moved into an optional `examples` section of the binding.
`scripts/sync_skills.py`'s hard-coded `TARGETS` 2-tuple becomes an **adapter
registry** so each coding agent (Claude, Cursor, +Copilot) is one entry; a new
`scripts/pack_skills.py` emits the six `.skill` archives carrying the binding
template.

## Options considered & rejected

| Option | Why it lost |
|---|---|
| **D6 — extract one new portable skill, leave the six untouched** | Two sources of truth for the same methodology; the existing six stay Claude/Cursor-only. Rejected at the Stage-1 gate in favor of one source. |
| **Static sync-time substitution** (mirrors get real values baked in) | Simpler, but the mirrors would be repo-specific — defeats "adapts to a new workspace." The human chose runtime resolution + ecosystem auto-adapt (spec Q2). |
| **Auto-detect and run with no confirm** | Fastest drop-in, but runs a guessed `check`/`test` command with no human gate — violates the repo's ask-on-undecidable norm (AP-6). Rejected (spec Q2c). |
| **Keep repo examples in the portable body behind an allowlisted region** | The FR-1 guard would need a fragile allowlist; leak-creep risk. Rejected (spec Q1) — examples are genericized + moved to the binding instead. |
| **Fully manual template fill, no auto-detect** | Drops the "tune/adapt to new workspace" capability the human explicitly asked for. Rejected (spec Q2c). |

## Rationale

The binding contract wins because it makes the coupling **explicit and finite**:
a 13-key vocabulary the FR-1 guard can enforce mechanically, versus prose the
guard cannot reason about. Runtime resolution + auto-adapt delivers the actual
goal (drop-in-anywhere, ecosystem-agnostic) that static substitution cannot. The
adapter registry generalizes an already-proven mechanism (the byte-mirror sync +
its `--check` parity guard), so multi-agent support is one entry, not a fork.
Precedent: the repo already splits portable-vs-binding skills
(`llm-eval-grounded-theory` ↔ `agentsframework-eval-probe`,
`docs/skills/README.md`) and already ships `.skill` zips — we are systematizing
two existing patterns, not inventing new ones (G1: what it buys = one reusable
source across repos/agents; simpler thing rejected = D6 duplicate skill).

## Consequences

- **New abstraction (the binding contract).** The cost is a placeholder
  vocabulary + a runtime-resolution convention the skills must document. Mitigated
  by the FR-3 round-trip test (reference binding reproduces today's strings) and
  the FR-1 leak guard.
- **Behavior-adjacent change to six LIVE skills.** Mirrors now carry placeholders,
  so the agent resolves the binding on every invocation. Mitigated by FR-8a
  (auto-resolve from the committed reference in THIS repo → live UX unchanged) and
  Stage-7 review.
- **Worked examples genericized.** Some concreteness moves from the body to the
  binding's `examples`; a reader in THIS repo still sees the router/guardrail
  example (via the reference binding), a foreign reader sees their own or none.
- **Follow-on:** Windsurf/Codex adapters (one registry entry each);
  adopting the 4 legacy hand-zipped archives into the emitter (deferred, spec §6).
- **No `trust/` re-sign, no new dependency** (`zipfile`/`tomllib` stdlib), **no
  Architecture Invariant touched**, **no live LLM in CI**.

## Supersedes / related

Realizes [sdd-skills-portability-export.spec.md](../plan/sdd-skills-portability-export.spec.md).
Extends the sync mechanism in `scripts/sync_skills.py` (no prior ADR governs it;
it was introduced under `docs/adr/decisions.md` 2026-07-02). Related pattern:
`docs/skills/README.md` portable↔binding split.
