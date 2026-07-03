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
2. **Validate the premise before expanding it.** The problem statement is
   itself a hypothesis — check it against the working tree first. If it's
   stale ("X is orphaned" when X shipped last month), say so with evidence,
   reframe to the *actual* open space, and offer to re-validate on another
   branch if the human's mental model may come from elsewhere. If the
   correction reveals the system is **live with a known open defect**, name
   closing that defect as a blocking direction (D0) ahead of the six — a
   present risk outranks every future capability.
3. **Generate ~6 directions**: 3 high-probability (follow existing repo
   patterns — name the file/pattern each one follows) + 3 exploratory
   (different abstraction / integration / architectural shift). At least one
   exploratory direction must **challenge the framing itself** — invert the
   premise or shrink the problem. Six variations *inside* the stated framing
   is the most common reviewer rejection: the human usually needs the option
   that changes the problem's size, not just its mechanism. Two specific
   inversion lenses reviewers keep asking for:
   - **Demand-side, not just supply-side.** When the problem is governing an
     expensive operation (LLM calls, DB writes, egress), "govern it
     differently" is still supply-side. The demand-side direction makes the
     operation *not happen*: deterministic cascades / local reasoning /
     known-answer fast-paths first, the expensive call as fallback. This repo
     has two proven precedents to anchor on: the router's pure-deterministic
     decision tree (`components/router.py`) and the guardrail's
     regex→classifier→LLM cascade with its `decision_stage` audit field
     (`services/guardrails.py`).
   - **Class over instance.** If premise validation shows the same defect
     class recurring (a third composition-root drift, say), offer the
     class-level fix — shared seam + an architecture test that fails the next
     occurrence — as a direction, not just the instance patch.
   For each direction: tradeoffs, what-breaks-if-chosen, which Architecture
   Invariant it stresses. If a direction crosses a deliberately-maintained
   discipline (e.g., recalled-content-vs-metadata), enumerate *every* surface
   that discipline currently protects — "needs a fresh ruling" understates a
   cross-cutting reversal.
4. **Propose hypotheses** for the leading direction: "works *because* X",
   "safe *because* Y".
5. **Validate every hypothesis against repo evidence** — grep/glob the actual
   files, never parametric memory. A hypothesis that references an API, path,
   or helper the repo doesn't contain is REJECTED (the "context blindness"
   failure mode). Evidence rules reviewers consistently enforce:
   - **Quantified claims state their sweep scope — and the scope must match
     the claim.** "~9 call sites" that silently skipped `tests/`, `meta/`,
     and `scripts/` is a wrong count, and a wrong count is a rejected
     hypothesis. A "total waste" claim includes tests (the volume is often
     *in* the test suite); a "prod hot path" claim may exclude them — say
     which and why.
   - **Only verified `file:line` citations.** A "~line 258" guess is exactly
     the claim that turns out false in review — open the file or drop the
     line number.
   - **Name the live prod surface.** This repo runs dual route surfaces
     (`middleware/app_prod.py` hand-builds the prod routes;
     `agent_ui_adapter/server.py` is the dev/standalone surface — see the
     drift warning inside `app_prod.py`). A "ship it at seam X" claim that
     cites the dev surface does not relieve prod.
   - **Feasibility adjectives are hypotheses too.** "Trivial", "zero code",
     "an afternoon", "the arms are a flag flip", and *especially* "these are
     parallel" get the same evidence check: verify what actually fires
     before/after (calls upstream of the proposed gate), whether an
     experiment's arms are actually matched, and whether "zero code" hides a
     calendar dependency (data that must accumulate first).
   Use the read-only `explore` subagent (`.claude/agents/explore.md`) as the
   context firewall for broad sweeps — only the distilled answer returns to
   the main thread.
6. **Map the dependency structure before naming a lead.** State which
   directions are genuinely sequenced (B needs A's output) versus independent
   and parallel — "leading: A" quietly collapses parallel tracks into a
   critical path and buries cheap wins. Call out any zero-risk / no-ADR
   hygiene direction as "do regardless of the pick", and distinguish
   *capability* deliverables from *operational* ones: they usually share a
   substrate but are different goals, and which one the human actually wants
   is often the real decision. Three refinements:
   - **Engineering time and calendar time are different axes.** "Mostly eval
     labor" hides a wait for production data to accumulate; a fork whose
     load-bearing cost is calendar time should say so.
   - **When feasibility hinges on a quantity the repo can't answer** (traffic
     volume, corpus size, cache-hit rates), name the cheapest *read-only
     probe* as the track's step 1 instead of assuming the answer.
   - **Split conflated axes in the gate.** If the decision mixes independent
     choices (what unit is metered vs. where it's enforced; deny vs.
     degrade), pose them as separate axes, not one flat option list.

## Human gate

Direction-level acceptance only — the human picks *what to specify next*, not
the spec itself. When directions are orthogonal, pose the gate as independent
tracks (do-regardless / pick-the-priority / deferred-behind-X) rather than
forcing a single winner. Loop back if every direction violates an invariant,
the hypotheses don't validate, or the framing is rejected. Advance →
**sdd-spec** with the chosen direction + validated hypotheses.

## Constraints

- Constitution backdrop: the 8 invariants in `AGENTS.md` + `tests/architecture/`.
  A direction that needs an ⚠️ Ask-first item (new dep, trust-kernel type,
  new node, new service, new abstraction) must say so up front — it will need
  an ADR at spec time.
- Throwaway/exploratory outcome? Light spec only (runbook §6 carve-out).
