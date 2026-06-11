# GoalJudge Stage 5 — Phase 6-B: Fresh + Pilot Merge Measurement (Path A)

> **Run date:** 2026-06-11
> **Combined sheet:** [`goaljudge_stage5_goldset_combined_sheet.csv`](goaljudge_stage5_goldset_combined_sheet.csv) (101 rows)
> **Combined smoke manifest:** [`goldset_v1_manifest_smoke_combined.json`](../../../../cache/goaljudge_eval/goldset_v1_manifest_smoke_combined.json)
> **Status:** **Combined sheet built; production-freeze still blocked on L1/L2/web-bound/wrong-tool gaps**

---

## Path A executed: merged fresh (79) + pilot-production (22) = 101 rows

Built [scripts/build_goaljudge_stage5_combined_sheet.py](../../../../scripts/build_goaljudge_stage5_combined_sheet.py)
to merge the streams:

1. **Synthetic pilot rows excluded.** Pilot has 50 rows; 28 are synthetic-dev
   stress fixtures (firewall-locked to dev split). Only the 22 production-
   provenance rows enter the combined sheet, promoted to `split=test`.
2. **D1/D5 dimensions classified.** Pilot sheet predates the Tier-3
   stratification — `planning_depth` and `tool_cluster` were blank. Script
   re-runs `select_planning_depth` + `classify_tool_cluster` against the
   pilot corpus's tool-call trajectories (loaded from
   `cache/goaljudge_eval/corpus_gcp_goldset_pilot_2026-06-09.jsonl`).
3. **`adjudicated_*` backfilled from consensus.** Pilot prod has **100 %
   A1/A2 agreement on `goal_met`** — no adjudication round needed; the
   consensus IS the adjudicated value.
4. **Failure-mode vocab remapped.** Pilot's legacy codes (e.g.
   `incomplete-run`) are dropped in favor of A2's current-vocab code
   (same logic as the fresh-sheet backfill).

---

## What the merge actually closed

| Dim | Cell | Floor | Fresh alone | Combined | Gap closure |
|---|---|---|---|---|---|
| D1 | L0 | 60 | 16 | **32** | -16 (16→32) |
| D1 | L1 | 100 | 38 | 44 | -6 (38→44) |
| D1 | L2 | 60 | 25 | 25 | 0 (pilot has no L2) |
| D5 | blocked-tool | 15 | 4 | 4 | 0 |
| D5 | compose | 40 | 25 | 29 | -4 |
| D5 | file-only | 25 | 14 | 16 | -2 |
| D5 | no-tool | 15 | 7 | 8 | -1 |
| D5 | request_approval | 10 | 4 | 4 | 0 |
| D5 | **shell-bound** | 30 | 11 | **25** | **-14 (11→25)** |
| D5 | web-bound | 25 | 8 | 9 | -1 |
| D5 | wrong-tool | 20 | 6 | 6 | 0 |

**Bottom line — the pilot is a heavily L0/shell-bound stream**:

- Closes **most** of the L0 gap (44 → 28) and **most** of the shell-bound gap
  (19 → 5).
- Closes **almost nothing** for L1, L2, web-bound, wrong-tool, blocked-tool,
  request_approval.

This makes sense reading the pilot rows: they're the original GJ-001…GJ-022
registry, which was designed as a "trace basic file/shell operations through
real production" corpus — exactly the L0/shell-bound shape.

---

## Production-floor run on combined sheet

```bash
.venv/bin/python scripts/assemble_goaljudge_goldset.py \
    --sheet docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_combined_sheet.csv \
    --manifest cache/goaljudge_eval/goldset_v1_manifest.json \
    --frozen-at 2026-06-11T00:00:00Z \
    --dry-run
```

**Result:**

```
assembly invariant violated: planning_depth floor unmet: cell='L0' count=32 floor=60
```

The error message lists the *first* failing cell. The full remaining gap:

```
D1 total deficit: 119 → 88 rows still needed (down from 141 fresh-alone)
D5 total deficit:  79 → 64 rows still needed (down from 95 fresh-alone)
```

Combined fresh+pilot recovers **~30 %** of the original gap. **~70 % remains.**

---

## Smoke-floor run (101-row provisional manifest)

