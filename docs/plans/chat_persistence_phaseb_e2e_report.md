---
type: plan
title: 'Chat persistence Phase B — E2E validation report'
description: 'Status: generated report — VALIDATED.'
tags: [plan]
---

# Chat persistence Phase B — E2E validation report

**Status:** generated report — **VALIDATED**.
**Plan:** [`chat_persistence_phaseb_gcp_e2e_validation.plan.md`](chat_persistence_phaseb_gcp_e2e_validation.plan.md).
**Capture:** `cache/phaseb_reject/probe_batch.jsonl`

## Per-case results

| case | run-1 keys | rejected key | run-2 keys | excluded? |
|------|------------|--------------|------------|-----------|
| PHASEB-LOCATION | ['54934e3f53b14b74bd7c80da86e4bcb2', '7ae5c670dc2c4373af0b5acc4fe9410b'] | 54934e3f53b14b74bd7c80da86e4bcb2 | ['7ae5c670dc2c4373af0b5acc4fe9410b'] | True |
| PHASEB-THEME | ['925a9263f26a4ba3908ca44291c643af', 'profile'] | 925a9263f26a4ba3908ca44291c643af | ['profile'] | True |
| PHASEB-UNITS | ['d6120c737ca64926987c8ba538b83111'] | d6120c737ca64926987c8ba538b83111 | [] | True |

## Hard-0 gates

- recall_keys_missing (C1): 0
- suppress_carrier_missing (C3): 0
- reject_not_excluded (C4): 0
- content_leaked_in_carrier (C5): 0
- missing_trace_join: 0

**Verdict:** **VALIDATED**

## Screenshot index

See `frontend/e2e/artifacts/phaseb/` for disclosure + full-page captures.
