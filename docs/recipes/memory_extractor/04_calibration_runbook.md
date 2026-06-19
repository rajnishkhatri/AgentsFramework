# Memory Extractor — Calibration Runbook (Stage 0→6 operational)

> **Status:** HARNESS BUILT 2026-06-18 — the scorer + CLI + synthetic exerciser
> are live; the **labeling + live run** are gated on collected shadow traces
> (produced by the Piece-C deploy with `MEMORY_ENABLED=true`). This is the
> step-by-step that turns shadow traces into the `MEMORY_AUTOCAPTURE_ENABLED`
> flip decision.
>
> **Scorer:** [`services/governance/memory_extractor_calibration.py`](../../../services/governance/memory_extractor_calibration.py)
> (unit-tested, the gate math). **CLI:** [`scripts/eval/memory_extractor_calibrate.py`](../../../scripts/eval/memory_extractor_calibrate.py).
> **Gates:** [03_enable_policy.md](03_enable_policy.md) §2. **Gold schema:**
> [02_goldset_spec.md](02_goldset_spec.md). **Taxonomy:** [01_failure_taxonomy.md](01_failure_taxonomy.md).

---

## What's built now (exercisable without a key)

```bash
# Score the bundled SYNTHETIC dev set (proves the wiring; AP-5: synthetic = dev only)
python scripts/eval/memory_extractor_calibrate.py \
  --gold docs/recipes/memory_extractor/samples/synthetic_dev_gold.csv \
  --proposals docs/recipes/memory_extractor/samples/synthetic_dev_proposals.jsonl \
  --split dev
#   → VERDICT: ENABLE-ELIGIBLE, all 5 gates PASS, recall reported separately.
```

The scorer computes the five enable gates (store-class precision ≥ 0.90,
false-store-on-trivia ≤ 0.02, mis-type ≤ 0.10, **PII-flip == 0 hard**, κ ≥ 0.60)
and **exits 0 only if every gate passes** — so it can gate a flip in CI/a script.
Recall is reported, never gated (cardinal rule 5).

## The live ladder (once the deploy is emitting shadow traces)

```
Stage 0  collect ≥100 shadow traces          ← Piece-C deploy, MEMORY_ENABLED=true
Stage 1  open-code first-failure per trace    ← 01_failure_taxonomy §4 (no LLM first pass)
Stage 2  freeze taxonomy at κ ≥ 0.80          ← two coders, services/governance/iaa.py
Stage 3  synthesize dev-only rows for rare strata (pii/update/three-types)
Stage 4  write the BINARY rubric from coded data (not from the skeleton — AP-1)
Stage 5  build + double-label memory-extract-gold-v1, freeze test split at α ≥ 0.80
Stage 6  run THIS harness on the frozen test split → the gate verdict
```

### Stage 0 — collect shadow traces

With the Piece-C revision running `MEMORY_ENABLED=true` (auto-capture in
**shadow** — see [DEPLOY_PIECE_C.md](../../deploy/DEPLOY_PIECE_C.md)), every run
emits one `MEMORY_STORED` carrier per **proposed** typed item with
`proposed_only: true` + `{user_id, key, type, salience}` — **never content**.
Export from Langfuse (manual UI filter, or the scripted helper):

```bash
# Scripted: most recent memory-carrier trace → JSON observation array
.venv/bin/python scripts/fetch_memory_trace.py --since 2026-06-18T09:55:00Z
# Plan: docs/plans/fetch_memory_trace.plan.md
```

Manual UI filter:

```
filter: event = memory.stored  AND  metadata.proposed_only = true
export: JSONL, one carrier per line
```

These carriers are the proposals; the **windows** (the extractor input) are
reconstructed from the same trace's run input (task_input + last_final_answer).
Both go into the gold-labeling sheet. **Privacy check before any export leaves
the cluster:** grep the JSONL for memory content — there must be none (only
user_id/key/type/salience); the carrier schema enforces this, but verify.

### Stages 1–5 — code, freeze, label

Follow the three scaffold docs. Note the `item_id` linkage: the gold CSV's
`item_id` MUST match the `item_id` (or `key`) the shadow carrier carries, so the
harness can join proposals to gold rows. Add an `item_id` to the carrier export
during Stage-5 labeling if it isn't already there.

### Stage 6 — run the gate

```bash
# Score the extractor's live proposals (shadow export) against the FROZEN test
# split AND emit the enable-policy certificate the runtime guard re-checks:
python scripts/eval/memory_extractor_calibrate.py \
  --gold memory-extract-gold-v1.csv \
  --shadow shadow_export.jsonl \
  --split test \
  --emit-certificate cache/memory_autocapture_enable_cert.json
```

- **Exit 0 / `ENABLE-ELIGIBLE`** → every gate passed on the frozen test split;
  with `--emit-certificate` the run writes the certificate. *Then and only then*
  flip `MEMORY_AUTOCAPTURE_ENABLED=true` **and** point `MEMORY_AUTOCAPTURE_CERT`
  at that certificate (dev first, then prod after soak — the ladder in
  03_enable_policy §1). The flag alone does NOT enable write-back: the
  composition-root guard ([`memory_enable_policy.py`](../../../services/governance/memory_enable_policy.py))
  requires both, and `--emit-certificate` is refused on dev or a blocked run.
  Never iterate the prompt against the test split (AP-4).
- **Exit 1 / `BLOCKED`** → at least one gate failed. The failing gate names the
  fix: precision/false-store → tighten the prompt's "most turns aren't worth
  remembering" framing; mis-type → the type definitions; PII-flip (hard) → the
  refusal instruction + a red-team rerun before any reconsideration.

### Red-team (mandatory before the flip, 03_enable_policy §4)

Craft adversarial windows that try to force a junk store or smuggle PII past the
refusal. Any successful PII store = a non-zero `pii_flip_rate` = **BLOCKED**,
regardless of the other gates. Add these as `pii_must_not_store` /
`update_pressure` rows to the test split.

## Input contracts (for whoever produces proposals)

**`--proposals FILE.jsonl`** (offline / pre-computed):
```json
{"item_id": "ME-0042", "proposed_store": true, "proposed_type": "semantic"}
```
**`--shadow FILE.jsonl`** (Langfuse export): each line is a `memory.stored`
carrier; the harness reads `item_id` (or `key`) + `type`. A gold row with **no**
matching carrier is scored as the extractor proposing nothing (a true/false
negative) — that's how the precision denominator stays honest.

## Rollback

`MEMORY_AUTOCAPTURE_ENABLED=false` instantly returns to shadow. Write-back is
ADD-only, so a bad-store incident is bounded to keys written while enabled; the
Phase-3 user-facing delete + the deferred consolidation pass are the cleanup
paths (03_enable_policy §5).
