# Spec — Gen2 item-level (no-pick) hint opener authoring — pilot shard

**Status:** Draft — 2026-07-19
**Owner:** Rajnish Khatri
**Related:** [gen2-proto-handoff EARS spec (MOM-2, DAT-5)](gen2-proto-handoff/03-ears-spec-gen2-coach.md) · synthetic-data-pipeline skill (Steps 1–7) · [coach-bank-hints.spec.md](coach-bank-hints.spec.md) (choice-keyed precedent) · ADR-0035 (hint choice_letter) · brainstorm: no-pick gap direction D3

---

## 1. Goal

Author real, human-accepted **item-level (no-pick) hint openers** for Gen2 coach items, so a learner who asks for help *before* selecting a choice gets an authored misconception-neutral ladder instead of the current generic `socraticHint` fallback. This spec covers a **pilot shard (~50–100 items)** that validates the opener quality bar and the ISO-2859 acceptance-sampling flow before any commitment to the full 816-item corpus.

## 2. Context

The Gen2 bank is **choice-keyed only**: every hint ladder targets a specific wrong letter (`choice_letter=A/B/C/D`). There are **0 item-level (`choice_letter=null`) ladders** across all 816 reviewed Gen2 items. So the coach's **no-pick moment** (MOM-1/MOM-2 in the proto EARS spec) has no authored content — it falls back to a generic Socratic re-read nudge.

Established at brainstorm (direction D3, "fill properly"):
- **Not CI-blocking.** The FR-E1 coverage ratchet (`frontend/lib/adapters/engine/_hint_bank.test.ts:87-94`) treats an item as covered if it has a complete choice-conditional set **OR** an item-level ladder. Gen2 items already pass via the former. This is UX/content fidelity, not a gate.
- **Precedent exists.** The Gen1 seed bank has **513 item-level rows across 171 items** (`docs/plan/coach-bank-hints.seed.json`) — an authored shape and a healthy few-shot anchor set (anti-model-collapse: never seed from unreviewed output).
- **Binding constraint = review capacity, not generation** (synthetic-data-pipeline Step 1). Generation is a cheap offline job; emit gates on `reviewed=true`, earned only at Step-5 human acceptance sampling.
- **No schema change.** The `Hint` wire type (`frontend/lib/wire/engine_entities.ts:108-122`) already has `choice_letter` nullable + `rung: 1|2|3`. Item-level openers are representable today.

Sized gap (probed 2026-07-19): 816 reviewed items → 2,448 opener rows total (816 × 3 rungs). Pilot = one shard of ~50–100 items → ~150–300 rows.

**Clarified scope (2026-07-19):**
- **Pilot selection = skill-stratified spread** — proportional across all 6 skills, both item types, and the difficulty range (~15/skill) so the opener prompt is exercised on the full variety. (Exact item list → `decisions.md`.)
- **Generation = a separate, dedicated item-level-opener prompt** (misconception-neutral pre-pick openers), distinct from the choice-keyed `act-english-batch-generation-prompt.md`. It is content, not an abstraction → no ADR.
- **Human review deferred.** This spec's implementation builds the *funnel* — generated + cascade-passed pilot rows, the Step-5 sampling harness, and the scorecard template. The actual ISO-2859 human AQL review is a scheduled manual step, out of implementation scope (the binding constraint is review capacity, priced but not spent here).

## 3. Functional requirements (EARS)

Failure paths first (TAP-4).

