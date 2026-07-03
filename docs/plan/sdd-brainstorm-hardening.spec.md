# Spec — SDD Stage 1 Brainstorm Hardening

> This spec hardens the Stage-1 brainstorm workflow so premise validation happens
> before direction generation. It follows `docs/plan/_spec_template.md`.

**Status:** Draft — 2026-07-02
**Owner:** rajnishkhatri
**Related:** `docs/skills/sdd-spec/SKILL.md`, `docs/skills/sdd-brainstorm/SKILL.md`, `docs/research/agenticengineeringplaybook/sdd_lifecycle_runbook.md`, `docs/adr/decisions.md`

---

## 1. Goal

Ensure Stage-1 brainstorm outputs are grounded in verified repo reality before a
direction is selected, so the workflow does not proceed from refuted premises.

## 2. Context

This session surfaced repeated Stage-1 framing failures across multiple
brainstorms:

- User-supplied load-bearing premises were sometimes incorrect but were only
  corrected later in analysis, not before direction generation.
- Data-dependent directions were treated as feasible before prerequisite corpus
  counts were measured.
- Measurement proposals did not consistently call out confounds and clean-toggle
  requirements.
- Signal-driven directions did not consistently characterize coverage vs quality.
- Multi-option confirmations accepted bare "yes", creating ambiguity.

Reconciliation note (2026-07-02): these requirements were merged with the
eval-loop v3 skill revision (commit 65d84f9) into one unified SKILL.md —
compression, not concatenation; overlapping rules were deduplicated.

Clarify decisions (resolved during Stage 2 clarify pass on 2026-07-02):

- Q1 (blocking vs advisory premise audit): **BLOCKING**
- Q2 (when under-used-signal direction is mandatory): **CONDITIONAL**
  (required when an existing telemetry/feedback signal surface is in scope)
- Q3 (rough probe count vs thresholded gate): **ROUGH + THRESHOLD**
  (report measured count and state explicit feasibility threshold in-context)

## 3. Functional requirements (EARS)

- **FR-1.** WHEN a `brainstorm.md` (or equivalent problem framing) is supplied as
  initiation, THE AGENT SHALL audit each load-bearing premise against repo
  evidence via grep/glob/read and publish a premise-status table
  (`verified` / `refuted` / `unverifiable`) before generating any direction.
- **FR-2.** IF a load-bearing premise is `refuted` by repo evidence THEN THE
  AGENT SHALL re-pose the problem statement with corrected facts before any
  direction is selected. *Resolved semantics (2026-07-02 reconciliation):
  correct-and-continue — the corrected framing is re-posed in the same
  document and directions are generated over the corrected space; the human
  gate is the confirmation point. Present-and-wait (stopping for a human
  round-trip before generating any directions) was rejected — see
  `docs/adr/decisions.md` entry of 2026-07-02.*
- **FR-3.** WHILE a direction depends on a corpus, dataset, or runtime quantity,
  THE AGENT SHALL probe that quantity before declaring the direction feasible,
  and tag the direction `gated-on-data: <measured-count>`.
- **FR-4.** WHEN a direction proposes an A/B or measurement gate THE AGENT SHALL
  enumerate confounding variables and state the clean-toggle requirement; IF no
  clean toggle exists THEN THE AGENT SHALL reject the direction as-stated and
  propose a matched-seed alternative.
- **FR-5.** WHERE a direction consumes an existing telemetry / judge / feedback
  signal THE AGENT SHALL characterize the signal on coverage x quality and name
  the bias class.
- **FR-6.** WHERE the problem touches an existing telemetry/feedback signal
  surface, THE AGENT SHALL include one direction seeded by "what existing
  high-quality signal is under-used".
- **FR-7.** WHEN offering next-step options to the human THE AGENT SHALL label
  each option with a distinct id and require a directional answer (`option N`,
  `all`, `none`), not a bare "yes" as multi-option consent.
- **FR-8.** IF the agent cannot verify a premise due to missing repo access or
  live-data dependency THEN THE AGENT SHALL mark the premise `unverifiable` and
  flag the dependent direction `needs-probe` instead of assuming correctness.

## 4. Data model / contracts

No runtime data model or API contract changes. This change defines process
artifacts and vocabulary in docs:

- premise-status labels: `verified` / `refuted` / `unverifiable`
- direction tags: `gated-on-data: <measured-count>` and `needs-probe`
- option acceptance protocol: explicit option ids for multi-option prompts

## 5. Invariants & security boundaries

No Architecture Invariant is modified. This is docs-only (`docs/skills/`,
`docs/research/`, `docs/adr/`) with no code-path, trust-kernel, orchestration,
service, or dependency change. No security boundary change is introduced.

## 6. Edge cases

- Premise is partly true and partly false: split and classify each sub-claim.
- Repo evidence is unavailable/inconclusive: mark `unverifiable`, do not infer.
- Data probe succeeds but count is below explicit threshold: keep direction as
  deferred/not-feasible-yet and state the threshold shortfall.
- Direction appears high quality but has poor coverage: record coverage-risk
  explicitly before recommendation.
- Human replies "yes" to a multi-option prompt: require explicit option id
  selection instead of interpreting intent.

## 7. Non-functional requirements

- Determinism: Stage-1 outputs should become more repeatable by forcing explicit
  premise-audit and tagging.
- Latency/cost: slight upfront read/search overhead is acceptable to reduce
  downstream rework.
- Reversibility: docs-only changes are fully reversible.
- CI safety: no live-LLM requirement in CI added.

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | Review `docs/skills/sdd-brainstorm/SKILL.md` includes premise-audit step before direction generation | L1 (prose/static) | yes |
| FR-2 | Review skill + runbook include loop-back behavior for `refuted` premises | L1 (prose/static) | yes |
| FR-3 | Review skill + runbook include `gated-on-data` and probe-before-feasible language | L1 (prose/static) | yes |
| FR-4 | Review skill includes explicit measurement-confound + clean-toggle requirement | L1 (prose/static) | yes |
| FR-5 | Review skill includes coverage x quality characterization for signal directions | L1 (prose/static) | yes |
| FR-6 | Review skill requires under-used-signal seeded direction per clarify scope | L1 (prose/static) | yes |
| FR-7 | Review skill human-gate text requires id-labeled options, no bare "yes" | L1 (prose/static) | yes |
| FR-8 | Review skill/runbook include `unverifiable` + `needs-probe` behavior | L1 (prose/static) | yes |

Verification commands at implementation gate:

- `pytest tests/architecture/ -q`
- `make check`

## 9. Definition of Done

- [ ] All FRs reflected in updated Stage-1 docs with no zero-coverage criteria.
- [x] Clarify Q1/Q2/Q3 answered and reflected in this spec.
- [ ] `docs/skills/sdd-brainstorm/SKILL.md` and runbook Stage 1 updated.
- [ ] `docs/adr/decisions.md` has an append-only entry for the ordering decision.
- [ ] `pytest tests/architecture/ -q` and `make check` are green.
- [ ] Verification output captured from real command runs.
