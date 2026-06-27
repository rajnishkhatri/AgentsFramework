---
type: plan
title: 'Live-LLM E2E Validation of the F1–F7 Tool-Calling Fixes (localhost)'
description: 'Drive per-fix probe prompts through the real chat UI against a live model on localhost; reconcile DOM capture against BlackBox carriers + Langfuse spans.'
status: planned
tags: [plan, e2e, tool-calling, validation, langfuse, playwright]
---

# Plan — Live-LLM E2E Validation of the F1–F7 Tool-Calling Fixes (localhost)

> The F1–F7 *implementation* is DONE and committed (`53e7927`, `0f31187`); its progress
> log is archived in the memory note `toolcalling-f1-f7-fix-workstream`. THIS plan is the
> **validation** workstream: prove the seven fixes change real agent behavior end-to-end
> against a **live LLM**, on **localhost**, with **per-fix provider pinning** and **Langfuse
> trace-reasoning analysis**.

## Context

The F1–F7 fixes are verified by unit/sim tests (full suite 3974 green) but **not yet by
evidence** — we know the contracts hold, not that the fixes land in production behavior.
Each fix was motivated by a real corpus failure (masked validation, hallucinated tools,
corrupt success, the GLM `user`-less rejection, the 73-call cascade). This plan drives a
small set of **fix-probe prompts** — each engineered to trigger exactly one fix's seam —
through the **real chat UI against a live model on localhost**, then reconciles the DOM
capture against **BlackBox carriers + Langfuse spans** to confirm the expected signal
appeared (and the old failure did not).

We reuse the existing, mature T3 batch harness rather than inventing one. The pattern is
already proven by [`goaljudge-batch.spec.ts`](../../frontend/e2e/full-stack/goaljudge-batch.spec.ts):
a registry of cases → real composer injection → deterministic `gj:{id}:{trace_id}` thread
bridge → JSONL capture → `verify_run.py` reconciliation → Langfuse trace fetch by
`workflow_id`. We add a **fix-probe registry** + a **fix-probe spec** + a **carrier-assertion
analyzer**, mirroring those three components one-for-one.

Methodology binding: `docs/skills/playwright-agentic-e2e/SKILL.md` (T3 = full-stack live
model; assert structure/provenance not prose; settle-poll not `finished()`; verify
server-side) and the workspace skill `docs/skills/agentsframework-playwright/SKILL.md`
(exact selectors, auth, gotchas FE-AP-5/7, thread bridge).

## Decisions (locked with the user)

- **Target:** localhost backend (Python middleware on :8000) + Next.js dev (:3000), live LLM.
- **Providers:** multi-provider, **pinned per fix** via `pinned_model` input key + the right
  `MODEL_PROFILE_SET` — GLM/Z.ai for F7 (the provider that actually *rejects* the malformed
  shape), DeepSeek for F3 (the real hallucinated-tool offender), default profile for F1/F2/F6.
- **Corpus:** focused fix-probe subset (~8–12 prompts), each a named probe for one fix.

## The fix → probe → observable-carrier matrix

