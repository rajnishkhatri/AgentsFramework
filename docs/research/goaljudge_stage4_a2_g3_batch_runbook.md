# GoalJudge Stage 4 — G3 Axis-B Remediation & Batch Re-run Runbook

> **What this is.** An executable walk-through of the
> [Axis-B remediation sequencing](goaljudge_axis_b_remediation_strategy.md#6-recommended-sequencing)
> (steps 1→8), scoped to what the Stage 4 **Confirmation gate** (plan §8.3 / spec §10.2) needs:
> clean Axis-A counts (`gate-remediation`) and the Langfuse trace export that the shadow harness
> replays. It names the **real repo surfaces and commands** so an operator with pipeline access can run
> it end to end.
>
> **Determinism boundary (AGENTS.md H1).** This runbook *describes* live work — it is not run in CI and
> nothing here renders a prompt through anything but `PromptService`. The code/doc artifacts it feeds
> (the verdict-swap loader, the IAA sheets) are committed and green offline; this is the live half that
> turns the §8.3 scaffold into the behavioral gate.
>
> **Why before Stage 4 confirmation, not after.** 18/22 cases carry Axis-B contamination; today's
> Axis-A counts are uninterpretable, so A2's "top mode" lead and the clean/contaminated anchor split
> can't be trusted until B is remediated and the corpus re-run. See remediation §2.1 / §9.

---

## Preconditions

- [ ] `goal_judge_downgrade_enabled` stays **`false`** throughout (this runbook does not flip it — that's Stage 6).
- [ ] Stage 4 PROVISIONAL code is in tree (branch `feat/goaljudge-stage4-a2`): A2 prompt, offline pins, shadow scaffold, verdict-swap loader.
- [ ] `.env` configured: `LANGFUSE_*` keys + `OPENAI_API_KEY` (the batch runner reads these).
- [ ] Outbox relay available: `python -m middleware.sidecars` (the batch script needs it running in another terminal).
- [ ] Security sign-off **secured in advance** for any allowlist/validator change (step 3) — do **not** relax validators for eval convenience (remediation §7).

---

## The sequence (remediation §6, made executable)

Each step: **surface → action → acceptance signal → what it unblocks.** Steps 1–3 are code/adjudication
(land as their own PRs); step 4 is the batch; steps 5–8 re-measure and feed Stage 4.

### Step 1 — B3 mount + B4 terminal-abort (pure cleanup, no security trade-off)

| | |
|---|---|
| **Surface** | `services/tools/file_io.py` (`WORKSPACE_DIR`, currently `os.environ.get("WORKSPACE_DIR", "/workspace")`); Cloud Run volume mount. `components/evaluator.py` `classify_outcome` (`tool_error` vs `terminal`, ~L99–124). |
| **Action** | (B3) Default bare paths under `WORKSPACE_DIR`; mount `/workspace` for the shell tool so `ls /workspace` stops ENOENT-ing. (B4) Classify tool **validation** errors as `tool_error`, not `terminal`, so a recoverable tool failure doesn't pre-emptively abort the ReAct loop (`orchestration/react_loop.py` terminal-abort path). |
| **Acceptance** | `GJ-001A`, `GJ-007`, `GJ-020/021` re-run without a pre-emptive abort; **L2 offline tests stay green** (`pytest tests/ -q`). |
| **Unblocks** | Removes harness noise so steps 4–6 measure agent capability, not env rejection. Pure cleanup — agent capability unchanged (remediation §3.1 / §4 B3, B4). |

### Step 2 — B5 / E1 eval export (telemetry; unblocks Axis C)

| | |
|---|---|
| **Surface** | `services/eval_capture.py` (`record(target=…)`); Langfuse export path. |
| **Action** | Implement E1.1–E1.3: emit `eval.{target}` rows on the Langfuse trace so `target=goal_judge` `per_criterion` rows are visible and joinable. This is the **EC half** the export currently leaves empty. |
| **Acceptance** | `target=goal_judge` rows visible on batch runs; export script EC half populated; `workflow_id`/`trace_id` joinable. |
| **Unblocks** | Without B5/E1, Axis C is unconfirmable and the export is half-empty — **do not skip and jump to the rubric** (remediation §7, §3.6: B5 is the hidden critical path). Also: the populated `ai_response` rows are exactly what the verdict-swap loader consumes (see Handoff). |

### Step 3 — Human adjudication of B1/B2 (confound vs Axis-A vs security)

| | |
|---|---|
| **Surface** | `services/tools/shell.py` — `ALLOWED_COMMANDS = {"ls","cat","head","tail","grep","find","python","wc"}`, `SHELL_METACHARACTERS = frozenset(";&|$\`<>")`. |
| **Action** | Per-case review using remediation §5 (GJ-001–022). **Document the allowlist in agent/prompt guidance** so the agent stops attempting blocked commands. **Do not relax `SHELL_METACHARACTERS`** (shell-injection risk) and **do not widen `ALLOWED_COMMANDS`** before adjudicating B1-vs-Axis-A — widening erases genuine recovery-failure signal (remediation §3.3, §7). Where a command is genuinely blocked, add a **compute workaround** (e.g. the `compute`/delegation path for factorial), not a validator relaxation. |
| **Acceptance** | A written **adjudication log** (one decision per B1/B2 case); security sign-off recorded on any allowlist change. |
| **Unblocks** | Decides which cases are confound (cleanup) vs real Axis-A recovery failures (recode) before they're re-run and re-coded. |

### Step 4 — Batch re-run under a single env posture **← produces the Stage 4 inputs**

| | |
|---|---|
| **Surface** | `scripts/run_goaljudge_synthetic_batch.py` (drives live prompts through the real agent + GoalJudge under `user_id="synthetic-saturation-user"` with deterministic 32-hex trace/task/workflow IDs); `middleware/goaljudge_saturation_bridge.py`. Optional UI path: `frontend/e2e/full-stack/goaljudge-batch.spec.ts` (`cd frontend && npm run test:e2e:t3`). |
| **Run** | In one terminal: `python -m middleware.sidecars`. In another, from the agent root: `python scripts/run_goaljudge_synthetic_batch.py`. Single env posture — same `synthetic-saturation-user`, same mount, same allowlist as adjudicated. |
| **Acceptance** | `workflow_id`/`trace_id` joinable across the corpus; **GJ-010 remains aligned** (the gold reference / post-fix sanity check, remediation §5). |
| **Unblocks** | **This is the step that produces the two Stage 4 inputs:** (a) the Langfuse verdict export for the shadow swap, and (b) the fresh post-G3 traces the IAA sheet's second pass grades. |
| **Caveat** | The UI path is subject to the streaming render gap (spec §8.4) — **persistent-gap cases `GJ-011/014/015` and never-re-run `GJ-003B`** are inadmissible from Playwright capture; use the Langfuse/manual trace as authority for those. |

### Step 5 — Re-open Stage 2 coding on affected cases

| | |
|---|---|
| **Action** | Re-open-code the `†` cases and any case whose **first-failure event** changed after the B fixes (a capability-granting fix can move the first deviation). Do **not** treat post-fix counts as corrections of the June-4 tallies — it's a different agent–environment system (remediation §7, §3.5). |
| **Acceptance** | New open codes logged; saturation gate re-evaluated. |

### Step 6 — Re-axial matrix + counts (the new measurement)

| | |
|---|---|
| **Action** | Rebuild the §6 axial matrix; provisional counts with **reduced** Axis-B contamination. |
| **Acceptance** | ≥N cases now scoring `Counts Axis-A? = Yes`; **A2 lead reconfirmed or revised.** |
| **Unblocks** | This is the `gate-remediation` checklist row and the **Reconfirm A2** precondition of §8.3. If A2 loses top mode here → plan §8.4 rollback (re-pick, open a new Stage 4 plan). |

### Step 7 — Axis-C calibration (now EC-confirmable)

| | |
|---|---|
| **Action** | Confirm J2/J3 on the EC `per_criterion` rows. The pre-rubric C1 drift cases (`GJ-008/012/013`: Langfuse `goal_met=true` vs registry `false`, spec §8.7) are now reproducible against real rows. |
| **Acceptance** | C1 drift reproducible **or** fixed by the A2 prompt — moving those rows to `goal_met=false` is the Stage 4 success signal (spec §10.2 "Current expectation"). |

### Step 8 — Stage 4 rubric confirmation

The A2 prompt section already shipped (PROVISIONAL). With steps 1–7 done, run the two §8.3 checks
(Shadow + Human IAA below). If both pass and G1–G10 are cleared, A2 moves PROVISIONAL → **confirmed**.

---

## Handoff into the Stage 4 confirmation checks

The batch output feeds the two committed §8.3 instruments directly:

### → Shadow run (the verdict swap)

1. From the step-4 run, export the `target=goal_judge` verdicts for the §10.2 anchors (the trace IDs are
   in [spec §"Trace ID reference"](goaljudge_stage4_a2_rubric_spec.md#trace-id-reference-8-anchors)).
   Either form the loader accepts works:
   - **Form A:** `[{"trace_id": "...", "verdict": {…GoalVerdict…}}, …]`
   - **Form B (EvalRecord-shaped):** `[{"trace_id": "...", "target": "goal_judge", "ai_response": {…}}, …]`
2. Save it as `tests/fixtures/goaljudge/langfuse_replay_export.json` (this filename is **git-ignored** —
   it is a real run, not a fixture) or anywhere, and point the env var at it:
   ```bash
   export GOALJUDGE_LANGFUSE_EXPORT=/abs/path/to/langfuse_replay_export.json
   .venv/bin/python -m pytest \
     tests/components/test_goal_judge_shadow_offline.py::TestLangfuseReplaySwapSeam::test_live_export_matches_registry_when_env_set \
     -q
   ```
3. The harness ([`langfuse_replay.py`](../../tests/fixtures/goaljudge/langfuse_replay.py) →
   [`test_goal_judge_shadow_offline.py`](../../tests/components/test_goal_judge_shadow_offline.py)) maps
   `trace_id → registry_id`, replaces the recorded verdict per anchor, and runs the **same §10.2
   assertions** against `case_registry.py` truth (F7). **No test edits** — the swap is the env var.
   Gate pass = `GJ-008/010/012 → goal_met=false (pf 0.0 / 0.67 / 0.67)`, `GJ-001B → true (1.0)`,
   `GJ-019 → false (0.0, must NOT be A2)`. Post-G3 additions `GJ-011/013/003B` follow the same pattern.

### → Human IAA (κ ≥ 0.8)

The fresh post-G3 traces are the second-pass grading set for the
[IAA instrument](goaljudge_stage4_iaa/README.md): graders score `GJ-011/013/003B` (gradable only after
this batch) alongside the five already-gradable anchors, blind, and κ is computed on the `a2_fail`
column. κ ≥ 0.8 on the gate-eligible set is the other §8.3 blocker.

---

## What *not* to do (remediation §7)

| Anti-pattern | Why |
|---|---|
| Relax `SHELL_METACHARACTERS` for eval convenience | Trades measurement for shell-injection risk (Security Model L2). |
| Widen `ALLOWED_COMMANDS` before adjudicating B1 vs Axis-A | Erases genuine recovery-failure signal. |
| Treat post-fix counts as corrections of the June-4 tallies | Different agent–environment system after capability-granting fixes. |
| Skip B5/E1 and jump to the rubric | Axis C unconfirmable; export half-empty; the verdict swap has nothing to consume. |
| Skip the Stage-2 re-open after B fixes | `†` cases and changed first-failure events invalidate the per-case matrix. |

---

## References

| Document | Path |
|---|---|
| Axis-B remediation strategy (§4 mapping, §5 per-case, §6 sequencing) | [`goaljudge_axis_b_remediation_strategy.md`](goaljudge_axis_b_remediation_strategy.md) |
| Stage 4 plan (§8.3 Confirmation gate, §8.4 rollback) | [`../plans/goaljudge_stage4_a2_rubric.plan.md`](../plans/goaljudge_stage4_a2_rubric.plan.md) |
| Stage 4 spec (§8 anchors + trace IDs, §10.2 shadow table) | [`goaljudge_stage4_a2_rubric_spec.md`](goaljudge_stage4_a2_rubric_spec.md) |
| Verdict-swap loader | [`../../tests/fixtures/goaljudge/langfuse_replay.py`](../../tests/fixtures/goaljudge/langfuse_replay.py) |
| Human IAA instrument | [`goaljudge_stage4_iaa/README.md`](goaljudge_stage4_iaa/README.md) |
| Batch runner | [`../../scripts/run_goaljudge_synthetic_batch.py`](../../scripts/run_goaljudge_synthetic_batch.py) |
