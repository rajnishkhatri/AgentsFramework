# GoalJudge Stage 5 — Phase 6 Assembly Status

> **Run date:** 2026-06-11
> **Sheet input:** [`goaljudge_stage5_goldset_full_sheet.csv`](goaljudge_stage5_goldset_full_sheet.csv) (79 rows, post-adjudication + post-backfill)
> **Manifest (smoke):** [`goldset_v1_manifest_smoke.json`](../../../../cache/goaljudge_eval/goldset_v1_manifest_smoke.json)
> **Status:** **PARTIAL — assembly path validated, production-floor freeze blocked on sourcing volume**

---

## Headline

The Phase 6 infrastructure is fully working — `scripts/assemble_goaljudge_goldset.py`
produces a v1 manifest with a frozen `test_split_sha256`, and every row in the
79-row fresh corpus passes per-row GoldsetItem validation after the schema +
data fixes landed in this session. The production freeze is blocked only on a
**sourcing-volume gap** (D1/D5 floors calibrated for ~250 rows; fresh corpus
alone is 79). This is the expected gate that catches "too small to be a
trustworthy gold-set" before the manifest hashes and freezes.

---

## What changed to get to a working manifest path

Three integration-boundary issues surfaced when the canonical assemble script
ran against the post-Phase-5 sheet. All three were data/schema seams between
Phase 5's outputs and Phase 6's expectations:

### 1. `adjudicated_*` columns blank on agreement rows

* **Symptom:** `row → GoldsetItem failed on item_id='GJ-F-001': adjudicated_goal_met='' is not a recognized truth value`.
* **Root cause:** Phase 5's `apply_adjudication` writes `adjudicated_*` only on
  disagreement rows (per protocol Rule 5). Phase 6's `row_to_goldset_item`
  reads only `adjudicated_*` columns. The 57 agreement rows had no
  per-row final verdict on the column the assembler expected.
