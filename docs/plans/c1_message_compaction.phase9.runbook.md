---
type: runbook
title: 'C1 — Phase 9 live-validation runbook'
description: 'Tagged --no-traffic Cloud Run rev + planning-stress run + analyzer assert. Operator-driven, never automated.'
tags: [runbook, compaction, c1, phase-9, gcp]
---

# C1 — Phase 9 live-validation runbook

> **Status.** Companion to [`c1_message_compaction.impl.md`](c1_message_compaction.impl.md) §11.
> **Phase 9 is on-request and operator-driven.** This doc is the exact command list — it is not
> executed by an agent. Read top-to-bottom before running anything.
>
> **Bars (impl.md §11):** tokens-per-run drops materially on folded traces; prompt-cache
> hit-rate does not collapse; **zero pinned-constraint loss.** This runbook resolves those to
> concrete numbers (≥20% / ±2pp / 0 unsafe folds) — sanity-floor only; the first N real
> folded traces inform the gold-set later (design §8.4–§8.5).
>
> **Invariant:** *prod traffic is untouched.* The tagged revision serves on its own URL with
> `--no-traffic`; the LATEST tag stays on the current prod revision. Two checkpoints below
> verify this before and after.

---

## 0. Pre-flight

```bash
# 0a. Confirm you have the right project + region (matches infra/gcp/cloud-run-backend.tf)
gcloud config get-value project
gcloud config get-value run/region

# 0b. Read current prod state: this is the revision we MUST NOT touch
gcloud run services describe agent-backend-combined \
    --region=us-central1 \
    --format='value(spec.traffic[].revisionName, spec.traffic[].percent)'

# 0c. Confirm the current image tag (we deploy the SAME image with new env vars)
PROD_IMAGE=$(gcloud run services describe agent-backend-combined \
    --region=us-central1 \
    --format='value(spec.template.spec.containers[0].image)')
echo "PROD_IMAGE=${PROD_IMAGE}"

# 0d. Confirm Phase 8 code is on the deployed image (the wire we are validating
# must actually be in the binary — a stale image silently invalidates the run).
# Look for the §5.1 evaluate_node block:
gcloud run services describe agent-backend-combined --region=us-central1 \
    --format='value(spec.template.metadata.annotations."run.googleapis.com/git-sha")'
# Or: pull the image locally and `grep collect_compaction_l1` orchestration/react_loop.py
```

If `PROD_IMAGE` does not contain Phase 1–8, **stop**: deploy a fresh image first via the
normal build pipeline. Do not enable compaction on a stale binary.

## 1. Deploy the tagged --no-traffic revision

The 8 `CONTEXT_*` knobs are NOT in `infra/gcp/cloud-run-backend.tf` (deploy-gcp-stress-revision
pattern). They are passed inline at `gcloud run deploy` time, scoped to this tag.

```bash
gcloud run deploy agent-backend-combined \
    --region=us-central1 \
    --image="${PROD_IMAGE}" \
    --tag=c1-compact \
    --no-traffic \
    --update-env-vars="\
CONTEXT_COMPACT_MESSAGES=true,\
CONTEXT_COMPACT_TRIGGER_FRACTION=0.6,\
CONTEXT_OBSERVATION_CLEAR_FRACTION=0.3,\
CONTEXT_KEEP_LAST_K=10,\
CONTEXT_MASK_AFTER_STEPS=10,\
CONTEXT_COMPACT_COOLDOWN_STEPS=5,\
CONTEXT_CONSTRAINT_REINJECT_TURNS=0,\
CONTEXT_COMPACTION_FIDELITY_SAMPLE_RATE=1.0"
```

Defaults retained on purpose:
- `CONTEXT_COMPACT_TRIGGER_FRACTION=0.6` — fold at 60% of model window (default).
- `CONTEXT_CONSTRAINT_REINJECT_TURNS=0` — DEFAULT-OFF persisted tail floor (design §0).
- `CONTEXT_COMPACTION_FIDELITY_SAMPLE_RATE=1.0` — every fold emits the L2 telemetry record
  (Phase 9 wants every fold sampled to validate the wire, not a fraction).

Capture the tag URL:

```bash
TAG_URL=$(gcloud run services describe agent-backend-combined \
    --region=us-central1 \
    --format='value(status.traffic[?tag=c1-compact].url)')
echo "TAG_URL=${TAG_URL}"
```

### Checkpoint #1 — prod is untouched

```bash
# The LATEST tag MUST still point to the pre-deploy revision (prod is on LATEST).
gcloud run services describe agent-backend-combined --region=us-central1 \
    --format='value(spec.traffic[].revisionName, spec.traffic[].percent, spec.traffic[].tag)'
# Expect: 100% traffic on the SAME revisionName captured in step 0b.
# The new revision has tag=c1-compact and percent=0.
```

**If 100% traffic shifted to the new revision, ROLLBACK IMMEDIATELY (§5).**

## 2. Drive the corpus through the tag URL

The C1 stress corpus is `compaction`-phase rows in
`frontend/e2e/fixtures/planning_stress_corpus.json` (4 cases, ids `COMPACTION-*`).

