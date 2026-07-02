---
name: sdd-brainstorm
type: skill
description: >-
  Run SDD Stage 1 (brainstorm/ideation) for a change to THIS repository: expand
  a problem statement into ~6 candidate directions and validate every
  hypothesis against repo evidence before any spec exists. Use whenever the
  user says "let's brainstorm approaches", "explore options/directions for X",
  "how should we approach X", "generate alternatives", or poses a new
  non-trivial idea with no chosen direction yet. Do NOT use once a direction is
  chosen and needs specifying (sdd-spec), for mid-flight re-prioritization
  (sdd-replan), for documentation write-ups (agentsframework-okf-curator), or
  for generic product ideation unrelated to this codebase.
---

# SDD Stage 1 — Brainstorm

Runbook: `docs/research/agenticengineeringplaybook/sdd_lifecycle_runbook.md` §3
Stage 1. Micro-loop: human poses the *problem* (not the solution) → agent
expands + validates → human accepts a direction or re-poses.

## Agent work

1. **Read the subtree's nested `AGENTS.md`** for every folder the idea touches.
2. **Generate ~6 directions**: 3 high-probability (follow existing repo
   patterns — name the file/pattern each one follows) + 3 exploratory
   (different abstraction / integration / architectural shift). For each:
   tradeoffs, what-breaks-if-chosen, which Architecture Invariant it stresses.
3. **Propose hypotheses** for the leading direction: "works *because* X",
   "safe *because* Y".
4. **Validate every hypothesis against repo evidence** — grep/glob the actual
   files, never parametric memory. A hypothesis that references an API, path,
   or helper the repo doesn't contain is REJECTED (the "context blindness"
   failure mode). Use the read-only `explore` subagent
   (`.claude/agents/explore.md`) as the context firewall for broad sweeps —
   only the distilled answer returns to the main thread.

## Human gate

Direction-level acceptance only — the human picks *what to specify next*, not
the spec itself. Loop back if every direction violates an invariant, the
hypotheses don't validate, or the framing is rejected. Advance → **sdd-spec**
with the chosen direction + validated hypotheses.

## Constraints

- Constitution backdrop: the 8 invariants in `AGENTS.md` + `tests/architecture/`.
  A direction that needs an ⚠️ Ask-first item (new dep, trust-kernel type,
  new node, new service, new abstraction) must say so up front — it will need
  an ADR at spec time.
- Throwaway/exploratory outcome? Light spec only (runbook §6 carve-out).
