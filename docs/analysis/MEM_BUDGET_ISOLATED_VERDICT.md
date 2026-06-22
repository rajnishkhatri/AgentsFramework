---
type: analysis
title: 'MEM-BUDGET-overflow-evicts-low-01 — isolated rerun verdict (rev 00094-rfq)'
description: 'Isolated probe of the budget-eviction case under a wiped owner namespace; eviction structurally unreachable in prod (budget=50 default vs case-rationale 5). Plus a BFF MemoryStore.add() key-discard finding.'
tags: [analysis, memory, pgvector, budget-eviction, e2e]
---

# MEM-BUDGET-overflow-evicts-low-01 — isolated rerun verdict

## Setup

| Field | Value |
|---|---|
| Backend rev | `agent-backend-combined-00094-rfq` (commit `af3336a`) |
| Frontend | `https://agent-frontend-w65nrxwkiq-uc.a.run.app` |
| Auth | Real WorkOS owner |
| Spec | [`frontend/e2e/full-stack/memory-budget-isolated.spec.ts`](../../frontend/e2e/full-stack/memory-budget-isolated.spec.ts) |
| Result row | [`cache/memory_multisession/budget_isolated.jsonl`](../../cache/memory_multisession/budget_isolated.jsonl) |
| Screenshot | `cache/memory_multisession/screenshots_budget_isolated/MEM-BUDGET-overflow-evicts-low-01-s1.png` |
| Probe trace id | `2fec3d4b11adf3a9f66fb4359a6dc5f2` |
| Date | 2026-06-22 |

## What the isolated rerun did

Unlike the shared MEM_SMOKE rerun (which seeded BUDGET-01 after DEDUP and SALIENCE had already written to the same `identity.owner` namespace), this spec:

1. **Wipes** every owner memory before the case (`GET /api/memory` → `DELETE` each key). Wiped **26 rows**; confirmed 0 remaining.
2. Seeds the 6 BUDGET-01 facts via `POST /api/memory`.
3. Drives the probe prompt `"What are the most important things you know about me?"` on a fresh thread.
4. Asserts on the answer content semantically:
   - **(a)** bleed tokens (`email`, `Pacific`, `metric`, `phone`) absent → confirms isolation.
   - **(b)** at least one high-salience fact (`Go`/`Seattle`/`tabs`) surfaces → confirms own seeds reached the model.
   - **(c)** `teal` (lowest salience 0.1) absent → eviction signal.

## Observation

```json
{
  "owner_wipe": { "wiped": 26, "remaining": 0 },
  "recalled_count_dom": 3,
  "response_text": "Based on the context I have, here are the most important things I know about you:\n\nYou live in Seattle.\nYou drink espresso.\nYou once mentioned liking the color teal.\n…"
}
```

| Assertion | Result | Notes |
|---|---|---|
| (a) bleed tokens absent | ✅ **PASS** | wipe + isolation worked; no email/Pacific/metric/phone |
| (b) high-salience surfaces | ✅ **PASS** | Seattle (salience 0.9) surfaced |
| (c) `teal` absent (eviction) | ❌ **FAIL** | teal (salience 0.1) appears in the answer |

## Root cause (eviction unreachable in prod)

The case rationale assumes `budget=5` (six facts overflows budget by one, lowest-salience evicted). The deployed backend has **no `MEMORY_BUDGET_SEMANTIC` env var** ([`infra/gcp/cloud-run-backend.tf`](../../infra/gcp/cloud-run-backend.tf)), so it falls back to the default **50** ([`middleware/composition.py:500`](../../middleware/composition.py)):

```python
memory_budget_semantic: int = Field(
    default=50, validation_alias="MEMORY_BUDGET_SEMANTIC"
)
```

`_consolidate_on_overflow` ([`services/long_term_memory.py:194`](../../services/long_term_memory.py)) only runs `consolidate()` when `count > budget`. With 6 facts and budget=50, the branch never fires — teal stays. The probe-time top-k is then chosen by semantic relevance + recall floor, and teal ("color teal") apparently scores well against the abstract "most important" prompt.

This is **expected-given-config**, not a bug in `consolidate()` itself. The consolidation code is exercised and green under unit tests; the production trigger is just not crossed.

## Secondary finding — BFF `MemoryStore.add()` discards the client key

[`frontend/lib/adapters/memory_store/http_memory_store.ts`](../../frontend/lib/adapters/memory_store/http_memory_store.ts) `async add(content, type, salience)` builds the request body with **`key: null` hardcoded** — there is no `key` parameter on the port, and `MemoryCreateRequestSchema` defaults it to `null`. The backend then mints a UUID (`middleware/app_prod.py:463` `key = body.key or uuid.uuid4().hex`).

Effect on the existing `cleanupSeededMemories` helper in [`frontend/e2e/full-stack/memory-multisession.spec.ts:172`](../../frontend/e2e/full-stack/memory-multisession.spec.ts): it deletes by the corpus-declared key (`f1`–`f6`, `pref-a`/`pref-b`, etc.) — but those keys never existed in the backend. **Every crud-seed case's `afterAll` cleanup has been a silent no-op**. This is why the shared MEM_SMOKE rerun showed bleed across DEDUP → SALIENCE → BUDGET (each prior case's seeds survived into the next case's window — and into this case's pre-wipe count of 26 stale owner rows).

That helper either needs to switch to list-then-delete (the pattern used in `memory-budget-isolated.spec.ts`), OR the BFF adapter + port needs a `key?: string` parameter forwarded to the backend (so corpus keys are honored). The list-then-delete teardown is operationally simpler and is what this spec uses; deciding to also fix the port is out of scope for this validation workstream — it is the **first thing the next memory-suite touch-up should do** because the same gap affects DEDUP cleanup, SALIENCE cleanup, and any other crud-seed case.

## Recommendations

1. **Configuration**: To exercise the eviction code path on prod, set `MEMORY_BUDGET_SEMANTIC=5` on a stress revision (via `infra/gcp/cloud-run-backend.tf` env var or a `--update-env-vars` tag deploy) and rerun this spec. Do NOT change the default on the production revision — production wants the high budget for real users.
2. **Spec**: This spec is committed and runnable; it will flip from FAIL to PASS once budget=5 is in effect, with no further changes.
3. **Cleanup hygiene fix (out of scope here)**: file a follow-up to either teach `cleanupSeededMemories` to list-then-delete, or add a `key` parameter to the `MemoryStore` port.
4. **No change to `services/long_term_memory.py`**: the consolidation code is correct under unit tests; the bug is in the deployment config (and the corpus assumption that budget=5 in the target env).

## Reproduce

```bash
TEST_PROFILE=prod E2E_AUTHENTICATED=1 \
  pnpm --filter @agent/frontend exec playwright test \
  e2e/full-stack/memory-budget-isolated.spec.ts \
  --project=chromium-desktop --reporter=line --timeout=240000
```
