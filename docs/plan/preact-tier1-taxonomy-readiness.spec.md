# Spec — Tier-1 misconception-callout taxonomy-readiness probe

**Status:** Approved — 2026-07-12
**Owner:** Rajnish Khatri
**Related:** brainstorm [preact-tier1-misconception-taxonomy.brainstorm.md](preact-tier1-misconception-taxonomy.brainstorm.md) (SDD Stage-1, HG-2 → **D3 measure-first** chosen 2026-07-12) · parent [preact-parity-epic-E1b.brainstorm.md](preact-parity-epic-E1b.brainstorm.md) (tier-1 deferred) · design OQ-2 in `Eng-coach-ui-design/e1-learn-skill-delivery/specs/PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md` §3.4/tier-1 · precedent `scripts/syllabus_coverage_report.py` + `tests/architecture/test_syllabus_coverage_ratchet.py`

> **Light spec** (runbook §6 measurement/exploratory carve-out). The deliverable is a **read-only
> measurement probe + a decision rule** — no taxonomy authored, no tier-1 render code, no DB change,
> **no ADR**. It ships the *decision* ("author the D1 taxonomy now, or defer"), not the feature.

---

## 1. Goal

Give the team a **measured, honest answer** to one question that currently rests on assumption:
*is there enough tagged, themeable misconception data for the deferred tier-1 "Your pattern · X"
aggregate callout to ever fire meaningfully?* The probe reports per-skill tag coverage, **candidate
themes on the already-controlled `standard_id` axis** (never manufactured), and a **simulated
per-learner tier-1 fire-rate**, then emits a machine-readable **verdict** (`build` / `defer`) against
explicit thresholds. It converts "author the D1 controlled taxonomy?" from a guess into a number.

## 2. Context

The `/learn/skill` tier-1 callout (`"Your pattern · {theme}"`, design §3.4 tier-1 / DATA-CALL-1)
renders only when a learner has **≥2 due misses that share a genuine misconception theme**. E1b
formally deferred it behind "the reviewed OQ-2 tag-clustering pipeline" — a *separate initiative*.
The Stage-1 brainstorm chose the **measure-first** posture (HG-2 = D3): before paying the authoring
+ data-accumulation cost of a controlled taxonomy (D1), measure whether the corpus can support the
feature at all.

Two facts from the brainstorm's premise audit make measurement necessary, not obvious:
- **The free-text tags don't cluster** — 47/171 tagged, all 47 distinct, 0 exact clusters; naive
  word-normalization **manufactures false themes** (the audit's finding: `s-gram` "where"×3 are three
  *different* misconceptions). Clustering on free text is the exact OQ-2 anti-pattern.
- **But `standard_id` is an already-controlled axis** — every tagged item carries a `standard_id`
  from the 32-standard ACT-English syllabus (`docs/plan/act-english-syllabus.seed.json`, governed by
  `syllabus_coverage_report.py` + its ratchet). Clustering tagged items by `standard_id` **within a
  multi-standard skill** is honest, not manufactured — and the audit found genuine candidate clusters
  (e.g. `s-sent` standard 15 "Sentences, fragments and run-ons" = 3 tagged items; `s-style` standard 5
  "Redundancy" = 3). So tier-1 is **not permanently dead** — it is *readiness-gated*, which is exactly
  what a probe measures.

The load-bearing cost the probe exists to size is **corpus density + authoring calendar time**, not
engineering time.

## 3. Functional requirements (EARS)

Numbered, testable, one behavior each. **Failure paths first** (FR-1…FR-4).

