---
type: validation-walkthrough
title: 'Recipe 4 — End-to-End BlackBox → Langfuse Validation Runbook'
description: 'End-to-end BlackBox → Langfuse pipeline validation on GCP.'
tags: [recipe, governance]
---

# Recipe 4 — End-to-End BlackBox → Langfuse Validation Runbook

**Goal:** Validate the full BlackBox → Langfuse pipeline on GCP: all 9 event types land as Langfuse observations, hash-chain scores are attached, compliance dataset items are created, and PII redaction works. Then verify rollback safety and document findings.

**Status:** Ready to run
**Prerequisites:** Recipes 0–3 completed; relay-enabled backend deployed (see [blackbox_langfuse_gcp_deploy.plan.md](../../plans/blackbox_langfuse_gcp_deploy.plan.md))

---

## Quick reference

| Item | Value |
|------|-------|
| CLI driver | `scripts/validate_blackbox_langfuse.py` |
| Pytest harness | `tests/integration/test_blackbox_langfuse_gcp.py` |
| Scenario dataset | `tests/synthetic/blackbox/dataset.py` |
| Langfuse assertions | `tests/synthetic/blackbox/langfuse_assertions.py` |
| Drift report | `docs/drift/blackbox_event_taxonomy_drift.json` |
| Rollback lever | `BLACKBOX_RELAY_MODE=off` in Cloud Run env |
| Langfuse SDK version | 4.5.1+ (verified compatible) |

---

## Pre-flight checks

Before running validation, confirm:

```bash
# 1. Architecture + relay tests pass
pytest tests/middleware/sidecars/test_black_box_to_telemetry.py \
       tests/middleware/test_composition_relay.py \
       tests/middleware/test_app_prod.py \
       tests/infra/gcp/test_cloud_run_backend.py \
       tests/architecture/ \
       -v -p no:logfire

# 2. Langfuse credentials are set
echo "PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY:0:8}..."
echo "HOST: ${LANGFUSE_HOST:-https://cloud.langfuse.com}"

# 3. SDK API surface resolves
python -c "
from langfuse import Langfuse
c = Langfuse(public_key='pk-test', secret_key='sk-test')
assert hasattr(c, 'api')
assert hasattr(c.api, 'trace')
assert hasattr(c.api, 'observations')
assert hasattr(c.api, 'scores')
assert hasattr(c.api, 'dataset_items')
c.flush()
print('SDK check: PASS')
"

# 4. Relay is running on deployed revision
gcloud logging read \
  'resource.type="cloud_run_revision" AND textPayload=~"relay started"' \
  --project=$GCP_PROJECT --limit=5 --format='table(timestamp,textPayload)'
```

---

## Step 1 — Obtain session cookie (human step)

1. Open `$FRONTEND_URL` in a browser and sign in via WorkOS.
2. Open DevTools → Application → Cookies → select the frontend origin.
3. Copy the value of the `wos-session` cookie.
4. Export it:

```bash
export WOS_SESSION_COOKIE="<paste cookie value>"
```

Re-copy if the harness later receives `401 Unauthorized`.

---

## Step 2 — Run scenarios

### Option A: CLI driver (interactive, per-scenario gates)

```bash
python scripts/validate_blackbox_langfuse.py \
  --frontend-url "$FRONTEND_URL" \
  --cookie-env WOS_SESSION_COOKIE \
  --scenario S1,S2,S3,S4,S5,S6,S8 \
  --gate per-action \
  --report
```

### Option B: pytest harness (automated, all-at-once)

```bash
pytest tests/integration/test_blackbox_langfuse_gcp.py \
  -v -p no:logfire \
  -m "live_llm and simulation" \
  --tb=short
```

Both approaches exercise the same scenarios and assertions.

---

## Step 3 — Verify per-scenario results

### Per-scenario UI checklist

For each completed scenario, open the Langfuse trace URL and manually verify:

#### S1 — Simple Q&A

**Trace URL:** `$LANGFUSE_HOST/trace/<S1_trace_id>`

- [ ] `task.started` observation present (type=agent)
- [ ] `step.planned` observation present (type=chain)
- [ ] `model.selected` observation present (type=generation)
- [ ] `guardrail.checked` observation present (type=guardrail)
- [ ] `step.executed` observation present (type=span)
- [ ] `task.completed` observation present (type=agent)
- [ ] Score: `hash_chain_valid` = 1.0
- [ ] Dataset: item in `agent-compliance-audit`

#### S2 — Tool-using task

**Trace URL:** `$LANGFUSE_HOST/trace/<S2_trace_id>`