Every probe asserts a **positive carrier** (the fix's signal appeared) AND, where possible, a
**negative control** (the pre-fix failure did NOT happen). Carriers verified in source by
exploration; file:line anchors below.

| Probe | Fix | Prompt seam | Provider pin | Positive carrier (BlackBox → Langfuse) | Negative control |
|---|---|---|---|---|---|
| **P-F1-path** | F1 | "read the file `/etc/passwd`" (outside workspace boundary) | default | `ERROR_OCCURRED.details.error_class == "validation"` (react_loop ~538; classifier ~321) | not `"tool_reported"` |
| **P-F1b-shell** | F1b | "run `rm -rf /`" (blocked command) | default | `error_class == "validation"` on shell | — |
| **P-F1b-timeout** | F1b | a command that exceeds the shell timeout | default | `error_class == "timeout"` | not `validation` |
| **P-F2-repair** | F2 | malformed-args call that should self-repair next turn | default | tool output contains marker `"[tool-call rejected: invalid arguments"` (`_repair_hint` ~355); run then **succeeds** (no give-up loop) | run does not terminate on repeat-failure |
| **P-F3-halluc** | F3/F4 | task that makes the model reach for a non-existent tool (e.g. `read` vs `read_file`) | **DeepSeek** | `error_class == "unknown_tool"` + tool output contains `"is not a registered tool"` / `"The available tools are:"` (`_unknown_tool_nudge` ~375) | model does NOT loop the invented name ≥3× |
| **P-F6-empty** | F6 | task whose trajectory has substance but final answer is empty | default | `TASK_COMPLETED.details.goal_met == false` & `criteria_met == 0.0` (evaluator.py:349) | outcome ≠ "success" |
| **P-F7-multiturn** | F7a | a **2-turn** exchange (turn 1 uses a tool, turn 2 follow-up) | **GLM/Z.ai** | turn-2 completes; **no** `last_llm_error` user-message rejection; run outcome not "rejected" | (pre-fix: GLM 400 on turn 2) |
| **P-F7-cascade** | F7b | multi-turn where a mid-convo LLM error occurs | GLM/Z.ai | `ERROR_OCCURRED(source=llm_call)` recorded **once**; persisted `messages` has **no** AIMessage carrying the raw error text | no consecutive-assistant pile-up / no 73-call thrash |

> F7a/F7b are the hardest: their primary signal is the **absence** of a failure. The probe
> asserts (a) the run reaches a turn-2 answer at all, and (b) cross-checks Langfuse that the
> turn-2 `llm.call` span has no provider-rejection error. If GLM infra/keys are unavailable
> locally (see Risks), P-F7 degrades to a documented SKIP with the reason recorded — never a
> silent pass.

## Approach — three new artifacts mirroring the GoalJudge batch trio

### 1. Fix-probe registry — `frontend/e2e/fixtures/fix_probes.ts`
A typed array mirroring `GoalJudgeRegistryCase`, with the probe-specific fields the analyzer
needs: `id`, `prompt`, `fix` (`"F1"|"F1b"|"F2"|"F3"|"F6"|"F7a"|"F7b"`), `pinned_model`,
`expected_error_class?`, `expected_marker?` (string the tool output must contain),
`expected_goal_met?`, `negative_control?`, plus the `trace_id`/`session_id` join keys (minted
the same deterministic way the GoalJudge registry mints them — reuse that generator). Source
the prompts from the corpus memos (`STAGE5_root_cause_report.md` §6 exemplars) so each probe
reproduces a *real* observed failure, not a synthetic one.

### 2. Fix-probe spec — `frontend/e2e/full-stack/fix-probes.spec.ts`
Copy `goaljudge-batch.spec.ts` almost verbatim and adapt:
- Reuse the `installGoalJudgeThreadBridge` shape for the `gj:`-style thread id (rename to a
  probe bridge; keep the FE-AP-7 no-client-`trace_id` guard).
- **Add `pinned_model` to the outbound body** in the bridge (the route rewrite already edits
  the POST body — set `body.pinned_model = caseRow.pinned_model` there). This is the one
  mechanical addition vs the GoalJudge spec.
- Reuse `sendMessage` / `waitForResponse` (settle-poll) / `waitForComposerReady` from
  `e2e/fixtures/helpers.ts` and the `article div[aria-live='polite']` selector (FE-AP-5).
- For P-F7 multi-turn: send turn 1, settle, then send turn 2 in the **same thread** (do NOT
  click New chat between turns) so `state["messages"]` is non-empty on turn 2 — the exact
  condition F7 targets.
- Capture JSONL rows (extend the schema with `fix`, `pinned_model`, `tool_card_count`, and the
  raw streamed `tool_output` text so the analyzer can grep the F2/F3 markers) to
  `cache/fix_probe_eval/ui_batch.jsonl`; screenshots alongside.
- Gate: `test.skip(MOCK_MIDDLEWARE === "1")`; per-probe `test.skip` if its required provider
  pin is unavailable (env probe), recording the skip reason.

### 3. Carrier-assertion analyzer — `scripts/analyze_fix_probes.py`
Reuse the Langfuse-by-`workflow_id` resolution already written in
[`analyze_planning_traces.py`](../../scripts/analyze_planning_traces.py) (it maps
`gj:{id}:{trace_id}` → backend `workflow_id` → Langfuse trace, ~lines 827–858) and the
BlackBox-reading + status-prefix-strip helpers from
[`verify_run.py`](../skills/playwright-agentic-e2e/scripts/verify_run.py). For each probe
row: load the BlackBox recording (`cache/.../black_box_recordings`) + the Langfuse trace, then
assert that probe's expected carrier from the matrix (error_class string, the goal_met/
criteria_met pair, or the marker substring in the tool message), and that the negative control
did NOT fire. Emit a per-probe PASS/FAIL/SKIP scorecard (mirror the governance-trace-audit
report shape). `error_class` survives redaction (verified — preserved as a string in
`black_box_publisher.py`).

**Do NOT build a new Langfuse client** — reuse `scripts/langfuse_dataset_client.py` / the fetch
pattern in `analyze_planning_traces.py`. **Do NOT build a new trace reconciler** — extend
`verify_run.py`'s loader.

## Critical files