- **FR-1 (honesty — untagged never counted).** IF a bank item's `misconception` is `null` or empty
  THEN THE SYSTEM SHALL NOT count it toward any theme, cluster, or fire-rate, and SHALL report the
  untagged count separately (mirrors `syllabus_coverage_report.py` FR-5 "UNTAGGED rows never counted,
  flagged at the foot").
- **FR-2 (no manufactured themes).** IF two tagged items in the same skill do **not** share a
  `standard_id` THEN THE SYSTEM SHALL NOT treat them as one theme — the *only* clustering key is
  `standard_id` (a pre-existing controlled axis); free-text word overlap SHALL NEVER form a cluster.
- **FR-3 (single-standard skills excluded from clustering).** IF a skill maps to exactly one
  `standard_id` in the syllabus THEN THE SYSTEM SHALL mark its clusters `not-meaningful` (whole-skill
  bucket ≠ sub-theme) and exclude it from the fire-rate simulation's cluster count — a "pattern in X ·
  X" callout is tautological. (`s-org` is the current instance: 1 standard, 5/5 tagged all under it.)
- **FR-4 (candidate ≠ theme — human-review gate).** THE SYSTEM SHALL label every `standard_id` cluster
  it surfaces as a **candidate requiring human review** ("is standard N a genuine misconception theme
  for this skill?"), NEVER as a confirmed theme. The probe surfaces; a human ratifies (OQ-2 discipline).
- **FR-5 (per-skill coverage report).** THE SYSTEM SHALL report, per skill: total items, tagged count,
  tagged %, distinct `standard_id`s among tagged items, and the size of each `standard_id` cluster
  (≥2 tagged items = a *candidate fireable theme*).
- **FR-6 (simulated tier-1 fire-rate).** THE SYSTEM SHALL simulate, over a deterministic population of
  synthetic learners with parametrized miss behavior, the fraction of learners for whom **≥2 misses
  land in one meaningful `standard_id` cluster** (the tier-1 firing condition, mirroring the render
  join `newest_due_miss.ts` extended from newest-single to ≥2-in-cluster), and report the fire-rate
  per skill and overall.
- **FR-7 (explicit due-ness model, stated not hidden).** THE SYSTEM SHALL make the due-ness assumption
  an **explicit, documented parameter** of the simulation (default: treat every missed skill as due —
  the *upper bound* on fire-rate), because FSRS due-logic is TypeScript-only and MUST NOT be silently
  re-implemented in the probe. The report SHALL state which due-model produced the number.
- **FR-8 (machine-readable verdict against thresholds).** THE SYSTEM SHALL emit a JSON verdict
  `{verdict: "build"|"defer", thresholds: {min_meaningful_clusters, min_fire_rate}, measured: {...},
  reasons: [...]}` (mirrors `scripts/measure_l2l3_goaljudge.py`'s `formal_gate` verdict-to-disk
  pattern). `build` iff ≥1 multi-standard skill clears the cluster threshold **and** simulated
  fire-rate clears the rate threshold; otherwise `defer` with the failing reason(s).
- **FR-9 (read-only, deterministic, offline).** THE SYSTEM SHALL perform zero writes to the bank, DB,
  or any shipped artifact, make zero network/LLM calls, and produce byte-identical output for
  identical inputs (stdlib + fixed-seed only) — safe to run in `make check`.

## 4. Data model / contracts

**No new persisted types. No DB change. No wire change.** The probe *reads*:

| Input | Path | Shape used |
|-------|------|-----------|
| Serving bank | `docs/plan/coach-item-bank-live.promoted.json` (the "governed practice bank ADR-0021", emitted → `_test_item_bank.ts`; misnamed "coach", is the `ti-gen-*` bank `/learn` serves) | rows `{id, skill_id, standard_id, misconception (string\|null), difficulty}` |
| Syllabus (controlled axis) | `docs/plan/act-english-syllabus.seed.json` | 32 rows `{standard_id, name, category, app_skill}` — gives per-skill standard count (FR-3) + human-readable theme names |

**New output artifacts (probe-owned, not shipped content):**
- Human report to stdout (fixed-width, mirrors `render_report`).
- `docs/plan/tier1-taxonomy-readiness.verdict.json` — the machine verdict (FR-8), committed so the
  decision is auditable + diffable across re-runs as the bank grows.

**The threshold decision rule (resolved values → §10 clarify):** `min_meaningful_clusters` and
`min_fire_rate` are the two numbers that flip `build`/`defer`. Default proposals carried to clarify.

## 5. Invariants & security boundaries

- **Architecture invariants:** the probe lives in `scripts/` (offline tooling), imports **stdlib only**
  (Invariant-agnostic — it's not in a package layer). It does **not** import `frontend/`, `trust/`,
  `services/`, or `components/`; it reads two JSON files. No layer boundary crossed.
- **No live LLM in CI** (🚫 Never): the probe makes zero model calls — pure arithmetic over JSON.
- **AP-6 (return None, not a fabricated 0.0):** where a skill has no tagged items or no meaningful
  clusters, the probe reports `—`/absent, never a fabricated `0.0` fire-rate that reads as "measured".
- **OQ-2 anti-manufacture** is the security boundary of *meaning* here: FR-2/FR-3/FR-4 guarantee the
  probe never invents a taxonomy — it clusters only on the pre-controlled `standard_id` axis and
  surfaces candidates for human ratification.
- **No ADR trigger:** no new dependency, no trust-kernel type, no new graph node, no new service, no
  new abstraction on a shipped path. A `scripts/` measurement tool + a companion architecture test is
  the `syllabus_coverage_report.py` precedent exactly (that shipped without an ADR).

## 6. Edge cases

- **Bank file absent** → report zero coverage + `verdict: defer` (mirror `syllabus_coverage_report.py`
  absent-file = zero-coverage), never crash.
- **A skill with 0 tagged items** → `tagged: 0`, no clusters, contributes 0 to fire-rate; reported, not
  skipped silently.
- **Single-standard skill** (`s-org`) → clusters marked `not-meaningful` (FR-3), excluded from the
  build gate — must not let a tautological whole-skill bucket trip `build`.
- **A `standard_id` on a tagged item that isn't in the syllabus registry** → flagged as an integrity
  warning at the foot (like untagged rows), not counted — the two controlled axes must agree.
- **Fire-rate simulation with an empty meaningful-cluster set** → fire-rate is exactly `0.0` *and*
  that 0.0 is labeled "no meaningful clusters exist" (distinguish structural-zero from measured-low).
- **Duplicate-named bank copies** (`Eng-coach-ui-design/…` has 0 tags; worktree copies) → the probe
  path is pinned to `docs/plan/…`; a `--corpus` override exists but defaults are explicit.

## 7. Non-functional requirements

- **Determinism:** L1 exact — fixed synthetic-learner seed, stdlib `random` seeded or pure enumeration;
  byte-identical output. Runs inside `make check` (no cadence/live path).
- **Cost:** zero LLM, zero network, milliseconds — pure JSON arithmetic.
- **Reversibility:** fully reversible — a script + a test + a committed verdict JSON; deletes cleanly.
- **The due-ness model is a documented approximation** (FR-7), not the shipped FSRS logic — the report
  states this so the number is never mistaken for production-exact.

## 8. Test plan

Failure-path tests before happy-path. All L1 deterministic, all in `make check`.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `test_untagged_items_never_counted` — null/empty misconception excluded from every count | L1 | yes |
| FR-2 | `test_free_text_overlap_never_clusters` — two same-skill items sharing a word but not a `standard_id` are NOT one theme | L1 | yes |
| FR-3 | `test_single_standard_skill_marked_not_meaningful` — a 1-standard skill's cluster excluded from build gate | L1 | yes |
| FR-4 | `test_clusters_labelled_candidate_not_theme` — output marks clusters `candidate`/needs-review | L1 | yes |
| FR-5 | `test_per_skill_coverage_counts` — per-skill totals reconcile (Σ tagged = 47, Σ items = 171 on today's bank) | L1 | yes |
| FR-6 | `test_fire_rate_counts_two_in_one_cluster` — a synthetic learner with 2 misses in one meaningful cluster fires; 2 misses across clusters does not | L1 | yes |
| FR-7 | `test_due_model_is_explicit_param` — changing the due-model param changes the number + the report states which model ran | L1 | yes |
| FR-8 | `test_verdict_build_iff_thresholds_clear` — `build` only when clusters≥N AND fire-rate≥X; else `defer` + reason | L1 | yes |
| FR-8 | `test_verdict_defer_on_todays_bank` — against the real committed bank, verdict is `defer` (or `build`) with the reason stated (regression-locks the current measured reality) | L1 | yes |
| FR-9 | `test_probe_is_read_only_deterministic` — no writes except the verdict JSON; identical output on repeat run | L1 | yes |

Companion architecture test `tests/architecture/test_tier1_readiness_probe.py` (mirrors
`test_syllabus_coverage_ratchet.py`): asserts the probe's pure helpers behave (FR-1…FR-8) and that the
committed verdict matches a fresh run (drift lock).

## 9. Definition of Done

- [ ] `scripts/tier1_taxonomy_readiness.py` (read-only, stdlib-only, deterministic) implements FR-1…FR-9.
- [ ] `docs/plan/tier1-taxonomy-readiness.verdict.json` committed with today's measured verdict.
- [ ] Every FR has a passing test **seen to fail first** (red→green); output pasted, not summarized.
- [ ] `make check` green (lint + format-check + pyright + test) incl. the new architecture test.
- [ ] Invariants §5 unbroken (`tests/architecture/` green); no ADR (confirmed no ⚠️ trigger).
- [ ] The verdict + its thresholds recorded so the D1 build/defer decision is auditable.

## 10. Clarify resolutions

_(sdd-spec clarify pass — recorded here; open items flagged for the human gate.)_

- **CQ-1 — the two thresholds (FR-8):** **RESOLVED at the human gate 2026-07-12** —
  `min_meaningful_clusters` = **≥1 skill with a `standard_id` cluster of ≥3 tagged items**;
  `min_fire_rate` = **≥5%** of simulated learners under the all-missed-skills-due upper-bound model.
  `build` iff BOTH clear; else `defer` + reason. Measured substrate: today's bank has exactly 4
  meaningful ≥3-clusters (`s-rhet` std 2 & 4, `s-sent` std 15, `s-style` std 5) → the cluster gate
  PASSES today, so the verdict hinges on the fire-rate simulation (the honest tie-breaker).
- **CQ-2 — "genuine theme" operationalization (FR-2/4):** **RESOLVED** — cluster **only** on the
  pre-controlled `standard_id` axis, within multi-standard skills, surfaced as human-review candidates.
  No free-text/LLM derivation (that's D1/D4, gated behind this measurement).
- **CQ-3 — which corpus for the fire-rate sim (FR-6/7):** **RESOLVED** — **synthetic, in-probe learner
  population**, not `build_memory_multisession_corpus.py` (grounded: that's the *memory-recall* corpus,
  wrong subsystem, no skill/attempt/due concepts) and not a live FSRS run (grounded: FSRS is TS-only,
  no Python scheduler). Due-ness is an explicit param (FR-7), default = all-missed-skills-due (upper
  bound). This keeps the probe honest about being an approximation.
- **CQ-4 — naming (avoid collision):** **RESOLVED** — call it the **tier-1 taxonomy-readiness probe**,
  NOT "D3": `syllabus_coverage_report.py` already self-names "D3" (ADR-0022) and there's a released
  Epic-D "D3" (session-length). File = `scripts/tier1_taxonomy_readiness.py`.

## 11. Thresholds — RESOLVED (human gate 2026-07-12)

`min_meaningful_clusters` = **≥1 skill with a `standard_id` cluster of ≥3 tagged items**;
`min_fire_rate` = **≥5%** of simulated learners (all-due upper-bound model). `build` iff BOTH clear.

Measured today: 4 meaningful ≥3-clusters exist → **cluster gate PASSES**, so the verdict is decided by
the fire-rate simulation. Since the largest cluster is 3 items and firing needs a learner to miss ≥2
of *those specific* items, the expected verdict on today's bank is **`defer`** unless the simulated
fire-rate clears 5% — the honest, useful answer: "keep authoring tagged items until a standard-cluster
densifies, *then* build D1." The probe re-runs cheaply as the bank grows and flips to `build`
automatically when the data arrives. Spec fully resolved → **advance to Plan + Tasks.**
