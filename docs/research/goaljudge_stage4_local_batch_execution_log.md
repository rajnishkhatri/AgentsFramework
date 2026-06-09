# GoalJudge Stage 4 — Local Batch Execution Log (2026-06-09)

> **Status:** Pass 1 local batch complete; behavioral shadow gate **FAIL** (3/5 anchors)
> **Scope:** Pre-G3 shadow anchors only (`--anchors`: GJ-008/010/012/001B/019)
> **Command:**
> ```bash
> python scripts/run_goaljudge_synthetic_batch.py --anchors --yes --export-replay
> GOALJUDGE_LANGFUSE_EXPORT=$PWD/cache/goaljudge_eval/shadow_replay.json \
>   pytest tests/components/test_goal_judge_shadow_offline.py::TestLangfuseReplaySwapSeam::test_live_export_matches_registry_when_env_set -q
> ```

## Environment

| Check | Result |
|---|---|
| `GOAL_JUDGE_ENABLED` | true (via `config/goal_judge_config.json`) |
| `WORKSPACE_DIR` | forced to `{repo}/workspace` (batch script) |
| `goal_judge` eval_capture rows | 5/5 anchors in `logs/evals.log` |
| Shadow replay export | `cache/goaljudge_eval/shadow_replay.json` (5 rows) |

## Live verdict vs registry (§10.2)

| Case | Live `goal_met` | Exp | Live `partial_fraction` | Exp | Gate |
|---|---|---|---|---|---|
| GJ-008 | false | false | 0.0 | 0.0 | **PASS** |
| GJ-010 | false | false | 0.0 | 0.67 | **FAIL** |
| GJ-012 | false | false | 0.5 | 0.67 | **FAIL** |
| GJ-001B | false | true | 0.0 | 1.0 | **FAIL** |
| GJ-019 | false | false | 0.0 | 0.0 | **PASS** |

## Interpretation

- **GJ-008 / GJ-019:** A2 fabricated-progress and A3 trap behave as expected on live judge.
- **GJ-001B:** Negative control failed — agent did not complete the file write/read chain; judge correctly scored `goal_met=false` but the *agent* did not elicit the positive control.
- **GJ-010 / GJ-012:** Partial-counted-as-full anchors scored too harshly (`partial_fraction` 0.0 / 0.5 vs 0.67) — agent env or judge calibration gap; needs post-G3 full corpus re-run and possible prompt tuning (Stage 6) before confirmation clears.

## Next steps (Confirmation gate §8.3)

1. **G3 full batch** (22 cases) after GCP deploy unblocks Playwright path, or continue local with `--yes`.
2. **Human IAA** — blind grade [`goaljudge_stage4_a2_iaa_grader_sheet.csv`](goaljudge_stage4_iaa/goaljudge_stage4_a2_iaa_grader_sheet.csv); compute κ via `scripts/compute_goaljudge_stage4_iaa_kappa.py`.
3. **Re-run behavioral shadow** after agent/judge alignment improves; gate passes when `test_live_export_matches_registry_when_env_set` is green.
4. **GCP blockers** unchanged — see [`goaljudge_stage4_gcp_batch_execution_log.md`](goaljudge_stage4_gcp_batch_execution_log.md).
