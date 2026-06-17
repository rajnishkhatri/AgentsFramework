# Memory Extractor — Enable Policy (the `MEMORY_AUTOCAPTURE_ENABLED` write-back gate)

> **Status:** SCAFFOLD — the policy *template* and the gate thresholds are
> authorable now; the **decision** to flip `MEMORY_AUTOCAPTURE_ENABLED` to
> write-back is made only when these gates clear on the **frozen test split**
> (Stage 6). Until then the flag stays OFF and Phase 2 runs in **shadow**: the
> extractor proposes, the trace carries the proposal, NOTHING is stored.
>
> **Date:** 2026-06-17. **Scope:** the precision-first enable-policy for the
> Phase-2 typed extractor's write-back. **Out of scope:** the rubric, the gold
> set ([02_goldset_spec.md](02_goldset_spec.md)), the live calibration run.
>
> **Flag:** `MEMORY_AUTOCAPTURE_ENABLED` →
> [`services/base_config.py`](../../../services/base_config.py)
> `memory_autocapture_enabled` →
> [`middleware/composition.py`](../../../middleware/composition.py)
> `MemoryAutoCaptureService(write_back_enabled=...)`.

---

## 1. The rollout ladder (mirrors GoalJudge)

```
shadow (propose-only)  →  dev-enable (write-back on dev)  →  prod-enable
        ^ here now                ^ after Stage-6 gates           ^ after dev soak
```

The flag is the gate. `MEMORY_AUTOCAPTURE_ENABLED=false` (default) IS cardinal
rule 6 ("default-off until calibrated"). It flips to write-back **only** when
every gate in §2 passes on the **frozen** `memory-extract-gold-v1` test split.
Never iterate the prompt against the test split (AP-4).

## 2. Enable gates (precision-first profile)

All must pass on the frozen test split before write-back is enabled:

| Gate | Threshold | Rationale |
|------|-----------|-----------|
| **store-class precision** | ≥ 0.90 | a polluting store degrades every future recall — precision is the gate metric (cardinal rule 5) |
| **false-store on trivia** | ≤ 2% | bounds over-capture directly |
| **mis-type rate** | ≤ 10% (tune from coded data) | type-filtered recall correctness |
| **content-leak / PII flip-rate** | **0** | a CoT-gaming red-team must not be able to force a PII store (hard gate) |
| **κ (judge vs gold)** | ≥ 0.6 | the judge agrees with humans well enough to trust |

Recall is **reported, not gated** (a missed fact is recoverable; a bad store
is not).

## 3. What "shadow" guarantees until the gate clears

- The extractor runs post-run (background, off the hot path) and proposes
  typed items.
- One `MEMORY_STORED` carrier per proposed item is emitted with
  `proposed_only: true` and `{user_id, key, type, salience}` — **never content**.
- `LongTermMemoryService.store` is **NOT called** — production state is
  untouched. (Verified by `test_memory_autocapture.py::test_shadow_proposes_but_does_not_store`.)
- The shadow carriers are the Stage-0 trace corpus the rest of the pipeline
  codes.

## 4. Red-team before flip (Stage 6)

A crafted-message red-team must be run before the flip: can a user message
force a junk store, or smuggle PII past the prompt's refusal? The
content-leak flip-rate gate (§2) is **hard zero** — any successful forced PII
store blocks the flip regardless of the other gates.

## 5. Rollback

`MEMORY_AUTOCAPTURE_ENABLED=false` instantly returns to shadow (propose-only).
Because write-back is ADD-only (no live UPDATE/DELETE), a bad-store incident is
contained to the keys written while enabled; the deferred consolidation pass +
the Phase-3 user-facing delete are the cleanup paths.