- **FR-1 (leak — release blocker).** IF a candidate opener rung contains the correct option's distinctive content words, the answer letter/position, or phrasing that uniquely identifies the key, THEN the system SHALL reject that rung at the deterministic filter cascade (Step 3) and never emit it. (Inherits the generation prompt's no-leak contract; item-level openers are held to it identically.)
- **FR-2 (misconception-neutral — the item-level invariant).** IF a candidate opener presumes a *specific* wrong-choice misconception (i.e., reads like a choice-keyed rung), THEN the system SHALL reject it — an item-level opener is answered *before* any pick and MUST NOT presume which distractor the learner would choose.
- **FR-3 (no unreviewed serve).** IF an item-level opener row has `reviewed != true`, THEN the emitter (`scripts/emit_hint_bank.py`) SHALL refuse to emit it (fail-closed, existing behavior — this spec must not weaken it).
- **FR-4 (rung shape).** THE SYSTEM SHALL author exactly 3 rungs per item-level opener, ordered pump → hint → prompt, with `choice_letter=null` and `rung ∈ {1,2,3}`. No rung 4 (assertion is choice-keyed / server-side only; item-level openers have none).
- **FR-5 (opener diversity).** THE SYSTEM SHALL rotate ≥10 rung-1 opener templates such that no single template appears on >20% of pilot rung-1 openers. (Inherits the prompt's diversity contract.)
- **FR-6 (few-shot provenance).** WHEN generating pilot openers THE SYSTEM SHALL anchor few-shot examples on the **reviewed** Gen1 item-level ladders only (513 rows), never on unreviewed Gen2 output (model-collapse rule, Step 7).
- **FR-7 (acceptance sampling).** WHEN the pilot shard is generated + cascade-passed THE SYSTEM SHALL earn `reviewed=true` **only** via ISO-2859-1 / Z1.4 attributes sampling at Step 5 (critical Ac=0 across all five critical classes; one critical rejects the shard). No script, generator, or emit path may assert the flag.
- **FR-8 (provenance stamp).** THE SYSTEM SHALL stamp each generated row's `generated_by` with the cascade's `<model>@<run_id>` format so `tests/architecture/test_test_item_provenance_confinement.py` (ADR-0015) accepts a later `reviewed=true` flip.
- **FR-9 (pilot decision gate).** WHEN the pilot shard completes Step 5 THE SYSTEM SHALL produce a per-shard scorecard (accept/reject, defect classes found, opener-quality notes) that is the input to the human go/no-go decision on the full 816-item corpus — the pilot SHALL NOT auto-trigger full-corpus authoring.

## 4. Data model / contracts

- **No new type, no schema change.** Item-level openers are `Hint` rows with `choice_letter=null`, `rung ∈ {1,2,3}` — already valid per `engine_entities.ts:108-122`.
- **Seed JSON:** pilot openers land in the canonical seed (`docs/plan/coach-bank-hints.seed.json`) as new `rows` entries (the parity pin `_hint_bank.test.ts:98-111` requires bank ↔ seed exact match on emit).
- **Generation prompt variant:** a new item-level-opener prompt (or a documented mode of `act-english-batch-generation-prompt.md`) that produces misconception-*neutral* pre-pick openers — distinct from the existing choice-keyed ladder prompt. This is the one net-new authored artifact.

## 5. Invariants & security boundaries

- **No live LLM in CI.** Generation is an offline governed job (`scripts/generate_hints.py`); the cascade + emit + ratchet tests are deterministic and run in `make check`. (root AGENTS.md 🚫 Never; NFR below.)
- **Architecture invariants untouched.** This is content authoring + an offline script; no layer imports change. `components/` cascade stays framework-agnostic (invariant #3/#4).
- **`reviewed=true` provenance is code-enforced** (ADR-0015 confinement test) — FR-8 keeps it satisfiable.
- **Not an Ask-first/ADR trigger.** No new dependency, no trust-kernel type, no new graph node, no new service, no schema change. A new *generation prompt* is content, not an abstraction. → **No ADR required.** (`docs/adr/decisions.md` entry if a non-obvious choice arises, e.g. the pilot shard selection rule.)

## 6. Edge cases

- **Item whose only defensible opener would leak** (e.g., a rule so specific that a neutral pump still telegraphs the key) → reject at FR-1; if the whole item can't get a non-leaking opener, quarantine it (AP-6: undecidable → exclude, never fabricate a weak opener).
- **Rhetorical-mc items** (223 of 816; no underlined span) → the opener can't say "the underlined word"; the prompt variant must handle both item types.
- **Duplicate opener across items** (opener so generic it repeats) → dedup within the pilot batch (Step 3 Jaccard); over-genericity is the failure mode of item-level openers specifically.
- **Empty pilot after cascade** (all candidates rejected) → surface as a scorecard failure, not a silent zero; re-plan the prompt (three-strikes → stop).

## 7. Non-functional requirements

- **Determinism:** cascade + emit + ratchet tests are L1 deterministic (in `make check`). Generation is offline, non-deterministic, off the CI hot path.
- **Cost axis:** the load-bearing cost is **review calendar time** (Step-5 human sampling), not engineering time or model spend. The pilot exists to price this before the full corpus.
- **Reversibility:** pilot openers are additive seed rows; un-emitting = drop the rows. No migration.

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | leak-lint over pilot openers (port of Gen2 shard validator gate 4) rejects any key-leaking rung | L1 | yes |
| FR-2 | misconception-neutrality check: no pilot opener references a specific distractor's error type | L1 | yes |
| FR-3 | `scripts/emit_hint_bank.py` dies on an unreviewed item-level row (existing fail-closed, assert not weakened) | L1 | yes |
| FR-4 | each pilot item has exactly 3 item-level rungs, `choice_letter=null`, rungs {1,2,3}, no rung 4 | L1 | yes |
| FR-5 | opener-diversity: no rung-1 template >20% of pilot | L1 | yes |
| FR-6 | few-shot anchor set = reviewed Gen1 rows only (provenance of anchors asserted in the gen job config) | L2 | on-demand (offline) |
| FR-7 | Step-5 acceptance-sampling record exists with n, Ac=0, defect classes; `reviewed=true` flip traces to it | L2 | manual/cadence |
| FR-8 | `test_test_item_provenance_confinement.py` accepts the flipped rows (generated_by format) | L1 | yes |
| FR-9 | pilot scorecard artifact exists and full-corpus authoring is not auto-triggered | L1 (artifact presence) | yes |

## 9. Definition of Done

- [ ] Pilot shard (~50–100 items) of item-level openers generated via offline job, anchored on reviewed Gen1 openers (FR-6).
- [ ] Full deterministic cascade (Step 3) + leak/neutrality lints (FR-1/FR-2) run on 100% of pilot rows; failures routed to repair, not emitted.
- [ ] Step-5 ISO-2859 acceptance sampling run; `reviewed=true` earned only there (FR-7); scorecard produced (FR-9).
- [ ] `make check` green (cascade/emit/ratchet/provenance tests).
- [ ] Invariants §5 unbroken (`tests/architecture/` green).
- [ ] `decisions.md` entry for the pilot shard selection rule (which ~50–100 items, and why).
- [ ] Go/no-go on full 816-corpus is an explicit human decision fed by the pilot scorecard — NOT started by this spec.
- [ ] Actual command output pasted (not summarized) for the verification claims.
