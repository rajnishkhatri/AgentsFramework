---
name: sdd-brainstorm
type: skill
description: >-
  Run SDD Stage 1 (brainstorm/ideation) for a change to your workspace: expand
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

> **Workspace binding.** Resolve each `{{placeholder}}` from the workspace binding:
> `.sdd/binding.toml` at the repo root, else the committed reference
> (`docs/skills/_sdd/binding.reference.toml` in this repo), else first-run
> auto-adapt (inspect ecosystem → propose → human-confirm → persist). See
> `docs/skills/_sdd/binding.schema.md`.

Runbook: `{{methodology_source}}` §3
Stage 1. Micro-loop: human poses the *problem* (not the solution) → agent
expands + validates → human accepts a direction or re-poses.

## Agent work

1. **Read the subtree's nested `{{constitution}}`** for every folder the idea touches.
2. **Audit the premises before ideation.** The problem statement is itself a
   hypothesis. Check every load-bearing premise against the working tree
   (grep/glob; the workspace's broad read-only exploration tool ({{breadth_read_tool}}) for broad sweeps) and publish a
   premise-status table: `verified` / `refuted` / `unverifiable`.
   - `refuted` → re-pose the corrected framing with evidence *in the same
     document* and generate directions over the corrected space; the human
     gate is where they confirm it. Silently continuing on the stale framing
     is the failure this step exists to catch. Offer to re-validate on another
     branch if their mental model may come from elsewhere.
   - `unverifiable` (needs live data / traffic / external state) → say so and
     tag dependent directions `needs-probe` instead of assuming.
   - Audit reveals the system is **live with a known open defect** → name
     closing it as a blocking direction (D0) ahead of the six; a present risk
     outranks every future capability.
3. **Generate ~6 directions**: 3 high-probability (follow existing repo
   patterns — name the file/pattern each one follows) + 3 exploratory
   (different abstraction / integration / architectural shift). Six variations
   *inside* the stated framing is the most common reviewer rejection — lenses
   reviewers keep asking for:
   - **Demand-side, not just supply-side.** When the problem is governing an
     expensive operation (LLM calls, DB writes, egress), include the direction
     that makes the operation *not happen*: deterministic cascades / local
     reasoning / known-answer fast-paths first, the expensive call as
     fallback. Repo precedent: your workspace's deterministic-cascade precedent
     ({{examples.deterministic_cascade}}).
   - **Class over instance.** A recurring defect class (a third
     composition-root drift, say) gets the class-level fix — shared seam + an
     architecture test that fails the next occurrence — not just the patch.
   - **Under-used signal.** When an existing telemetry/judge/feedback surface
     is in scope, seed one direction with "what high-quality signal is
     currently under-used?".
   For each direction: tradeoffs, what-breaks-if-chosen, which Architecture
   Invariant it stresses. Where they apply:
   - A/B or measurement gate → enumerate confounds and the clean-toggle
     requirement; no clean toggle → reject as-stated, propose a matched-seed
     alternative.
   - Consumes a telemetry/judge/feedback signal → characterize it on
     coverage × quality and name the bias class.
   - Depends on a corpus/dataset/runtime quantity → run the cheapest
     read-only probe first and tag `gated-on-data: <measured-count>`, or
     `needs-probe` if it can't be measured now.
   - Crosses a deliberately-maintained discipline (e.g. recalled-content
     vs metadata) → enumerate *every* surface that discipline protects.
4. **Propose hypotheses** for the leading direction: "works *because* X",
   "safe *because* Y".
5. **Validate every hypothesis against repo evidence** — grep/glob the actual
   files, never parametric memory. A hypothesis that references an API, path,
   or helper the repo doesn't contain is REJECTED (the "context blindness"
   failure mode). Evidence rules reviewers consistently enforce:
   - **Sweep scope matches the claim.** A count that silently skipped
     `tests/`, `meta/`, `scripts/` is a wrong count = rejected hypothesis;
     "total waste" includes tests, "prod hot path" may exclude them — say
     which and why.
   - **Only verified `file:line` citations** — open the file or drop the
     line number.
   - **Name the live prod surface.** Name the live prod surface, not a
     dev/standalone one ({{examples.live_prod_surface}}). A "ship at
     seam X" claim citing the dev surface does not relieve prod.
   - **Feasibility adjectives are hypotheses.** "Trivial", "zero code", "the
     arms are a flag flip", and especially "these are parallel" get the same
     check: what fires upstream of the proposed gate, whether experiment arms
     are actually matched, whether "zero code" hides calendar time (data that
     must accumulate first).
6. **Map the dependency structure before naming a lead**: sequenced (B needs
   A's output) vs independent-parallel; zero-risk / no-ADR hygiene is "do
   regardless of the pick"; capability and operational deliverables are
   different goals on a shared substrate — which one the human wants is often
   the real decision. Engineering time and calendar time are different cost
   axes — say when the load-bearing cost is the wait.

## Human gate

Direction-level acceptance only — the human picks *what to specify next*, not
the spec itself. Pose orthogonal directions as independent tracks
(do-regardless / pick-the-priority / deferred-behind-X), and split conflated
axes (what unit is metered vs where it's enforced vs deny-or-degrade) into
separate questions. Label options with explicit ids — a bare "yes" is not
valid multi-option consent. Loop back if every direction violates an
invariant, the hypotheses don't validate, a `refuted` load-bearing premise has
not been re-posed, or the framing is rejected. Advance → **sdd-spec** with the
chosen direction + validated hypotheses.

## Constraints

- Constitution backdrop: the 8 invariants in `{{constitution}}` + the {{test_gate}} suite.
  A direction that needs an ⚠️ Ask-first item (new dep, trust-kernel type,
  new node, new service, new abstraction) must say so up front — it will need
  an ADR at spec time.
- Throwaway/exploratory outcome? Light spec only (runbook §6 carve-out).
