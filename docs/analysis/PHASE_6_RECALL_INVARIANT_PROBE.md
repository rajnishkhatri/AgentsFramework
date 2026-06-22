---
type: analysis
title: Phase 6 — Memory recall invariant probe (Tier-A) — explanation report
description: What Phase 6 of the `replace-mem0-pgvector` plan shipped, why each piece exists, what's deliberately deferred, and how to read the wiring. Companion to the Phase 6 log entry in docs/plans/log.md.
tags: [analysis, memory, pgvector, probe, eval, tier-a, phase-6]
timestamp: 2026-06-22
plan_id: replace-mem0-pgvector
related:
  plan: "[replace_mem0_pgvector.plan.md](../plans/replace_mem0_pgvector.plan.md)"
  skill: "[agentsframework-eval-probe](../skills/agentsframework-eval-probe/SKILL.md)"
  log: "[docs/plans/log.md](../plans/log.md)"
  prior_phase: "Phase 5 cutover walkthrough — [MEMORY_MULTISESSION_PGVECTOR_CUTOVER_WALKTHROUGH.md](MEMORY_MULTISESSION_PGVECTOR_CUTOVER_WALKTHROUGH.md)"
---

# Phase 6 — Memory recall invariant probe (Tier-A)

> **TL;DR.** Phase 6 of the `replace-mem0-pgvector` plan added a deterministic, content-free invariant check that runs on **every** memory recall in the live runtime, plus a frozen offline regression fixture that goes red if any of the four guarded failure modes silently regresses. No judge, no rubric, no LLM call — just the cheapest thing that catches the failures the plan named, wired where the seam runs, and gated in CI.

## 1. Why this exists

After Phase 5 cut prod over to the new pgvector memory backend, the recall seam at `orchestration/react_loop.py:1080-1169` became the load-bearing read path for user memory. Nothing in the runtime was checking that the seam respects its own contract on every call — cross-user leak, returning more rows than requested, returning a malformed score, or dropping the carrier-join key would all have flown past silently and surfaced only as downstream quality regressions.

The plan called this out as Phase 6:

> Use the `agentsframework-eval-probe` skill to wire a Tier-A probe on the recall seam … L1 deterministic: invariant checks — every recall returns ≤ limit, every record has the requested `user_id`, `score` in [0,1], `created_at` non-null. 100% sample.

This is the **cheapest thing that catches the failures we have observed**. It is *not* an attempt to grade recall *quality* — that is Phase 7's job and requires human-led open coding first (skill cardinal rule R3 / AP-10). The probe shipped here is the structural-integrity floor.

## 2. The four invariants

The validator scores `(user_id, requested_limit, kept_records)` against four binary checks, emitted in a stable order so the eval payload schema is fixed:

| # | Invariant | What it catches | Severity |
|---|---|---|---|
| 1 | `memory_recall.limit_respected` | `len(kept) ≤ requested_limit` — the backend or post-filter returned more rows than asked for | Contract |
| 2 | `memory_recall.user_isolated` | Every kept record has `user_id` == the requested user — cross-user leak (`alice` sees `mallory`'s memories) | **PRIVACY** (load-bearing) |
| 3 | `memory_recall.score_bounded` | `metadata["score"]`, when present, is a float in `[0, 1]` — pgvector returns clamped cosine; in-memory may omit. Catches misclamps + non-numeric scores | Data integrity |
| 4 | `memory_recall.key_integrity` | Every `record.key` is a non-empty string — the carrier and eval-view join on these | Observability |

### 2.1 One swap vs the plan: `created_at` → `key_integrity`

The plan listed `created_at non-null` as the fourth invariant. While wiring up, it became clear that `created_at` is **database-side only** on the four-field `MemoryRecord` round-trip — the Phase 2 contract drops `created_at` (along with `id`, `embedding`, and `embed_text`) when `get` / `search` reconstruct the four user-facing fields. The validator can't see what `search` doesn't return.

`key` *is* in the round-trip and is what the existing `MEMORY_RECALLED` carrier already advertises in `details["keys"]`. A broken key surfaces as a join failure on every downstream consumer (eval-view, dedup, suppress audit). So the swap keeps the spirit of the plan (a non-null carrier-relevant field) and is decidable from what `search` actually returns.

This is recorded in the log entry; the plan still names `created_at`, but the shipped behavior is `key_integrity`.

## 3. Where each piece lives

```
services/governance/memory_recall_validator.py    ← L1 pure function
orchestration/react_loop.py:1155                  ← invocation seam (8 lines)
meta/probes/memory_recall_invariants_benchmark_v1.json   ← frozen fixture
tests/services/governance/test_memory_recall_validator.py    ← 16 tests
tests/orchestration/test_memory_wiring.py:+2                 ← wiring tests
tests/meta/probes/test_memory_recall_invariants_benchmark.py  ← 11 tests
tests/architecture/test_service_isolation.py:+4              ← isolation guards
```

### 3.1 The L1 validator — a pure function

`services/governance/memory_recall_validator.py` exposes:

```python
def validate_recall(
    *,
    user_id: str,
    requested_limit: int,
    kept: list[MemoryRecord],
) -> list[RecallInvariantResult]: ...
```

Modeled on `services/governance/guardrail_validator.py::ValidationResult` (same shape, same `details` discipline). Each result is binary (`passed: bool`), named (`name: str`), and carries a content-free `details` string.

**What it imports.** Only stdlib + `pydantic` + `services.long_term_memory.MemoryRecord` (the type it scores against — same precedent as `guardrail_validator` owning `GuardRail`). The architecture test pins this: no framework, no `orchestration/`, no `meta/`, no `middleware/`, no peer-service imports beyond `long_term_memory`.

### 3.2 The wiring — eight lines in the recall seam

The validator is invoked immediately after `filter_recall_records` produces `kept`:

```python
# orchestration/react_loop.py:1155
from services.governance.memory_recall_validator import validate_recall

_kept_for_invariants = [] if recall_error else list(kept)
_invariant_results = validate_recall(
    user_id=recall_user_id,
    requested_limit=3,
    kept=_kept_for_invariants,
)
_invariants_payload = [
    {"name": r.name, "passed": r.passed, "details": r.details}
    for r in _invariant_results
]

await eval_capture.record(
    target="memory_recall",
    ai_input={"query_len": len(recall_query)},
    ai_response={
        "count": recall_count,
        "degraded": bool(recall_error),
        "invariants": _invariants_payload,
    },
    config=config,
    step=state.get("step_count", 0),
)
```

**Two load-bearing wiring choices:**

1. **Results land in `eval_capture.record(...)`, not in the `MEMORY_RECALLED` carrier.** The carrier's `details` schema is pinned by a pre-existing regression-guard test (`test_t1_recall_injected_and_store_fires` at `tests/orchestration/test_memory_wiring.py:294`) which asserts a closed key set. Keeping the carrier untouched means zero migration of consumers + zero regression risk on the carrier surface. The eval-capture path is the explicit Recording-pillar audit surface anyway — exactly where the skill says to put it.

2. **Degraded path validates a vacuous empty `kept`.** When the backend raises `MemoryBackendError`, `kept` may not even exist; the wiring substitutes `[]` so the validator runs against an empty list (every invariant passes vacuously). This gives the eval surface a **stable schema on every recall** — consumers never have to branch on "did the probe run."

### 3.3 The offline regression fixture

`meta/probes/memory_recall_invariants_benchmark_v1.json` freezes nine rows:

- **4 acceptance rows** (`must_pass_all: true`): clean recall, empty recall, scores at `0.0` and `1.0` boundaries, missing score metadata.
- **5 rejection rows** (`must_fail: [<name>]`): limit exceeded, cross-user leak, score above 1, score below 0, empty key.

Rejection ≥ acceptance per AGENTS.md §Testing Rules and the skill's TAP-4 anti-pattern guard.

The replay test (`tests/meta/probes/test_memory_recall_invariants_benchmark.py`) parametrizes over the rows and asserts each lands on the right side. **This is the merge-blocking gate.** Per the skill: `meta.run_eval` is the judge-track scorer, not the deterministic CI gate — so the pytest replay is what gates merges, not `python -m meta.run_eval`.

Two coverage meta-tests guard the fixture itself:

- `test_fixture_has_rejection_majority`: rejection rows ≥ acceptance rows.
- `test_fixture_covers_every_invariant_at_least_once`: the validator's emitted invariant set must appear at least once in some row's `must_fail` list. **Adding a new invariant to the validator without extending the benchmark goes red here** — the gate is self-maintaining.

The fixture is versioned as `..._v1.json`. A v2 supersedes; v1 is never mutated.

### 3.4 Architecture isolation guards

`tests/architecture/test_service_isolation.py::TestMemoryRecallValidatorIsolation` adds four AST-level checks on `services/governance/memory_recall_validator.py`:

1. No imports from `orchestration/`, `components/`, `meta/`, or `trust/`.
2. No framework imports (`langgraph`, `langchain`, `openai`, `litellm`, `psycopg`, `psycopg_pool`, `sqlalchemy`).
3. No imports from `middleware/*`.
4. From peer services, only `services.long_term_memory` is allowed (the `MemoryRecord` type the validator scores against).

These are the same shape as `TestPgVectorBackendIsolation` (Phase 2) and `TestEmbeddingClientPortPlacement` (Phase 1). The validator stays pure forever or the build breaks.

## 4. The content-free privacy contract

The validator's `details` strings name only **identifiers + counts + numeric scores** — never payload values. Example failure-mode details:

```
USER_ISOLATED failed: "2 foreign-owner record(s) leaked into recall
                       for user_id='alice' (sample: 'mallory':'km')"

SCORE_BOUNDED failed: "1 record(s) with out-of-bounds score
                       (sample: key='k1':score=1.5)"
```

These are content-free: `user_id`, `key`, integer counts, and the numeric score itself are identifiers. Payload values (`payload["text"]`, the actual memory content) are **never referenced**.

This is enforced by `TestContentFreeContract` in the validator tests: a distinctive payload token (`TOTALLY_UNIQUE_PAYLOAD_TOKEN_42`) is injected into a record that triggers two simultaneous failures, and the test asserts the token appears in **none** of the result `details` strings.

Privacy in the LTM subsystem is structural — this test makes it structural for the probe too.

## 5. What Phase 6 deliberately did **not** ship

The skill (and the plan) draw a sharp line between Tier-A (this phase) and Tier-B (a judge track). Phase 6 stopped at Tier-A on purpose.

| Skipped piece | Why |
|---|---|
| **L2 sampled LLM judge** (recall-relevance grading) | This is Phase 7. Requires human-led open coding first (skill R3 / AP-10). An LLM-graded judge built without prior trace reading is the AP-1 anti-pattern. |
| **Rubric content / `.j2` prompt file** | Authored by the user, not the agent, per skill cardinal rule R3. Phase 7 territory. |
| **Gold set** | Skill Stage 5 — multi-week, double-labeled, frozen test split. Premature without shadow-mode evidence. |
| **Judge calibration + enable-policy certificate** | Skill Stage 6 — gated on the gold set. |
| **Langfuse `publish_memory_recall` sink adapter** | The skill names a `publish_<seam>` sink as a Phase 4 Done-when, but the existing `eval_capture.record(...)` path already lands the invariants payload in telemetry. A separate sink adapter (with the Langfuse SDK in `middleware/adapters/`) is its own commit when shadow data warrants. |
| **L3 drift detector (recall count / latency / degraded-rate over time)** | The plan §Phase 6 mentions L3 distribution monitoring; deferring this until the L1 fixture has caught at least one signal, to avoid building drift infra for invariants that may never fire. `meta/drift.py` is the spine when we want it. |
| **`MEMORY_RECALL_PROBE_ENABLED` composition flag** | The skill's "fail-closed / shadow" posture applies to *judges*, not to deterministic invariants. The L1 check is pure, free, content-free, and always-on. There is no enable-gate to flip because there is no LLM call to gate. |

The plan's Phase 7 (the human-led Tier-A recall-relevance eval scaffold) is the natural successor; it stays a separate workstream gated on shadow-mode evidence from this probe.

## 6. How to read what the probe emits

Every recall now writes an `eval_capture` row with `target="memory_recall"` and an `ai_response` shaped like:

```json
{
  "count": 2,
  "degraded": false,
  "invariants": [
    {"name": "memory_recall.limit_respected", "passed": true,
     "details": "kept=2 <= limit=3"},
    {"name": "memory_recall.user_isolated", "passed": true,
     "details": "all 2 records owned by user_id='alice'"},
    {"name": "memory_recall.score_bounded", "passed": true,
     "details": "all scores in [0, 1] across 2 record(s)"},
    {"name": "memory_recall.key_integrity", "passed": true,
     "details": "all 2 record key(s) non-empty"}
  ]
}
```

The schema is **stable on every recall** — even when the backend degraded (`degraded: true, count: 0, invariants: [<all passing on empty>]`). Consumers can rely on the shape without branching.

### Reading for failures in prod

Once the probe is shipped to a revision (Phase 6 itself shipped only code; the deploy is a separate operator action), a failure surfaces as:

```bash
# Any recall where the L1 floor was violated
gcloud logging read \
  'resource.type=cloud_run_revision
   AND resource.labels.service_name=agent-backend-combined
   AND jsonPayload.target="memory_recall"
   AND jsonPayload.ai_response.invariants.passed=false' \
  --limit=50
```

The cross-user-leak invariant (`memory_recall.user_isolated`) is the load-bearing privacy one — a single `passed: false` there is a P0 incident, not a drift signal. The other three are integrity contracts; their failure modes are real bugs but not privacy ones.

## 7. Test counts and regression sweep

| Surface | Tests | Result |
|---|---|---|
| `tests/services/governance/test_memory_recall_validator.py` | 16 | GREEN |
| `tests/orchestration/test_memory_wiring.py` (Phase 6 additions only) | 2 | GREEN |
| `tests/orchestration/test_memory_wiring.py` (pre-existing carrier regression-guard) | 9 | GREEN (unchanged) |
| `tests/meta/probes/test_memory_recall_invariants_benchmark.py` | 11 | GREEN |
| `tests/architecture/test_service_isolation.py::TestMemoryRecallValidatorIsolation` | 4 | GREEN |
| **Full regression** (`tests/services/ tests/middleware/ tests/orchestration/ tests/architecture/ tests/meta/`) | **2159** | **GREEN, 0 regressions** |

Rejection ≥ acceptance per AGENTS.md §Testing Rules across the validator + benchmark suites combined (8 validator rejection + 5 fixture rejection = 13 rejection vs 6 validator acceptance + 4 fixture acceptance = 10 acceptance).

`okf_lint.py`: 0 failures (123 pre-existing warnings, all unrelated docs).

## 8. Exit gate — Phase 6 → Phase 7 (deferred)

Plan §Phase 6 Done-when:

- ✅ L1 check is a pure function in `services/`, no framework imports, returns per-category results
- ✅ Invoked in the orchestration node on 100% of the seam's traffic; results recorded via `eval_capture.record(...)`
- ✅ A frozen `<seam>_benchmark_v1.json` (must-accept / must-reject) holds the failure modes
- ✅ The pytest replay scores it green in CI, with a replay test asserting it
- ✅ No judge built

**Phase 6 exits clear.** Phase 7 (Tier-A recall-relevance eval scaffold, human-led) is the natural successor; it stays a separate workstream and starts only when shadow data from this probe accumulates evidence that a judge is worth building.

## 9. What to do next (operator)

This phase ships **code only**. The deploy is a separate operator action:

1. **Commit the Phase 6 diff** on a dedicated branch (`feat/phase-6-recall-invariant-probe` or equivalent).
2. **Deploy to prod** via `./scripts/deploy_gcp.sh backend` whenever the soak watch (gates 7–11 of `replace_mem0_pgvector.phase5.soak_watch.md`) is clear. The probe is content-free and pure, so it could ride into the same revision as Phase 5's soak completion without affecting that clock — but cleaner to land it as its own revision after the soak passes.
3. **Once live**, monitor `eval_capture` rows for `target="memory_recall"` with any `invariants[].passed: false`. The `memory_recall.user_isolated` failure is the only P0 — the other three are integrity bugs worth fixing but not privacy incidents.
4. **Phase 7 trigger**: re-open this report's §5 deferred list when shadow data from the probe accumulates ≥ ~100 real recall traces with at least one persistent failure mode that a human-graded judge could distinguish. Until then, Phase 7 stays in plan — never in scope.

## 10. Companion artifacts

- Plan source of truth: [`docs/plans/replace_mem0_pgvector.plan.md`](../plans/replace_mem0_pgvector.plan.md) §Phase 6
- Log entry: [`docs/plans/log.md`](../plans/log.md) — 2026-06-22 Phase 6 row
- Skill spine: [`docs/skills/agentsframework-eval-probe/SKILL.md`](../skills/agentsframework-eval-probe/SKILL.md)
- Phase 5 cutover walkthrough (prior phase): [`MEMORY_MULTISESSION_PGVECTOR_CUTOVER_WALKTHROUGH.md`](MEMORY_MULTISESSION_PGVECTOR_CUTOVER_WALKTHROUGH.md)
- Soak watch (independent of Phase 6): [`docs/plans/replace_mem0_pgvector.phase5.soak_watch.md`](../plans/replace_mem0_pgvector.phase5.soak_watch.md)
- Budget-eviction side finding (independent workstream): [`MEM_BUDGET_ISOLATED_VERDICT.md`](MEM_BUDGET_ISOLATED_VERDICT.md)