```bash
# From frontend/
cd frontend

# E2E_BYPASS_AUTH=1 only if you do not have WorkOS creds in repo-root .env.
BASE_URL="${TAG_URL}" \
TEST_PROFILE=stress \
STRESS_PHASE=compaction \
STRESS_JSONL="../cache/planning_stress_phase9/ui_batch.jsonl" \
pnpm test:e2e -- frontend/e2e/full-stack/planning-stress.spec.ts
```

This runs the 4 compaction rows. Each row drives a multi-turn pinned-constraint task into
the tagged revision. The bridge per-run `freshTraceId` is what keeps each run a distinct
Langfuse trace (see the `stress-harness-traceid-superposition` fix). Outputs:

- `cache/planning_stress_phase9/ui_batch.jsonl` — one row per case
- `cache/planning_stress_phase9/screenshots/*.png` — evidence

If any case errors with a 5xx, check Cloud Run logs for that revision:

```bash
gcloud run revisions list --service=agent-backend-combined --region=us-central1 \
    --filter="metadata.labels.serving.knative.dev/configurationGeneration~c1-compact" \
    --format='value(metadata.name)' | head -1 | xargs -I{} \
    gcloud logging read "resource.labels.revision_name={}" --limit=50 --format=json
```

## 3. Score the results

```bash
# From repo root. The analyzer is unchanged in shape — it reads ui_batch.jsonl
# and the deployed Langfuse traces, then prints per-phase metrics.
.venv/bin/python scripts/analyze_planning_traces.py \
    --source=langfuse \
    --jsonl=cache/planning_stress_phase9/ui_batch.jsonl \
    --gate
```

The analyzer's `compaction` block reports:

- `folded` — cases that emitted ≥1 `CONTEXT_COMPACTED` carrier
- `mean_drop_ratio` — mean of `1 - tokens_after_last_fold / tokens_before_first_fold`
  across the folded subset
- `unsafe_folds_total` — count of carriers with `floor_exceeded=True` (the §B2-R bar)
- `unsafe_fold_rows` — which cases (an empty list is the green path)

### Gate bars (`--gate`)

| Bar | Threshold | Rule |
| --- | --- | --- |
| `unsafe_folds_total` | `== 0` | **INVIOLABLE.** Any `floor_exceeded=True` fold is a hard fail (§B2-R) |
| `mean_drop_ratio` | `≥ 0.20` over the folded subset | Sanity-floor only; if `folded == 0`, this bar is not checked |
| prompt-cache hit-rate | `±2pp` of a pre-deploy baseline | Read separately from the Langfuse cost panel (§4) |

A `folded == 0` run is **not a green light** — it means no row crossed the trigger on this
model window. Either:
1. Increase the corpus density (more distraction tokens per turn), or
2. Lower `CONTEXT_COMPACT_TRIGGER_FRACTION` to 0.5 for the validation run.

## 4. Prompt-cache hit-rate check (manual)

The analyzer does not score this — it is a provider-side signal. Open the Langfuse project
dashboard, filter by the `c1-compact` tag revision, and compare the **input cache hit rate**
column with a 1-hour pre-deploy baseline window. The §B1-R bar is "doesn't collapse" — a
2-percentage-point drop is acceptable; a 20pp drop indicates the fold broke prefix-cache
alignment and Phase 9 is a soft fail (re-tune `keep_last_k` or `observation_clear_fraction`).

## 5. Rollback / cleanup

Phase 9 ends when the analyzer reports `GATE PASSED` and the cache-hit-rate check is clean.
At that point the tag becomes evidence — keep it on `--no-traffic` until the call is made to
promote to LATEST via the normal deploy pipeline.

To delete the tag:

```bash
# Removes the tag URL; the underlying revision is GC'd by Cloud Run on its
# own retention policy. Does NOT shift any traffic.
gcloud run services update-traffic agent-backend-combined \
    --region=us-central1 \
    --remove-tags=c1-compact
```

### Checkpoint #2 — prod is still untouched

```bash
# Must match the output from step 0b.
gcloud run services describe agent-backend-combined --region=us-central1 \
    --format='value(spec.traffic[].revisionName, spec.traffic[].percent)'
```

## 6. What this runbook deliberately does NOT do

- **Does not edit `infra/gcp/cloud-run-backend.tf`.** Phase 9 is validation, not promotion.
  The 8 `CONTEXT_*` env vars stay out of Terraform; a future promotion gates them in.
- **Does not flip prod traffic.** Every step keeps `--no-traffic` on the new revision.
- **Does not run in CI.** Phase 9 is a one-shot operator step. It is not idempotent and the
  Langfuse trace volume from a batch run is non-trivial.
- **Does not score prompt-cache hit-rate from carriers.** That signal lives on the provider
  side; §4 is a manual read.

## 7. References

- Design: [`c1_message_compaction.design.md`](c1_message_compaction.design.md) §11
- Impl: [`c1_message_compaction.impl.md`](c1_message_compaction.impl.md) §11
- Stress harness: [`frontend/e2e/full-stack/planning-stress.spec.ts`](../../frontend/e2e/full-stack/planning-stress.spec.ts)
- Analyzer: [`scripts/analyze_planning_traces.py`](../../scripts/analyze_planning_traces.py) (`score_run` compaction branch + `gate_failures`)
- §7 carrier: [`services/governance/context_compaction_carrier.py`](../../services/governance/context_compaction_carrier.py)