| Purpose | Path |
|---|---|
| New: fix-probe registry (prompts + expected carriers) | `frontend/e2e/fixtures/fix_probes.ts` |
| New: fix-probe T3 spec (multi-turn + pinned_model bridge) | `frontend/e2e/full-stack/fix-probes.spec.ts` |
| New: carrier-assertion analyzer + scorecard | `scripts/analyze_fix_probes.py` |
| Reuse: thread-bridge + capture pattern | `frontend/e2e/full-stack/goaljudge-batch.spec.ts` |
| Reuse: registry shape + deterministic id mint | `frontend/e2e/fixtures/goaljudge_registry.ts` |
| Reuse: composer/settle helpers + selectors | `frontend/e2e/fixtures/helpers.ts` |
| Reuse: Langfuse-by-workflow_id resolver | `scripts/analyze_planning_traces.py` ~827 |
| Reuse: JSONL loader + status-strip + uuid5 check | `docs/skills/playwright-agentic-e2e/scripts/verify_run.py` |
| Carrier source of truth (error_class stamp) | `orchestration/react_loop.py:538` ; classifier ~321 |
| Repair hint / nudge markers | `_repair_hint` ~355, `_unknown_tool_nudge` ~375 (react_loop.py) |
| F6 empty-answer floor | `components/evaluator.py:349` |
| Provider profile sets + pin | `services/llm_config.py` (`MODEL_PROFILE_SET`); `pinned_model` input key |
| Relay export (error_class → Langfuse span) | `middleware/sidecars/black_box_to_telemetry.py` |

## Verification (how we run it end-to-end)

```bash
# 0. Backend up locally with all provider pins available.
#    (.venv/bin/python is the only working interpreter.)
export MODEL_PROFILE_SET=all            # so GLM + DeepSeek + default all resolve
#    + provider keys in env: OPENAI/ANTHROPIC, DEEPSEEK_API_KEY, ZAI/GLM key
#    start middleware on :8000  (per workspace skill local-dev section)

# 1. Frontend dev server (auto-started by playwright webServer when BASE_URL is local)
cd frontend && pnpm install
export BASE_URL=http://localhost:3000
export E2E_FAKE_SESSION=1               # local-only authed session (workspace skill)
export WORKOS_COOKIE_PASSWORD=<32+ chars from .env>
export MIDDLEWARE_URL=http://localhost:8000

# 2. Smoke a single probe first (cache warm, selectors valid):
FIX_PROBE_FILTER=P-F1-path pnpm exec playwright test e2e/full-stack/fix-probes.spec.ts \
  --project=chromium-desktop

# 3. Full fix-probe batch (live LLM, ~8–12 probes):
pnpm exec playwright test e2e/full-stack/fix-probes.spec.ts --project=chromium-desktop

# 4. Reconcile DOM capture vs BlackBox + Langfuse carriers → per-fix scorecard:
.venv/bin/python scripts/analyze_fix_probes.py \
  --jsonl ../cache/fix_probe_eval/ui_batch.jsonl \
  --recordings ../cache/.../black_box_recordings \
  --langfuse                                  # fetch + assert spans
```

**Pass criteria:** every probe row reaches a settled answer; the analyzer reports the expected
positive carrier for each fix AND the negative control absent; F7 probes either PASS on GLM or
record a documented SKIP (provider unavailable) — never a silent pass. Output is a scorecard
table (probe → fix → carrier-asserted → verdict) plus the JSONL + screenshots as evidence.

## Risks / guardrails

- **GLM/Z.ai + DeepSeek local infra.** Per memory, the DeepSeek key has **zero GCP infra**
  (pins 401 against deployed infra) and GLM routing needs the `glm` profile present. Locally
  this depends on direct-provider keys + the LiteLLM direct-call extension. **Pre-flight:** the
  spec env-probes each pinned provider and SKIPs (with reason) rather than failing the batch if
  a provider can't be reached. F1/F2/F6 (default provider) always run.
- **Live-LLM non-determinism.** Assert structure/carriers, never exact prose (skill rule;
  TAP-3). The probes target *deterministic seams* (a boundary-violating path is always
  `validation`), so the carriers are stable even though the prose isn't.
- **Don't overwrite GoalJudge config / no git stash** (workspace gotchas #8, #9) — this plan
  adds files only; it never mutates `goal_judge_config.json` or stashes.
- **Cost/time.** ~8–12 live runs × ~1 model call each; cheap. On-demand only, never CI.
- **Scope:** this is the plan's "fix-impact spot-check" realized as a repeatable suite; the
  heavier full **Stage-7 corpus re-coding** (re-measure A4/A5 collapse on all 56 cases) remains
  a separate later workstream and is explicitly out of scope here.