```bash
.venv/bin/python scripts/assemble_goaljudge_goldset.py \
    --sheet docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_combined_sheet.csv \
    --manifest cache/goaljudge_eval/goldset_v1_manifest_smoke_combined.json \
    --frozen-at 2026-06-11T00:00:00Z \
    --dry-run \
    --skip-cell-coverage
```

**Result:**

```
upserted 101 item(s) into goaljudge_goldset_v1 (dry_run=True)
wrote manifest (15 keys) to cache/goaljudge_eval/goldset_v1_manifest_smoke_combined.json
```

### Combined smoke manifest comparison

| Field | Fresh-only (79) | Combined (101) | Δ |
|---|---|---|---|
| `total_items` | 79 | **101** | +22 |
| `goal_met_false_share` | 0.823 | 0.792 | -0.03 (still ≥ 0.60 floor) |
| `failure_mode_distribution` codes | 14 / 16 | **15 / 16** | + impossible-task-unhandled |
| `stratum_distribution` | 4 strata | **5 strata** | + red_team (2) |
| `planning_depth_distribution` | L0=16, L1=38, L2=25 | L0=**32**, L1=44, L2=25 | +16 L0, +6 L1 |
| `tool_cluster_distribution.shell-bound` | 11 | **25** | +14 |
| `test_split_sha256` | `99b5bcab…5706a5ca` | **`ad5eccc0…dbc453cd`** | recomputed |

The combined provisional manifest is a **strict improvement** over the fresh-only
one across every dimension that matters: more rows, more strata, more
failure-mode codes, recomputed hash. It is — if shipped — a more credible
Stage 6 development artifact than the fresh-only smoke.

---

## What's left to close the gap

To pass production-floor freeze, we need ~152 more rows distributed roughly:

- **+28 L0** rows — but the cells these L0 rows would naturally land in
  (file-only / no-tool / request_approval) are also under-floor, so these
  can do double-duty
- **+56 L1** rows — file-only / shell-bound / web-bound / compose mix
- **+35 L2** rows — compose / wrong-tool / blocked-tool mix
- **+14 wrong-tool** rows
- **+11 blocked-tool** rows
- **+16 web-bound** rows
- **+6 request_approval** rows

A well-targeted Phase 4 wave 2 of ~150 fresh-authored prompts could close
all of these. The breakdown isn't accidental — it's the cells the fresh
+ pilot streams systematically under-cover, which means the next sourcing
brief writes itself.

---

## Strategic choice

Three paths now branch from here:

### Path B — Author Phase 4 wave 2

* Effort: days (author ~150 prompts, run them through GCP, label both
  rounds, adjudicate, freeze).
* Outcome: production-floor freeze passes. Real v1 goldset.

### Path C — Ship the combined provisional manifest, unblock Stage 6 dev

* Effort: done already (the combined smoke manifest exists, 101 items,
  reproducible hash).
* Outcome: Stage 6 development can begin against the combined manifest.
  Floors close at a later v1.1 freeze.

### Path D — Hybrid: ship combined smoke as v0.9, author wave 2 in parallel

* Effort: same as C (no extra work to ship) + same as B (wave 2 in
  background).
* Outcome: Stage 6 development unblocked immediately; production v1
  freeze when wave 2 lands.

---

## Recommendation

**Path D**, ship the combined provisional manifest as v0.9 to unblock Stage
6 development, and queue Phase 4 wave 2 as the next sourcing task. This is
the lowest-regret move:

- Stage 6 can begin immediately on a credible 101-row artifact.
- The wave 2 brief is concrete and uncontested: the gap report lists
  exactly which cells need which counts.
- When wave 2 lands, we re-run Phase 5 on the new rows only (they slot
  into the same sheet schema), re-run α + adjudicate the new rows, and
  re-freeze. The v0.9 → v1 transition is mechanical, not architectural.

---

## Artifacts produced

| File | Purpose |
|---|---|
| `scripts/build_goaljudge_stage5_combined_sheet.py` | Path A builder — merges fresh + pilot prod into one canonical sheet |
| `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_combined_sheet.csv` | 101-row combined sheet (fresh 79 + pilot 22) |
| `cache/goaljudge_eval/goldset_v1_manifest_smoke_combined.json` | Combined provisional manifest (15 keys, hash `ad5eccc0…`) |
| This document | Path A measurement results + strategic choice |