* **Fix:** Wrote [`scripts/_phase6_backfill_consensus_to_adjudicated.py`](../../../../scripts/_phase6_backfill_consensus_to_adjudicated.py).
  On agreement rows (where r1_goal_met == r2_goal_met), copies the consensus into
  `adjudicated_goal_met` and picks the failure_mode (prefer A1's iff it's in the
  active vocab, else A2's, else blank). Idempotent — running twice produces the
  same sheet.

### 2. `provenance='fresh-authored'` not in the enum

* **Symptom:** `'fresh-authored' is not a valid GoldsetProvenance`.
* **Root cause:** `GoldsetProvenance` had two values: `production` and `synthetic`.
  The Phase 4 fresh corpus introduced a third stream that's neither — it's
  real agent traces against fresh-authored prompts (not production traffic; not
  stress-fixture synthetic).
* **Fix:** Extended the enum with `FRESH_AUTHORED = "fresh-authored"`.
  Contamination firewall in `_firewall` validator already targets `SYNTHETIC`
  explicitly (line 103), so the new value is allowed in either split — which
  is correct: fresh-authored prompts go through the same admissibility checks
  as production runs. All 103 L1 tests pass.

### 3. Legacy `incomplete-run` failure_mode code

* **Symptom:** `row → GoldsetItem failed on item_id='GJ-F-002': unknown failure_mode 'incomplete-run'`.
* **Root cause:** A1's sheet used `incomplete-run` on 3 rows (GJ-F-002, 005, 098).
  That code was renamed to `incomplete-synthesis` and split out as
  `subtask-dropped` during vocabulary tightening — these 3 entries pre-date the
  tighter vocab. A2's sheet (built after the tightening) used `subtask-dropped`
  on the same 3 rows.
* **Fix:** Patched the 3 `adjudicated_failure_mode` cells to A2's
  `subtask-dropped`; updated the backfill script's tie-break to prefer A2 when
  A1's code is invalid under the current vocab.

After those three landed, every row passes per-row GoldsetItem validation.

---

## Production-freeze run

```bash
.venv/bin/python scripts/assemble_goaljudge_goldset.py \
    --sheet docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
    --manifest cache/goaljudge_eval/goldset_v1_manifest.json \
    --frozen-at 2026-06-11T00:00:00Z \
    --dry-run
```

**Result:**

```
assembly invariant violated: planning_depth floor unmet: cell='L0' count=16 floor=60
```

The fresh corpus has 16 L0-routed rows but the locked D1 floor is 60. The
assembler refuses to freeze a manifest where any cell is undersized. This is
**the expected behavior** — Phase 6 exists in part to prevent shipping a
gold-set that's too small for statistical power on any cell.

The full floor-gap picture (from Phase 5-G's coverage report):

| Dim | Cell | Floor | Have | Gap |
|---|---|---|---|---|
| D1 | L0 | 60 | 16 | **44** |
| D1 | L1 | 100 | 38 | **62** |
| D1 | L2 | 60 | 25 | **35** |
| D5 | file-only | 25 | 14 | 11 |
| D5 | shell-bound | 30 | 11 | 19 |
| D5 | web-bound | 25 | 8 | 17 |
| D5 | no-tool | 15 | 7 | 8 |
| D5 | compose | 40 | 25 | 15 |
| D5 | wrong-tool | 20 | 6 | 14 |
| D5 | blocked-tool | 15 | 4 | 11 |
| D5 | request_approval | 10 | 4 | 6 |

Total: **141 more rows needed across D1** + **101 more across D5** to clear the floors.

---

## Smoke-floor run (validates the manifest path end-to-end)

To confirm the assembly path itself works, ran with `--skip-cell-coverage`:

```bash
.venv/bin/python scripts/assemble_goaljudge_goldset.py \
    --sheet docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
    --manifest cache/goaljudge_eval/goldset_v1_manifest_smoke.json \
    --frozen-at 2026-06-11T00:00:00Z \
    --dry-run \
    --skip-cell-coverage
```

**Result:**

```
upserted 79 item(s) into goaljudge_goldset_v1 (dry_run=True)
wrote manifest (15 keys) to cache/goaljudge_eval/goldset_v1_manifest_smoke.json
```

### Smoke manifest summary

| Field | Value |
|---|---|
| `total_items` | 79 |
| `test_count` | 79 |
| `dev_count` | 0 |
| `goal_met_false_share` | **0.823** (≥ 0.60 spec §4 minimum) |
| `stratum_distribution` | representative=32, boundary=23, edge=16, impossible=8 |
| `planning_depth_distribution` | L0=16, L1=38, L2=25 |
| `tool_cluster_distribution` | all 8 clusters present, lowest at 4 (blocked-tool, request_approval) |
| `failure_mode_distribution` | 14 codes present (of 16 active) |
| `test_split_sha256` | `99b5bcab583621943366a1771afd096e53adcd29f99fd0549beb69bd5706a5ca` |

This is **what the production manifest will look like** once the floors close.
The hash is reproducible — running the smoke command again produces the same
SHA. That hash is what Stage 6 will record at calibration time and re-verify
at eval time.

---

## What this means

The Phase 6 infrastructure is **production-ready**. The fresh-corpus stream
itself is too small to support a frozen v1 manifest on its own — by design.
The Tier 3 plan always assumed multiple sourcing streams: pilot (22 rows,
already labeled), fresh (79 rows, this session), and future production sampling.

Three paths forward from here:

### Path A — Merge fresh + pilot, re-measure

The pilot 22 rows live in [`goaljudge_stage5_goldset_pilot_sheet.csv`](goaljudge_stage5_goldset_pilot_sheet.csv).
Combined: 101 rows. Still short of floors, but a measurable step. Worth
running to see which cells close.

### Path B — Author fresh wave 2 against the gap

Phase 4 authoring brief targeting:
* +44 L0 rows (heavy on `no-tool` + `request_approval` clusters which are the
  L0-natural cells)
* +62 L1 rows (file-only + shell-bound + web-bound to close those clusters)
* +35 L2 rows (compose + wrong-tool + blocked-tool)

That's ~141 additional fresh-authored prompts, mostly in cells that are
natural for the fresh-task corpus shape. Then a re-run through Phase 4 →
Phase 5 → Phase 6.

### Path C — Use the smoke manifest as a development gate for Stage 6

The smoke manifest with `--skip-cell-coverage` is a valid v1 artifact for
**Stage 6 development**: writes the same fields, computes the same hash, has
the same item count and false-share. Stage 6 can be built against it
provisionally; the final production freeze waits for floors to close.

---

## Recommendation

Path A first — it's a 30-minute measurement that tells us *how much* of the
gap the pilot stream actually closes. The answer determines whether Path B
(author more) or Path C (ship as smoke + Stage 6 dev) is the right next move.

---

## Artifacts produced this run

| File | Purpose |
|---|---|
| `cache/goaljudge_eval/goldset_v1_manifest_smoke.json` | Smoke manifest — validates assembly path; 79 items, reproducible hash |
| `scripts/_phase6_backfill_consensus_to_adjudicated.py` | Pre-step: backfill `adjudicated_*` from r1/r2 consensus on agreement rows |
| `services/governance/goaljudge_goldset_dataset.py` | Extended `GoldsetProvenance` enum with `FRESH_AUTHORED` |
| `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv` | Sheet now has `adjudicated_*` filled on all 79 rows; 3 legacy `incomplete-run` codes remapped to `subtask-dropped` |
| This document | Phase 6-A status |

## Regression

```
.venv/bin/python -m pytest tests/services/test_goaljudge_goldset_dataset.py -q
103 passed in 0.42s
```
