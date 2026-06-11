# GoalJudge Stage 5 — Gold-set v0.9 (Provisional) Contract

> **What this is.** The contract between Stage 6 (calibration + evaluation
> infrastructure) and the **v0.9 provisional gold-set artifact**. Stage 6
> begins development against v0.9 *now*; v1 freezes once Phase 4 wave 2
> labels land and every D1/D5 cell meets its floor.
>
> **Frozen at:** 2026-06-11T00:00:00Z
> **Manifest:** [`cache/goaljudge_eval/goldset_v0_9_manifest.json`](../../../../cache/goaljudge_eval/goldset_v0_9_manifest.json)
> **Sheet:** [`goaljudge_stage5_goldset_combined_sheet.csv`](goaljudge_stage5_goldset_combined_sheet.csv)
> **Hash:** `ad5eccc0abd857986e40c6b098e67448a309bd72e7fc1083b8b31db8dbc453cd`
> **Status:** **PROVISIONAL — blessed for Stage 6 development only.**

---

## Headline

v0.9 is a **strict subset** of what v1 will be: 101 of an eventual ~250 labeled
rows, with the same schema, same firewall, same hash invariant, same per-row
GoldsetItem validation. The only thing it lacks is **statistical power on
under-sized cells**. Stage 6 code that doesn't depend on per-cell power can —
and should — be developed against v0.9 today. Stage 6 code that *does* depend
on per-cell power is gated by `gate_goldset_v1_floors()` and turns on at v1.

The hash IS the freeze: a v0.9 → v1 cutover is a hash change. Stage 6 caches
keyed by `(path, sha256)` invalidate cleanly across the transition.

---

## What v0.9 contains

| Field | v0.9 value | Notes |
|---|---|---|
| `total_items` | 101 | 79 fresh + 22 pilot-production |
| `test_count` | 101 | All rows promoted to test split for the freeze |
| `dev_count` | 0 | Synthetic-dev pilot rows excluded by firewall |
| `goal_met_false_share` | 0.792 | ≥ 0.60 floor (spec §4) |
| `stratum_distribution` | 5 strata | representative=39, boundary=29, edge=22, impossible=9, red_team=2 |
| `planning_depth_distribution` | L0=32, L1=44, L2=25 | All three D1 cells present |
| `tool_cluster_distribution` | 8 clusters | Every D5 cluster has ≥ 4 rows |
| `failure_mode_distribution` | 15 / 16 codes | Missing: tool-error-misread (1 row), goal-met-but-unsafe-wasteful (1 row); 13 codes with ≥ 3 occurrences |
| `provisional` | `true` | Distinguishes v0.9 from v1 |
| `floor_gap_summary` | 11 entries | Per-cell gaps still to close |

### Floor gap summary (what's still under floor)

| Dim | Cell | Floor | Have | Gap |
|---|---|---|---|---|
| D1 | L0 | 60 | 32 | **28** |
| D1 | L1 | 100 | 44 | **56** |
| D1 | L2 | 60 | 25 | **35** |
| D5 | file-only | 25 | 16 | 9 |
| D5 | shell-bound | 30 | 25 | 5 |
| D5 | web-bound | 25 | 9 | 16 |
| D5 | no-tool | 15 | 8 | 7 |
| D5 | compose | 40 | 29 | 11 |
| D5 | wrong-tool | 20 | 6 | 14 |
| D5 | blocked-tool | 15 | 4 | 11 |
| D5 | request_approval | 10 | 4 | 6 |

These are the cells Phase 4 wave 2 targets.

---

## What Stage 6 **CAN** do against v0.9

These operations are correct against v0.9 and v1 alike; the gap doesn't matter.

* **Load the manifest** via the standard reader. `total_items`, `test_count`,
  `dev_count`, `frozen_at`, `rubric_version`, `dataset_name`, `test_split_sha256`
  are all canonical.
* **Verify the hash.** `compute_test_split_hash` recomputed against the
  combined sheet produces `ad5eccc0…dbc453cd`. The same recomputation should
  fire on every Stage 6 run.
* **Iterate items** (101 rows). Each one is a fully-validated `GoldsetItem`
  (firewall enforced, failure-mode-vocabulary enforced, `goal_met`
  canonical).
* **Run the rubric on every item.** GoalJudge can score every v0.9 row.
* **Compute per-failure-mode error counts** (15 of 16 codes are present).
* **Sanity-check the dev/test firewall** — v0.9 has 0 dev rows (the firewall
  permits SYNTHETIC ⇒ dev only; v0.9 has no synthetic).
* **Develop, test, and ship hash-verification, manifest-loader, item-iterator,
  per-item-evaluator, telemetry, error-aggregation pipelines.** All of these
  are floor-independent.

## What Stage 6 **CANNOT** do against v0.9

These operations need statistical power Stage 6 doesn't yet have.

* **Publish per-cell binomial confidence intervals.** Cells with 4 rows
  produce useless CIs (e.g. ±25% margin).
* **Calibrate gates on per-cell precision/recall.** Floors are sized so v1
  has ≥ 15 rows per cell — enough for ±15% CI. v0.9 doesn't.
* **Claim "this is the v1 frozen gold-set."** It isn't. It's v0.9.
* **Run `gate_goldset_v1_floors()` and expect PASS.** The gate fails-closed
  on `provisional=true` by design. Any Stage 6 code that depends on a v1
  artifact must call this gate; against v0.9 it raises
  `AssemblyInvariantError`.

---

## The gate API