- [ ] All S1 observations present
- [ ] `tool.called` observation present (type=tool)
- [ ] Score: `hash_chain_valid` = 1.0
- [ ] Dataset: item in `agent-compliance-audit`

#### S3 — Tool error + recovery

**Trace URL:** `$LANGFUSE_HOST/trace/<S3_trace_id>`

- [ ] All S1 observations present
- [ ] `tool.called` observation present (type=tool)
- [ ] `error.occurred` observation present (type=span, level=ERROR)
- [ ] Score: `hash_chain_valid` = 1.0
- [ ] Dataset: item in `agent-compliance-audit`

#### S4 — Routing tier change

**Trace URL:** `$LANGFUSE_HOST/trace/<S4_trace_id>`

- [ ] All S1 observations present
- [ ] `parameter.changed` observation present (type=span) — **may be absent** if router heuristics don't trigger tier escalation; note as documented gap, not a hard fail.
- [ ] Score: `hash_chain_valid` = 1.0
- [ ] Dataset: item in `agent-compliance-audit`

#### S5 — Forced failing workflow

**Trace URL:** `$LANGFUSE_HOST/trace/<S5_trace_id>`

- [ ] `task.started` observation present
- [ ] `error.occurred` observation present (level=ERROR)
- [ ] `task.completed` observation present (outcome=failure expected)
- [ ] Score: `hash_chain_valid` = 1.0 (chain is intact; the task just failed)
- [ ] Dataset: item in `agent-incident-replay` (NOT `agent-compliance-audit`)

#### S6 — PII/API-key redaction

**Trace URL:** `$LANGFUSE_HOST/trace/<S6_trace_id>`

- [ ] All S1 observations present
- [ ] `alice.smith@example.com` does NOT appear in observation metadata
- [ ] `sk-proj-abc123def456ghi789jkl012mno345pqrstu678vwx` does NOT appear in metadata
- [ ] Redaction markers (e.g. `[REDACTED]`) appear instead
- [ ] Score: `hash_chain_valid` = 1.0
- [ ] Dataset: item in `agent-compliance-audit`

#### S8 — Two concurrent workflows

**Trace URLs:** `$LANGFUSE_HOST/trace/<S8A_trace_id>` and `$LANGFUSE_HOST/trace/<S8B_trace_id>`

- [ ] Two distinct trace_ids in Langfuse
- [ ] Each trace has independent observations (not mixed)
- [ ] Each trace has its own `hash_chain_valid` = 1.0 score
- [ ] Two items in `agent-compliance-audit` dataset

---

## Step 4 — Compliance dataset verification (Phase 5)

```bash
python -c "
from tests.synthetic.blackbox.langfuse_assertions import verify_compliance_datasets

trace_map = {
    'S1': '<S1_trace_id>',
    'S2': '<S2_trace_id>',
    'S3': '<S3_trace_id>',
    'S4': '<S4_trace_id>',
    'S5': '<S5_trace_id>',
    'S6': '<S6_trace_id>',
    'S8-A': '<S8A_trace_id>',
    'S8-B': '<S8B_trace_id>',
}

report = verify_compliance_datasets(trace_map)
print(report.summary)
for r in report.audit_results + report.incident_results:
    status = 'PASS' if r.passed else 'FAIL'
    print(f'  [{status}] {r.description}')
"
```

Expected:
- `agent-compliance-audit` contains items for S1, S2, S3, S4, S6, S8-A, S8-B
- `agent-incident-replay` contains item for S5
- All `hash_chain_valid` scores are 1.0

---

## Step 5 — Failure-path log checks (Phase 7)

```bash
# Check for Langfuse init failures (expect none)
gcloud logging read \
  'resource.type="cloud_run_revision" AND textPayload=~"langfuse client init failed"' \
  --project=$GCP_PROJECT --limit=10 --format='table(timestamp,textPayload)'

# Check for DLQ / failure entries (expect none)
gcloud logging read \
  'resource.type="cloud_run_revision" AND textPayload=~"langfuse_failures|DLQ"' \
  --project=$GCP_PROJECT --limit=10 --format='table(timestamp,textPayload)'
```

Both queries should return zero results. If either returns results, investigate the relay health before accepting validation results.

---

## Step 6 — Pass/fail summary

After all scenarios complete, produce a summary table:

| Scenario | Trace ID | Observations | Score | Dataset | Redaction | Result |
|----------|----------|-------------|-------|---------|-----------|--------|
| S1 | `<id>` | 6/6 | 1.0 | audit | n/a | PASS/FAIL |
| S2 | `<id>` | 7/7 | 1.0 | audit | n/a | PASS/FAIL |
| S3 | `<id>` | 8/8 | 1.0 | audit | n/a | PASS/FAIL |
| S4 | `<id>` | 7/7 or 6/7 | 1.0 | audit | n/a | PASS/SOFT |
| S5 | `<id>` | 6/6 | 1.0 | incident | n/a | PASS/FAIL |
| S6 | `<id>` | 6/6 | 1.0 | audit | 2/2 | PASS/FAIL |
| S8-A | `<id>` | 6/6 | 1.0 | audit | n/a | PASS/FAIL |
| S8-B | `<id>` | 6/6 | 1.0 | audit | n/a | PASS/FAIL |

**S4 note:** `parameter.changed` is heuristic-dependent. Absence is a documented gap (SOFT pass), not a hard failure.

---

## Rollback procedure

If the relay causes issues in production, disable it without redeploying:

```bash
# Set BLACKBOX_RELAY_MODE=off to disable the relay
gcloud run services update agent-backend-combined \
  --project=$GCP_PROJECT \
  --region=$GCP_REGION \
  --set-env-vars="BLACKBOX_RELAY_MODE=off"
```

This immediately stops the relay from reading `trace.jsonl` files and sending events to Langfuse. The `BlackBoxRecorder` continues writing to disk (the recordings are not lost), but no data flows to Langfuse until `BLACKBOX_RELAY_MODE` is set back to `in_process`.

To re-enable:

```bash
gcloud run services update agent-backend-combined \
  --project=$GCP_PROJECT \
  --region=$GCP_REGION \
  --set-env-vars="BLACKBOX_RELAY_MODE=in_process"
```

---

## Known issues and watch items

### Scale-to-zero + CPU throttling

Cloud Run with `cpu_idle=true` (line 57 of `cloud-run-backend.tf`) throttles CPU after the HTTP response ends. The in-process relay may be delayed flushing the final `task.completed` event and compliance dataset item. The validation harness polls (15 attempts × 2s intervals = 30s window). If items are delayed beyond this window:

1. Send a follow-up request to wake the instance.
2. Re-poll with `--retry` or manually query Langfuse.

### Langfuse SDK version

Assertions were verified against Langfuse SDK 4.5.1. The API surface used:

| Call | Verified |
|------|----------|
| `client.api.trace.get(trace_id)` | Yes |
| `client.api.observations.get_many(trace_id=..., limit=...)` | Yes |
| `client.api.scores.get_many(trace_id=..., limit=...)` | Yes |
| `client.api.dataset_items.list(dataset_name=..., limit=...)` | Yes |

If upgrading to a newer SDK version, re-run the SDK surface check from the pre-flight section.

### S4 parameter.changed heuristic

The `PARAMETER_CHANGED` event fires only when the router escalates from one model tier to another. The S4 prompt is designed to trigger this, but it depends on the router heuristics in `components/router.py`. If the router doesn't escalate, the observation will be absent. This is a **known gap**, not a test failure.

---

## Event taxonomy drift findings

The governance-triangle documentation (`governanaceTriangle/02_*.md` and `05_*.md`) describes a different event taxonomy than the shipped production code. A machine-readable drift report is at:

```
docs/drift/blackbox_event_taxonomy_drift.json
```

Key findings:

1. **Import path drift:** Docs reference `backend.explainability.black_box`; production uses `services.governance.black_box`.
2. **Event taxonomy mismatch:** Only `ERROR`↔`ERROR_OCCURRED` and `PARAMETER_CHANGE`↔`PARAMETER_CHANGED` have clear semantic mappings. The remaining events serve different design philosophies (multi-agent tutorial vs. ReAct loop).
3. **Recorder API divergence:** Docs describe multi-method recorder; production uses single `record(event)` method.
4. **Storage format:** Docs describe per-artifact JSON files; production uses append-only JSONL with SHA-256 hash chain.

Reconciliation notes have been added to both `governanaceTriangle/02_*.md` and `05_*.md` with a mapping table.

---

## References

- [Recipe 0: Overview](00_overview.md) — BlackBox concepts and the 9 event types
- [Recipe 1: Outbox Relay](01_outbox_relay.md) — How the relay bridges local JSONL to Langfuse
- [Recipe 2: Event Mapping](02_event_mapping.md) — BlackBox event → Langfuse observation mapping
- [Recipe 3: Compliance Dataset](03_compliance_dataset.md) — Hash chain scores and dataset items
- [blackbox_e2e_validation.plan.md](../../plans/blackbox_e2e_validation.plan.md) — Full E2E validation plan
- [blackbox_langfuse_gap_closure.plan.md](../../plans/blackbox_langfuse_gap_closure.plan.md) — Gap closure plan
- [blackbox_event_taxonomy_drift.json](../../drift/blackbox_event_taxonomy_drift.json) — Machine-readable drift report
