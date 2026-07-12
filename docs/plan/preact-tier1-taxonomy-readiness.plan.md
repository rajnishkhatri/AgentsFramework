# Plan + Tasks — Tier-1 taxonomy-readiness probe

**Status:** Draft — 2026-07-12 · derived from [preact-tier1-taxonomy-readiness.spec.md](preact-tier1-taxonomy-readiness.spec.md) (Approved) · SDD Stages 2 (plan) + 3 (tasks)
**No ADR** — confirmed no ⚠️ Ask-first trigger (spec §5): a read-only `scripts/` measurement tool + companion architecture test, the `syllabus_coverage_report.py` precedent exactly (shipped without an ADR).

---

## A. Architecture

A single stdlib-only Python module of **pure helpers** + a thin `main()`, plus a companion
architecture test — the exact two-file shape of the syllabus-coverage precedent
(`scripts/syllabus_coverage_report.py` + `tests/architecture/test_syllabus_coverage_ratchet.py`).

```
scripts/tier1_taxonomy_readiness.py
├─ load_bank(path) -> list[dict]                 # absent file → [] (edge: FR-6/§6)
├─ load_syllabus(path) -> {skill_id: set[standard_id]}   # per-skill standard count (FR-3)
├─ tagged_rows(bank) -> list[dict]               # non-null non-empty misconception only (FR-1)
├─ untagged_ids(bank) -> list[str]               # flagged at foot, NEVER counted (FR-1)
├─ meaningful_clusters(tagged, syllabus) -> dict[(skill,std)] -> count
│      # key ONLY on standard_id (FR-2); EXCLUDE single-standard skills (FR-3); ≥2 = candidate theme
├─ integrity_warnings(tagged, syllabus) -> list[str]   # tagged std_id not in registry (§6)
├─ simulate_fire_rate(tagged, syllabus, *, n_learners, misses_per_learner, due_model, seed)
│      -> {per_skill: {skill: rate}, overall: float}
│      # a learner draws misses over tagged items; fires iff ≥2 land in ONE meaningful cluster
│      # due_model is an EXPLICIT param (FR-7); default "all_due" = upper bound
├─ verdict(clusters, fire_rate, *, min_meaningful_clusters, min_fire_rate) -> dict
│      # {verdict:"build"|"defer", thresholds, measured, reasons} (FR-8)
├─ render_report(...) -> str                     # fixed-width human report (mirror precedent)
└─ main()                                        # argparse --corpus/--syllabus/--out; print + write verdict JSON

tests/architecture/test_tier1_readiness_probe.py
└─ imports the pure helpers (from scripts.tier1_taxonomy_readiness import ...) — precedent
   test_syllabus_coverage_ratchet.py:27; asserts FR-1..FR-9 + verdict-drift lock.

docs/plan/tier1-taxonomy-readiness.verdict.json   # committed machine verdict (FR-8), diffable as bank grows
```

**Grounded anchors** (verified `file:line`):
- Read-only report + "UNTAGGED never counted, flagged at foot" discipline: `scripts/syllabus_coverage_report.py:36-53,93-97`.
- Test import pattern `from scripts.<mod> import <helpers>`: `tests/architecture/test_syllabus_coverage_ratchet.py:27`.
- Verdict-JSON-to-disk pattern: `scripts/measure_l2l3_goaljudge.py:279,355-358` (`write_text(json.dumps(result, indent=2)+"\n")`).
- Bank rows carry `{id, skill_id, standard_id, misconception, difficulty}` (all 171): `docs/plan/coach-item-bank-live.promoted.json`; syllabus `{standard_id, name, app_skill}` × 32: `docs/plan/act-english-syllabus.seed.json`.
- Firing condition mirrors the shipped render join extended newest-single → ≥2-in-cluster: `frontend/lib/translators/newest_due_miss.ts:35-58` (`due_at <= now` set; miss→question_id→skill/tag). Due-ness is per-skill (`SkillState.due_at`, `engine_entities.ts:305`); Attempt has NO skill_id (`:224-234`) → join via question — the sim models this by drawing over *tagged bank items* keyed to their skill+standard.

**Why the sim is synthetic, not corpus-driven** (grounded, spec CQ-3): `build_memory_multisession_corpus.py` is the memory-recall subsystem (no skill/attempt/due concepts); FSRS is TS-only (no Python scheduler, no `fsrs` in `pyproject.toml`). Re-implementing FSRS in Python would risk silent divergence (Invariant-adjacent smell). So the probe models due-ness as an **explicit documented parameter** and reports the number as an approximation (FR-7).

## B. Migration / touchpoints

Purely additive — **3 new files, 0 edits to shipped code**:
| File | Action |
|------|--------|
| `scripts/tier1_taxonomy_readiness.py` | NEW — the probe |
| `tests/architecture/test_tier1_readiness_probe.py` | NEW — FR gates + drift lock |
| `docs/plan/tier1-taxonomy-readiness.verdict.json` | NEW — committed verdict artifact |

