# Spec — ACT-English bank Phase B: authored tranche to ~180 items

> Acceptance criteria use **EARS**; each collapses to one testable claim.
> Failure paths first. Spec = the *what*; the *why* trail lives in
> `docs/adr/decisions.md` (2026-07-07 entries) + ADR-0013/0014/0015/0021.

**Status:** Draft — 2026-07-07
**Owner:** Rajnish Khatri
**Related:** `docs/plan/act-english-full-bank.brainstorm.md` (gate outcome
D3→D1→D2+D4; Phase B realizes the D1-adjacent authored path),
`docs/plan/coach-bank-hints.impl.md` (hint pipeline precedent, PR #134),
ADR-0015 (test-item cascade), ADR-0021 (bank-mode serving), ADR-0014 seam
(single-source corpus → emitted planes).

---

## 1. Goal

Grow the served ACT-English practice bank from 8 to ~180 cascade-verified
items **with full 3-rung hint ladders**, giving every one of the 32 syllabus
topics at least one practice item — through the authored-seed → cascade →
frozen-corpus → deterministic-emit pipeline proven in Phase A (26/30, 87%).

## 2. Context

- **Phase A (2026-07-07)** proved session-authored rich items survive the real
  cascade at 87%; the 4 losses are genuine solver disagreements. The
  rail-judge capture defect that initially ate 7 items is fixed (template
  sandwich + defensive parse) but **uncommitted — committing it is a
  prerequisite** (P0 below).
- **The coverage ratchet makes hints mandatory:** `_hint_bank.test.ts`
  (ladderGaps, FR-E1) hard-fails CI for any reviewed bank item lacking a full
  ladder or explicit waiver → ~176 new items ⇒ ~528 rungs in scope.
- **The 8 live items were hand-placed** into `_test_item_bank.ts`; no test-item
  emitter exists (hints have `emit_hint_bank.py`). At ~180 rows hand-placement
  is untenable → build the sibling emitter (clarify decision, 2026-07-07).
- **Coverage today:** 25 of 32 syllabus topics have zero items.
- Clarify decisions (2026-07-07, human gate): full ladders in-phase; build
  `emit_test_item_bank.py`; topic-weighted allocation; **capable-tier solver
  for difficulty ≥4** (overrides author-around).
- **Non-goals:** D3 syllabus-as-data substrate (standard_id wire tags,
  coverage ratchet CI), D4 product taxonomy (wire kernel change → its own
  spec+ADR), D2 Test-01 exclusivity split, P3 generator-prompt repair
  (generate-mode stays unused by Phase B), solver-seam quarantine-stage
  relabel (separate session, worktree sweet-wilson — FR-1 stays compatible
  either way).

## 3. Functional requirements (EARS)

Failure paths first.

- **FR-1 (fail-closed promotion).** IF an authored row fails any cascade stage
  (schema / answer-key / duplicate) THEN the system SHALL quarantine it with
  the owning stage recorded via `eval_capture` (`target="test_item_generator"`)
  and exclude it from the promoted corpus — never a fabricated pass (AP-6).
- **FR-2 (undecidable solver reply).** IF the independent solver's reply names
  zero or more than one valid letter THEN the row SHALL quarantine as
  undecidable — never guessed at.
- **FR-3 (persistent quarantine tolerated).** THE corpus SHALL tolerate rows
  that persistently fail re-verification: they remain `reviewed=false`, never
  reach a serving plane, and the promotion run report SHALL list them with
  stage + violations. (The 12-row base seed carries 4 such rows today.)
- **FR-4 (hint ratchet).** IF any promoted bank item lacks a full 3-rung
  reviewed ladder and no explicit `{question_id, rung, reason}` waiver THEN
  frontend CI SHALL fail (existing ladderGaps ratchet). Phase B SHALL land
  with **zero new waivers** as the target; any waiver used carries a reason.
- **FR-5 (hint leakage).** IF a generated rung leaks the answer per the
  deterministic leak predicate THEN the rung SHALL quarantine (existing hint
  cascade), and `make check` SHALL re-verify the committed ladders
  leakage-clean (existing `test_hint_bank_leakage.py`).
- **FR-6 (emit determinism).** WHEN either emitter re-runs on an unchanged
  frozen corpus THE emitted plane(s) SHALL be byte-identical.
- **FR-7 (idempotent re-promotion).** WHEN the full corpus is re-promoted THE
  already-landed rows SHALL derive identical content-hash row ids (`ti-gen-*`)
  — no id churn across runs.
- **FR-8 (canonical corpus).** THE authored corpus SHALL be the single seed
  `docs/plan/coach-item-bank-live.seed.json`, grown to **192 rows** (12 base +
  30 Phase A with its 4 disagreement items rewritten in place + 150 new), every
  row `reviewed=false` with the full teaching payload and a seed-only `topic`
  field (1–32) that promotion strips (the `_reviewed_row` field allowlist
  already guarantees this).
  *Amendments (2026-07-07):* D3 renames `topic` → `standard_id` and carries it
  through promotion (`act-english-syllabus-substrate.spec.md` FR-5/FR-8,
  sequenced before T7); D2 folds ~24 promoted Test-01 rows → **~216 rows
  total** (`test01-practice-split.spec.md` FR-5).
- **FR-9 (topic coverage).** WHEN Phase B authoring completes THE seed SHALL
  satisfy the §10 allocation matrix: every syllabus topic ≥1 item, per-bucket
  totals 25 new items each, bands drawn from each topic's syllabus bands.
- **FR-10 (tiered solver review bar).** WHEN a candidate's `difficulty` ≥ 4
  THE promotion run SHALL verify its key with a **capable-tier** solver
  profile; difficulty ≤ 3 uses the fast tier. The tier that verified each row
  SHALL be recoverable from the run's eval stream. Review bar: d1–3 =
  fast-tier-provable; d4–5 = capable-tier-provable.
- **FR-11 (hint generation).** WHEN new items promote THE hint pipeline
  (`generate_hints.py` → hint cascade → `coach-bank-hints.seed.json` →
  `emit_hint_bank.py`) SHALL produce 3-rung ladders for every new bank item
  and regenerate both hint planes (`_hint_bank.ts` +
  `components/subject_coach_bank_hints.py`).
- **FR-12 (test-item emitter).** THE repo SHALL gain
  `scripts/emit_test_item_bank.py`: frozen promoted corpus JSON
  (`docs/plan/coach-item-bank-live.promoted.json`) → deterministically emitted
  `frontend/lib/adapters/engine/_test_item_bank.ts` (rows +
  `seedTestItemBank()`), mirroring `emit_hint_bank.py`'s single-source →
  generated-plane posture.
- **FR-13 (serving unchanged).** THE landed items SHALL serve through the
  existing `seedTestItemBank` + reviewed-gate + per-skill pick with **zero
  serving-code changes** (brainstorm P4).
- **FR-14 (provenance confinement).** THE provenance/leakage guards
  (`test_test_item_provenance_confinement.py`,
  `test_hint_provenance_confinement.py`, `test_hint_bank_leakage.py`) SHALL
  pass over the grown planes; count floors (≥6 / ≥24) rise or stand, never
  weaken (G8).

## 4. Data model / contracts

- **Seed row (authoring input, `reviewed=false`):** existing shape + optional
  `topic: int` (1–32, seed-only; stripped at promotion by the
  `_reviewed_row` allowlist — no wire/schema change, D4 untouched).
- **Frozen promoted corpus (new artifact):**
  `docs/plan/coach-item-bank-live.promoted.json` = the cascade's `passed`
  list verbatim (`_reviewed_row` shape: id, subject, skill_id, difficulty,
  context_html, stem_md, choices, answer_letter, per_choice_rationale,
  why_correct_md, why_tempted_md, rule_md, item_type, reviewed=true,
  generated_by). The emitter's only input.
- **CLI contract:** `generate_test_items.py` gains
  `--capable-difficulty N` (default: off → fast tier for all; Phase B runs
  with `4`). No trust-kernel types touched; no re-signing.

## 5. Invariants & security boundaries

- **#2 trust kernel / #3 components purity:** untouched — `components/` gains
  no code; the solver-tier knob lives in `scripts/` (already
  langgraph-coupled by design).
- **#6 thin orchestration / #7 services:** untouched.
- **Never live-LLM-in-CI:** promotion + hint runs are offline governed jobs;
  everything in `make check`/vitest is deterministic (emitter tests, ratchet,
  provenance, leakage, seed schema pre-flight).
- **Prompt discipline (H1/AP-3):** no new prompt strings in Python; both
  emitters are stdlib-deterministic; solver/hint templates unchanged.
- **Provenance boundary:** `generated_by` re-stamped by the cascade on every
  promoted row (ADR-0015 clause 6); the seed-only `topic` field never reaches
  a serving plane.

## 6. Edge cases

- **s-org stem density:** 25 items inside one broad topic — near-duplicate
  gate (Jaccard ≥ 0.85 on stems) is the enforcement; authoring splits into
  sub-facets (§10) and varies stem verbs/nouns. Expect and tolerate a few
  duplicate quarantines; report them.
- **NO-CHANGE-correct items:** elevated solver-miss risk (Phase A: 1 of 2
  failed). Cap at ~10% of new items (matches real ACT distribution); losses
  quarantine cleanly.
- **DELETE-option items:** proven in Phase A (passed) — allowed.
- **Capable-tier undecidable reply:** same FR-2 path — quarantine, never
  guess; tier does not change parse semantics.
- **Full-corpus re-promotion vs `--existing`:** the run MUST NOT pass the
  current bank as `--existing` (self-collision would quarantine every landed
  row as its own duplicate); intra-batch dedup still applies. Emit is
  wholesale replacement from the frozen corpus.
- **Emit with partial corpus:** emitter emits exactly what the frozen corpus
  contains — a short corpus produces a short (valid) bank; the ratchet then
  arbitrates hints coverage.
- **Historical 4 base-seed rows:** may fail again → FR-3 path; rewriting them
  is optional authoring polish, not a gate.

## 7. Non-functional requirements

- **Cost (one-shot, offline):** ~192 solver graph runs (≈60 capable-tier) +
  ~176 hint graph runs + retry margin — fast-tier-dominant, single-digit
  dollars at Phase A rates (~$0.0001–0.001/call fast; capable ≈ 10–30×).
- **Calendar:** authoring 150 rich items is the long pole (LLM spend is not).
- **Determinism:** emitters + all CI gates are L1; live promotion/hint runs
  are L3 (on-demand, outputs pasted into the impl doc — evidence, not
  summaries).
- **Reversibility:** serving planes are wholesale-regenerated from frozen
  corpora in git — rollback = re-emit the previous corpus.

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1/2 | existing `tests/components/test_test_item_generation.py` (cascade fail-closed, undecidable) | L1 | yes |
| FR-3 | promotion run report lists quarantined rows (impl-doc evidence) | L3 | no (on-demand) |
| FR-4 | existing `_hint_bank.test.ts` ladderGaps ratchet | L1 (vitest) | frontend CI |
| FR-5 | existing `tests/components/test_hint_bank_leakage.py` | L1 | yes |
| FR-6 | NEW `tests/scripts/test_emit_test_item_bank.py::test_emit_idempotent` (+ hints emitter already covered) | L1 | yes |
| FR-7 | NEW `...::test_row_ids_stable_across_reruns` (pure `_row_id` property) | L1 | yes |
| FR-8 | NEW seed pre-flight test: every seed row passes `_schema_violations`, topic ∈ 1–32, 192 rows | L1 | yes |
| FR-9 | NEW matrix test: seed topic/bucket/band counts == §10 matrix | L1 | yes |
| FR-10 | NEW `tests/scripts/test_generate_test_items_config.py::test_capable_tier_routing` (mocked profiles; difficulty→tier) | L2 | yes |
| FR-11 | live hint run outputs + regenerated planes diff (impl doc) | L3 | no |
| FR-12 | NEW emitter unit tests (golden small corpus → TS module parses, seedTestItemBank present) | L1 | yes |
| FR-13 | existing frontend serving tests over the regenerated bank | L1 (vitest) | frontend CI |
| FR-14 | existing arch/provenance tests over grown planes | L1 | yes |

Failure-path tests (FR-1/2/3/4/5) precede happy-path work in the task order.

## 9. Definition of Done

- [ ] P0: rail sandwich fix (uncommitted `services/guardrails.py` +
      `prompts/input_guardrail.j2` + tests + decisions entry) committed first.
- [ ] All FRs implemented; each new test seen to fail first (red→green).
- [ ] `make check` + `pytest tests/architecture/ -q` green; frontend vitest
      green (ratchet satisfied, zero new waivers or reasons given).
- [ ] Promotion + hint run outputs pasted (not summarized) into
      `docs/plan/act-english-bank-phase-b.impl.md`.
- [ ] `decisions.md` entries: test-item emitter (ADR-0014 seam reuse) +
      tiered solver review bar. No ⚠️ Ask-first trigger fired → no new ADR.
- [ ] Bank serves ≥170 items; every topic ≥1 item (matrix test green).

## 10. Authoring allocation matrix (FR-9 contract)

150 new items; per bucket 25. Topic numbers from the brainstorm inventory;
bands per topic follow the syllabus. Sub-facets guide stem variety (dup gate).

| Bucket | Topic allocation (topic→count) | Sum |
|--------|-------------------------------|-----|
| s-punc | 14 commas→7 · 24 apostrophes→6 · 29 colons/semicolons→6 · 30 parentheticals→3 · 31 restrictive→3 | 25 |
| s-gram | 17 subj-verb→3 · 7,11,12,13,18,19,22,26,28→2 each · 3,16,23,27→1 each | 25 |
| s-sent | 15 fragments/run-ons→5 · 21 modifiers→5 · 10 clause-joining→4 · 25 parallelism→4 · 32 adv-revision→4 · 20 adj-placement→3 | 25 |
| s-rhet | 2 purpose (audience/connotation/ethos-pathos-logos)→13 · 4 style-tone (register/figures/comparison)→12 | 25 |
| s-org | 1 topic-and-organization: topic sentences→5 · concluding→4 · transitions→6 · development→5 · thesis/argument→5 | 25 |
| s-style | 9 word usage→7 · 5 redundancy→6 · 6 shades-of-meaning→6 · 8 word nuance→6 | 25 |

Plus in-place rewrites of the 4 Phase A disagreement items (intro-comma →
mandatory-comma clause; appositive NO-CHANGE → clearer distractors;
colon-after-are → self-contained labels; two-of comparative → underline
`most` only).

---

## 11. Implementation plan (Stage 2 — gated 2026-07-07, amended: rail fix rides this branch)

Branch: `feat/act-bank-phase-b`. P0 (the uncommitted rail sandwich fix) is the
**first commit** on it — no separate PR (human amendment at the plan gate).

| WP | Files | Depends on |
|----|-------|-----------|
| P0 commit rail fix | `services/guardrails.py`, `prompts/input_guardrail.j2`, `tests/services/test_guardrails.py`, `docs/adr/decisions.md` | — |
| WP1 solver-tier knob | `scripts/generate_test_items.py` (`--capable-difficulty`, second graph), NEW `default_capable_profile()` in `services/base_config.py` (sibling of :302), extend `tests/scripts/test_generate_test_items_config.py` | P0 |
| WP2 bank emitter | NEW `scripts/emit_test_item_bank.py` (mirrors `emit_hint_bank.py`: `_ROW_FIELDS` allowlist, `_sorted_rows`, `json.dumps(indent=4, ensure_ascii=False)`, `_die` fail-fast; TS plane only), NEW `tests/scripts/test_emit_test_item_bank.py` | — |
| WP3 seed gates | NEW `tests/scripts/test_bank_seed_preflight.py` (schema pre-flight + §10 matrix conformance; RED until authoring lands) | — |
| WP4 authoring | `docs/plan/coach-item-bank-live.seed.json` → 192 rows | WP3 |
| WP5 promotion run | live: `--import-seed … --capable-difficulty 4` (NO `--existing`) → `docs/plan/coach-item-bank-live.promoted.json`; evidence → `act-english-bank-phase-b.impl.md` | WP1+WP4 |
| WP6 hint ladders | live: `scripts/generate_hints.py --questions <new promoted items>` → `docs/plan/coach-bank-hints.seed.json` → `scripts/emit_hint_bank.py` (both hint planes) | WP5 |
| WP7 landing + gates | emit `_test_item_bank.ts`; `make check` + arch + frontend vitest; decisions.md ×2 | WP2+WP5+WP6 |

Constitution: no ⚠️ Ask-first trigger (no new dep/type/node/service; emitter =
ADR-0014 seam sibling, G1 satisfied in decisions.md). WP1/2/3 parallel after P0.

## 12. Task list (Stage 3) — pass/fail mapped to FRs

- **T0** Branch + commit rail fix. *Pass:* commit on branch; `make check` green. (DoD-P0)
- **T1** ~~Grounding~~ DONE 2026-07-07: hints CLI `--questions/--out/--existing` (`generate_hints.py:103-107`); tier helper = NEW `base_config` accessor; emitter conventions (`emit_hint_bank.py:95-216`).
- **T2** WP3 red tests. *Pass:* pre-flight+matrix tests exist and FAIL on the 12-row seed; schema logic passes on known-good rows. (FR-8, FR-9)
- **T3** WP1 knob, red→green. *Pass:* L2 tier-routing test (d≥4→capable, else fast, default off); existing config tests green. (FR-10)
- **T4** WP2 emitter, red→green. *Pass:* double-emit byte-identical on a synthetic fixture; output parses; `seedTestItemBank` present. (FR-6, FR-12)
- **T5** WP4a fold 12+30 (4 rewritten in place) → 42-row seed. *Pass:* pre-flight schema section green; matrix test still red (by design). (FR-8 partial)
- **T6** WP4b author 150 in six 25-item bucket tranches. *Pass:* T2 tests fully GREEN (192 rows, matrix conformance). (FR-8, FR-9)
- **T7** WP5 promotion run. *Pass:* promoted ≥170; quarantines listed w/ stage; capable-tier calls visible in eval stream for d4–5; ids stable. (FR-1,2,3,7,10)
- **T8** WP6 ladders. *Pass:* `ladderGaps == []`, zero new waivers; leakage test green. (FR-4, FR-5, FR-11)
- **T9** WP7 landing. *Pass:* `make check` + `tests/architecture/` + frontend vitest all green; bank ≥170 rows. (FR-6,12,13,14)
- **T10** Evidence + records: `.impl.md` pasted outputs; decisions.md ×2; spec Status → Implemented. *Pass:* §9 DoD all ticked.

## 13. Analyze (Stage 4 — cross-artifact, 2026-07-07)

- Spec↔plan↔tasks: every FR owned by a WP and a task (table above); no
  zero-coverage requirement. Baseline: `make check` green on the current tree
  (5207 passed, 2026-07-07, post-rail-fix — output pasted in session).
- References: all file paths probed this session (explore sweep + greps); the
  ONE not-yet-existing API is `default_capable_profile()` — an intentional
  WP1 addition, flagged here (not a broken reference).
- CRITICAL findings: none. Invariants #1–8 untouched; live LLM stays
  off the CI hot path (L3 runs are on-demand with pasted evidence).
