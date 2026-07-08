# Spec — D3: ACT-English syllabus-as-data substrate

> EARS criteria; failure paths first. Spec = the *what*; the ADR this change
> requires (G1 new abstraction: canonical syllabus corpus + coverage ratchet)
> carries the *why*.

**Status:** Draft — 2026-07-07
**Owner:** Rajnish Khatri
**Related:** `docs/plan/act-english-full-bank.brainstorm.md` (D3 direction +
32-topic extraction table), `docs/plan/act-english-bank-phase-b.spec.md`
(consumes the tag), ADR-0014 (single-source corpus seam), ADR-0015 (cascade),
ADR-0021 (bank serving). ADR: **new — required at implementation** (G1).

---

## 1. Goal

Make "the bank is full" a measurable, CI-enforced property instead of vibes:
a canonical machine-readable syllabus (32 standards × bands × app-skill
mapping), a `standard_id` tag that flows seed → promoted corpus, and a
rises-only coverage ratchet over the topic×band matrix.

## 2. Context

- The 12pp IXL PDF (`docs/ACT-syllabus/act-english.pdf`) was hand-extracted to
  a validated 32-topic table (brainstorm §topic-extraction, gate-accepted
  2026-07-07). The PDF stays a citation; the extraction becomes data.
- Phase B already introduces a seed-only `topic` field (1–32) that promotion
  strips. D3 formalizes it: rename to `standard_id`, carry it through
  promotion, count coverage against the syllabus.
- **Scope (clarified 2026-07-07, human gate): full converter now.** The
  canonical JSON is emitted into BOTH consumption planes today via a
  deterministic converter (`emit_hint_bank.py` pattern): a TS module for the
  frontend (D4's consumer) and a Python data asset for `components/`
  (generation targeting / coverage tooling). Rejected: lean substrate with
  emitters deferred (gate chose build-ahead so D4 lands against an existing
  plane).
- Sequencing (clarified): land **before Phase B's promotion run (T7)** so the
  tag flows into `coach-item-bank-live.promoted.json` on the first full run —
  no re-promotion ever needed. T7 gains this dependency.
- **Non-goals:** wire-kernel/product exposure of standards (D4's spec+ADR —
  the emitted TS module is data-plane only until D4 consumes it),
  PDF parsing, per-standard mastery UX.

## 3. Functional requirements (EARS)

- **FR-1 (invalid tag fails closed).** IF a seed row carries a `standard_id`
  not present in the canonical syllabus THEN the seed pre-flight SHALL fail
  naming the row and the unknown id.
- **FR-2 (band mismatch fails closed).** IF a seed row's `difficulty` is not
  one of its standard's syllabus bands THEN the pre-flight SHALL fail (a
  comma item at a band commas never occupies is a tagging error).
- **FR-3 (coverage regression).** IF the promoted corpus's per-cell
  (standard×band) count falls below the recorded floor THEN the ratchet test
  SHALL fail (floors only rise — G8 posture).
- **FR-4 (canonical syllabus).** THE repo SHALL hold
  `docs/plan/act-english-syllabus.seed.json`: exactly 32 standards, each
  `{standard_id (1–32), name, category (production|knowledge|conventions),
  bands ([1..5] subset), app_skill (s-*)}`, byte-for-byte matching the
  brainstorm extraction table.
- **FR-5 (tag carriage).** WHEN the cascade promotes a row THE promoted row
  SHALL carry the seed's `standard_id` verbatim (allowlist addition in
  `_reviewed_row`); promotion SHALL never invent or default a tag.
- **FR-6 (floors file).** THE ratchet SHALL read per-cell floors from a
  checked-in `docs/plan/act-english-coverage-floors.json`; updating a floor
  downward SHALL be impossible without failing the ratchet's monotonicity
  check (compares floors file to measured coverage AND to its own committed
  history via the ≥-guard pattern).
- **FR-7 (coverage report).** THE repo SHALL gain a deterministic coverage
  report (script or pytest `-s` artifact): the standard×band matrix with
  fill counts from the promoted corpus — the "full is measurable"
  deliverable, runnable offline with zero LLM calls.