```python
from services.governance.goaljudge_goldset_dataset import (
    gate_goldset_v1_floors, AssemblyInvariantError,
)

# Stage 6 calibration entry point:
try:
    gate_goldset_v1_floors(manifest)
except AssemblyInvariantError as exc:
    raise RuntimeError(
        f"refusing to calibrate against a non-v1 manifest: {exc}"
    ) from exc
# … proceed with per-cell power-dependent calibration …
```

Call the gate only from code paths that depend on per-cell power. Code paths
that don't depend on it should run against v0.9 directly — no gate, no
checking.

---

## v0.9 → v1 transition criteria

All of the following must hold for v1 freeze:

1. **Sheet has ≥ 250 rows.** Phase 4 wave 2 sources ~150 additional fresh
   prompts targeting the gap cells.
2. **All wave-2 rows blind-labeled by A1 + A2** following the same protocol
   (including the post-round-1 Rule 7 + request_approval clauses).
3. **α on wave 2 rows alone ≥ 0.8.** Sanity check; v1 doesn't recompute α on
   the full 250-row set because the original 101 rows are already frozen.
4. **Wave-2 disagreements adjudicated.**
5. **Combined sheet (251+ rows) passes assembler with the default flags** —
   no `--provisional`, no `--skip-cell-coverage`. The cell-coverage invariant
   produces no violations.
6. **Manifest emerges as `provisional=false`, `floor_gap_summary={}`.**
7. **Gate passes:** `gate_goldset_v1_floors(manifest)` returns `None`.

When all 7 hold, the manifest is renamed `goldset_v1_manifest.json` and
Stage 6's gate-protected code paths light up automatically. Stage 6 caches
keyed by `(path, sha256)` invalidate because both fields change.

---

## What does NOT change at the v0.9 → v1 transition

These are stable invariants — Stage 6 code that uses them works against both
versions.

* **Manifest schema** (key set, types, value shapes).
* **GoldsetItem pydantic model** (fields, firewall, validation rules).
* **`compute_test_split_hash` algorithm.** A v1 hash *value* differs from
  v0.9's, but the recomputation procedure is identical.
* **`gate_goldset_v1_floors` semantics.** Same function, same failure modes,
  same idempotence.
* **Failure-mode vocabulary.** v1 may add the two currently-absent codes
  (`tool-error-misread`, `goal-met-but-unsafe-wasteful`) at higher
  occurrence counts, but the vocabulary is fixed.

---

## Stage 6 development checklist (v0.9 era)

1. [ ] Manifest loader reads `goldset_v0_9_manifest.json` and verifies hash.
2. [ ] Per-item evaluator iterates 101 items, scores each.
3. [ ] Telemetry pipeline records per-item GoalJudge output.
4. [ ] Failure-mode aggregator counts codes across the 15 present.
5. [ ] Calibration entry point gates on `gate_goldset_v1_floors()` — raises
       against v0.9, lets v1 through.
6. [ ] Cache invalidation verified via `(path, sha256)` key.

The first 4 items can land against v0.9 alone. Item 5 is gated for v1 —
the test for it can be written against a mock-v1 manifest fixture today.
Item 6 is verified at v1 cutover via the cutover protocol.

---

## Cutover protocol (executed at v1 freeze)

> **Note:** This procedure runs at the moment of v0.9 → v1 transition. It's
> not part of v0.9 itself, but documented here so Stage 6 has the exact
> shape of the transition in writing.

1. Wave 2 freeze runs `scripts/assemble_goaljudge_goldset.py` against the
   wave-2-extended sheet with the default flags (no `--provisional`,
   no `--skip-cell-coverage`). The script either succeeds or raises
   `AssemblyInvariantError`.
2. On success, rename the manifest output from
   `goldset_v0_9_manifest.json` → `goldset_v1_manifest.json`. Keep the v0.9
   file for two weeks in case rollback is needed.
3. Re-run Stage 6's full eval pipeline against the v1 manifest. The
   `gate_goldset_v1_floors()` invariant now PASSES; previously-inert
   v1-only code paths fire.
4. Verify cache invalidation: any Stage 6 cache keyed by v0.9's hash
   must report a miss on v1.
5. Update the README banner to v1 status; archive this contract doc.

---

## Artifacts

| File | Purpose |
|---|---|
| [`goaljudge_stage5_goldset_combined_sheet.csv`](goaljudge_stage5_goldset_combined_sheet.csv) | 101-row v0.9 source sheet |
| [`../../../../cache/goaljudge_eval/goldset_v0_9_manifest.json`](../../../../cache/goaljudge_eval/goldset_v0_9_manifest.json) | The v0.9 manifest |
| [`../../../../scripts/assemble_goaljudge_goldset.py`](../../../../scripts/assemble_goaljudge_goldset.py) | Assembler — supports `--provisional` |
| [`../../../../services/governance/goaljudge_goldset_dataset.py`](../../../../services/governance/goaljudge_goldset_dataset.py) | `gate_goldset_v1_floors()` + `build_goldset_manifest()` |
| [`goaljudge_stage5_phase6b_combined_measurement.md`](goaljudge_stage5_phase6b_combined_measurement.md) | How the 101-row v0.9 set was assembled |

## Regression

```
.venv/bin/python -m pytest tests/services/test_goaljudge_goldset_dataset.py tests/scripts/test_assemble_goaljudge_goldset.py -q
117 passed in 1.15s
```

9 new L1 tests + 2 new L2 tests cover `gate_goldset_v1_floors`, the
manifest builder's `provisional` + `floor_gap_summary` keys, and the
assembler CLI's `--provisional` flag.