No DB, no wire, no `frontend/`, no ADR, no `pyproject.toml` dependency (stdlib only).

## C. Tasks (atomic, file-level, red→green; 1:1 EARS→verification)

Dependency markers: `[dep: Tn]`. Parallel-safe tasks share a group letter.

- **T1 [group A]** — `load_bank` + `load_syllabus` + `tagged_rows` + `untagged_ids`.
  **Test first (red):** `test_untagged_items_never_counted` (FR-1), `test_per_skill_coverage_counts`
  (FR-5, Σtagged=47/Σitems=171 on real bank). Verify: null/empty misconception excluded; untagged
  count surfaced.
- **T2 [group A]** — `meaningful_clusters` + `integrity_warnings`.
  **Red:** `test_free_text_overlap_never_clusters` (FR-2 — same-skill items sharing a *word* but not a
  `standard_id` are NOT one cluster), `test_single_standard_skill_marked_not_meaningful` (FR-3 —
  `s-org` excluded), `test_clusters_labelled_candidate_not_theme` (FR-4). Verify: cluster key is
  `standard_id` only; single-standard skills marked `not-meaningful`; clusters labelled `candidate`.
- **T3 [dep: T2]** — `simulate_fire_rate` with explicit `due_model` param + fixed seed.
  **Red:** `test_fire_rate_counts_two_in_one_cluster` (FR-6 — 2 misses in one meaningful cluster fires;
  2 across clusters does not), `test_due_model_is_explicit_param` (FR-7 — changing the param changes
  the number; report states which model ran). Verify: deterministic under fixed seed.
- **T4 [dep: T2,T3]** — `verdict` against the two locked thresholds (≥1 cluster of ≥3; ≥5% fire-rate).
  **Red:** `test_verdict_build_iff_thresholds_clear` (FR-8 — build only when BOTH clear; else defer +
  reason), `test_verdict_defer_or_build_on_todays_bank` (FR-8 — regression-lock today's measured
  verdict + reason). Verify: the exact `{verdict, thresholds, measured, reasons}` shape.
- **T5 [dep: T1,T2]** — `render_report` (fixed-width, mirror `syllabus_coverage_report.render_report`).
  Verify: per-skill coverage table + candidate-cluster list + untagged/integrity foot.
- **T6 [dep: T4,T5]** — `main()` (argparse `--corpus`/`--syllabus`/`--out`; print report; write verdict
  JSON via the `measure_l2l3_goaljudge` pattern). **Red:** `test_probe_is_read_only_deterministic`
  (FR-9 — no writes except verdict JSON; byte-identical on repeat). Verify: run it for real, commit
  `docs/plan/tier1-taxonomy-readiness.verdict.json`.
- **T7 [dep: T6]** — companion `tests/architecture/test_tier1_readiness_probe.py`: verdict-drift lock
  (committed verdict == fresh run) + FR gate re-assertions on the real bank. Mirror
  `test_syllabus_coverage_ratchet.py` structure.
- **T8 [dep: all]** — `make check` green (lint + format-check + pyright + full test); paste output.
  Commit all 3 files. Update spec §9 DoD checkboxes with pasted evidence.

**Critical path:** T1→T2→T3→T4→T6→T7→T8. T5 parallels T3. **FR→task→test matrix:**
FR-1→T1 · FR-2/3/4→T2 · FR-5→T1 · FR-6/7→T3 · FR-8→T4 · FR-9→T6 · drift-lock→T7.

## D. Analyze (Stage 4 — pre-implementation)

- **Spec↔plan↔tasks↔constitution cross-check:** every FR-1…FR-9 maps to a task + a named test
  (matrix above); no invariant violation (stdlib-only `scripts/` tool, no layer crossing); no
  zero-coverage FR.
- **Grounding:** all cited paths verified resolve (bank/syllabus JSON, the 3 precedent files at the
  cited lines, `newest_due_miss.ts` firing join). No new dependency (stdlib only → no `pyproject.toml`
  change → no ADR-ratchet trigger — confirmed the touched paths are `scripts/` + `tests/architecture/`
  + `docs/plan/`, none an ⚠️ Ask-first seam).
- **Baseline before implement:** `make check` + `pytest tests/architecture/ -q` green on the branch.

## E. Definition of Done (from spec §9)

- [ ] `scripts/tier1_taxonomy_readiness.py` implements FR-1…FR-9 (read-only, stdlib, deterministic).
- [ ] `docs/plan/tier1-taxonomy-readiness.verdict.json` committed with today's verdict + thresholds.
- [ ] Every FR test seen to fail first (red→green); output pasted.
- [ ] `make check` green incl. `test_tier1_readiness_probe.py`; `tests/architecture/` green.
- [ ] No ADR (confirmed); decision + thresholds auditable in the verdict JSON.

**Next: sdd-implement** (red/green TDD per task, watch-fail-first, paste output).