- **FR-8 (Phase B compatibility).** WHILE Phase B's seed uses `topic` THE
  migration SHALL rename it to `standard_id` in the same change that lands
  the syllabus JSON (one rename, no dual-field era).
- **FR-9 (syllabus converter).** THE repo SHALL gain
  `scripts/emit_syllabus.py`: canonical JSON → deterministically emitted
  `frontend/lib/adapters/engine/_act_english_syllabus.ts` AND
  `components/act_english_syllabus.py` (pure data asset, stdlib-only), the
  `emit_hint_bank.py` two-plane pattern. Byte-identical re-emit on an
  unchanged seed (the FR-6 determinism bar of the Phase B emitter applies).
- **FR-10 (plane drift).** IF an emitted syllabus plane is edited by hand
  (drifts from what the converter produces) THEN a deterministic drift test
  SHALL fail (re-emit-and-compare in CI, no LLM).

## 4. Data model / contracts

- `act-english-syllabus.seed.json` — new canonical corpus (shape in FR-4).
- Seed row: `topic` → `standard_id: int` (1–32).
- Promoted row (`_reviewed_row` in `components/test_item_generation.py`):
  gains `standard_id` in the field allowlist. Serving planes unchanged
  (the emitted TS bank does NOT carry the tag in D3 — D4 decides the wire).
- `act-english-coverage-floors.json` — `{ "<standard_id>:<band>": int }`,
  rises-only.

## 5. Invariants & security boundaries

- `components/` change is pure data-plumbing (one allowlist entry) —
  invariant #3 intact, no framework imports.
- Ratchet + pre-flight + report are L1 deterministic (no LLM, no I/O beyond
  repo files) — CI-safe.
- No trust-kernel types; no new deps; the ADR covers the G1 abstraction.

## 6. Edge cases

- Standards spanning non-contiguous bands (e.g. 13: bands 1,3) — FR-2
  validates set-membership, not range.
- A promoted corpus row from the pre-D3 era lacking `standard_id` (the 8 live
  rows if not re-promoted) — ratchet counts only tagged rows and the report
  flags untagged rows; FR-5 forbids inventing tags retroactively.
- Two app-skills claiming one standard: the extraction maps each standard to
  exactly ONE `app_skill`; FR-4's schema enforces single-valued mapping.
- Floors file cell absent for a filled cell — treated as floor 0 (report
  suggests the bump; ratchet doesn't fail on missing floors, only on
  regression below recorded ones).

## 7. Non-functional requirements

Zero LLM cost; all-deterministic; single-commit reversible (data + one
allowlist line + tests). Calendar: small — should land before Phase B T7.

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1/2 | extend `tests/scripts/test_bank_seed_preflight.py` (unknown id; band mismatch) | L1 | yes |
| FR-3/6 | NEW `tests/architecture/test_syllabus_coverage_ratchet.py` (regression fails; floors monotone) | L1 | yes |
| FR-4 | NEW syllabus-schema test (32 rows, shape, unique ids, category/app_skill enums) | L1 | yes |
| FR-5 | extend `tests/components/test_test_item_generation.py` (tag carried verbatim; absent tag NOT invented) | L1 | yes |
| FR-7 | report golden test on a fixture corpus | L1 | yes |
| FR-8 | pre-flight rejects the old `topic` key after rename | L1 | yes |
| FR-9 | NEW `tests/scripts/test_emit_syllabus.py` (double-emit byte-identical; both planes parse; 32 standards) | L1 | yes |
| FR-10 | drift test: re-emit == committed planes | L1 | yes |

## 9. Definition of Done

- [ ] ADR appended (`docs/adr/`): syllabus-as-data + converter + ratchet,
      Options incl. rejected lean-substrate (emitters deferred) and
      fixed-target variants; index + log lines.
- [ ] All FRs red→green; `make check` green.
- [ ] Coverage report over the current corpus committed as the baseline
      floors (post-Phase-B numbers if sequenced after T7).
- [ ] Phase B spec FR-8's `topic` field renamed in the same change (no split
      era).
