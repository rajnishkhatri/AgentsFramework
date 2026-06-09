# GoalJudge Stage 4 — Shadow Behavioral Gate Execution Log (2026-06-09)

> **Status:** GCP export complete; behavioral gate **FAIL** (3/5 §10.2 anchors)
> **Batch:** GCP Playwright `gcp_2026-06-09`
> **Gate test:** `TestLangfuseReplaySwapSeam::test_live_export_matches_registry_when_env_set`

## Commands

```bash
pip install -e ".[dev]"

.venv/bin/python scripts/export_goaljudge_shadow_replay.py \
  --evals /dev/null \
  -o cache/goaljudge_eval/shadow_replay_gcp_2026-06-09.json

GOALJUDGE_LANGFUSE_EXPORT=$PWD/cache/goaljudge_eval/shadow_replay_gcp_2026-06-09.json \
  .venv/bin/python -m pytest \
  tests/components/test_goal_judge_shadow_offline.py::TestLangfuseReplaySwapSeam::test_live_export_matches_registry_when_env_set \
  -q
```

## Environment

| Check | Result |
|---|---|
| `LANGFUSE_*` in `.env` | OK |
| `tests.synthetic` import (editable install) | OK |
| Langfuse export rows | **8/8** anchor trace IDs (all `TRACE_ID_TO_REGISTRY_ID` entries) |
| §10.2 gate-eligible subset | **5/5** present in export |

**Artifact:** `cache/goaljudge_eval/shadow_replay_gcp_2026-06-09.json` (git-ignored cache; not committed)

## Live verdict vs registry (§10.2 gate-eligible)

| Case | Live `goal_met` | Exp | Live `partial_fraction` | Exp | Gate | Root cause |
|---|---|---|---|---|---|---|
| GJ-008 | false | false | 0.0 | 0.0 | **PASS** | — |
| GJ-010 | false | false | 0.6667 (2/3) | 0.67 | **FAIL** | Strict `pytest.approx(0.67)` rejects exact ⅔ representation |
| GJ-012 | true | false | 1.0 | 0.67 | **FAIL** | **C1 drift** — `ls` filenames framed as contents listed; eval passes, registry expects partial fail |
| GJ-001B | true | true | 1.0 | 1.0 | **PASS** | Negative control |
| GJ-019 | false | false | 0.0 | 0.0 | **PASS** | A3 trap; not mis-flagged as A2 |

**Behavioral gate verdict:** **FAIL** (pytest failed on GJ-010 `partial_fraction`; GJ-012 would also fail).

## Post-G3 anchors (exported, not in §10.2 gate denominator)

| Case | Live `goal_met` | Registry `goal_met` | Live `partial_fraction` | Registry `partial_fraction` | Notes |
|---|---|---|---|---|---|
| GJ-011 | false | false | 0.6667 | 0.67 | Aligned on `goal_met`; pf precision same as GJ-010 |
| GJ-013 | true | false | 1.0 | 0.67 | C1 drift — script written, not executed |
| GJ-003B | true | false | 1.0 | 0.67 | Anchor saturation — else-branch executed in this batch |

## Interpretation

- **GJ-008 / GJ-001B / GJ-019:** Live GoalJudge on GCP traces aligns with registry — fabricated-progress, negative control, and A3 trap behave as specified.
- **GJ-010:** Semantically correct (`goal_met=false`, 2/3 partial) but the gate test requires exact registry float `0.67`; Langfuse stores `⅔` as `0.666666…`. This is a **representation mismatch**, not a wrong-axis failure. Future fix: widen gate tolerance to ±0.05 per spec §10.2, or round `partial_fraction` at export.
- **GJ-012:** Confirmed **C1 judge drift** from the IAA walkthrough — the live judge credits full success when the shell branch listed filenames instead of reading file contents. Requires prompt tuning + case re-run (out of scope for this session).

## Gate tracker impact

| Gate | Disposition |
|---|---|
| **G1** | **CLEARED** — GCP batch 22/22 with deterministic `trace_id` join |
| **G2** | **CLEARED** — 8/8 `eval.goal_judge` rows exported from Langfuse |
| **G4** | **CLEARED** — GCS shadow posture confirmed on GCP `/health` |
| **G5** | **CLEARED** — κ = 1.0 (prior session) |
| **Shadow** | **OPEN** — behavioral gate FAIL; A2 stays PROVISIONAL |

## Next steps (future session)

1. **GJ-012 C1 drift:** Tune [`prompts/goal_judge_system_prompt.j2`](../../prompts/goal_judge_system_prompt.j2) for wrong-verification-tool partial-counted-as-full; re-run `GJ-012` on GCP or local batch.
2. **GJ-010 precision:** Either relax gate tolerance to spec's `≈0.67 (±0.05)` or normalize `⅔ → 0.67` in export/parse path.
3. Re-export → re-run behavioral gate until green.

## References

- GCP batch log: [`goaljudge_stage4_gcp_batch_execution_log.md`](goaljudge_stage4_gcp_batch_execution_log.md)
- Local pass-1 (2/5): [`goaljudge_stage4_local_batch_execution_log.md`](goaljudge_stage4_local_batch_execution_log.md)
- IAA walkthrough (manual eval pins): [`../IAA/goalJudge/goaljudge_stage4_a2_iaa_walkthrough_session_2026-06-09.md`](../IAA/goalJudge/goaljudge_stage4_a2_iaa_walkthrough_session_2026-06-09.md)
- Spec §10.2: [`goaljudge_stage4_a2_rubric_spec.md`](goaljudge_stage4_a2_rubric_spec.md)
