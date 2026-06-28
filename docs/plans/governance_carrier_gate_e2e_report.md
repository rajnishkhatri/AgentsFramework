---
type: plan
title: 'Carrier-gate E2E validation — report'
description: 'Status: validation report — 2026-06-17.'
tags: [plan]
---

# Carrier-gate E2E validation — report

**Status:** validation report — **2026-06-17**. Generated from a live T3 run against the deployed prod stack.
**Plan:** [`governance_carrier_gate_e2e_validation.plan.md`](governance_carrier_gate_e2e_validation.plan.md).
**Verdict:** ✅ **CLEAN** — the shadow carrier gate emits at every wired phase, the carriers export to Langfuse with parseable details, the batch gap rate is **0.000**, and every run completed (no-block invariant holds).

---

## 1. Run parameters

| | |
|---|---|
| Target | prod frontend `https://agent-frontend-w65nrxwkiq-uc.a.run.app` (`TEST_PROFILE=prod`) |
| Why prod (not a stress revision) | the carrier gate is **unconditional** — no loops-on flag — so it fires on every normal run; no tagged revision needed |
| Driver | `frontend/e2e/full-stack/carrier-gate.spec.ts` (5 generic cases, fresh `trace_id`/run) |
| Analyzer | `scripts/analyze_planning_traces.py --source langfuse --carrier-gate` |
| Cases | 3 plain-answer + 2 tool-using (TOOL_EXECUTION coverage) |
| DOM result | 5/5 passed (non-empty answer rendered) — proves the no-block invariant in prod |

Captured trace_ids (one Langfuse trace per run — fresh id, no superposition):

| case | tool | resp chars | tool cards | trace_id |
|------|------|-----------:|-----------:|----------|
| carrier-plain-capital | no | 31 | 0 | `d85335e8…` |
| carrier-plain-explain | no | 281 | 0 | `efc877f7…` |
| carrier-tool-write | yes | 81 | 1 | `e4b639eb…` |
| carrier-tool-multi | yes | 171 | 2 | `8dfe8411…` |
| carrier-multistep | no | 607 | 0 | `b3132906…` |

---

## 2. Per-phase carrier scorecard (from Langfuse)

| Wired phase | Pillar | Carriers emitted | pass | alert |
|-------------|--------|-----------------:|-----:|------:|
| `initialization` | Identity | 5 | 5 | 0 |
| `routing` | Reasoning | 8 | 8 | 0 |
| `model_invocation` | Recording | 8 | 8 | 0 |
| `output_validation` | Validation | 8 | 8 | 0 |
| `tool_execution` | Validation (conditional) | 3 | 3 | 0 |
| **total** | | **32** | **32** | **0** |

**Gap rate: 0.000 — VERDICT: CLEAN.**

### Why the counts differ (and why that is correct)
- `initialization` = **5** (once per run — the init node runs once; resumed runs short-circuit it).
- `routing` / `model_invocation` / `output_validation` = **8** each — these fire **per ReAct step**, so the multi-step + tool prompts looped more than once (5 runs → 8 step-cycles). They move in lockstep because they share the loop body. ✓
- `tool_execution` = **3** — fired only where a tool actually ran (the conditional Validation pillar): `carrier-tool-multi` drove 2 (write+read, matching its 2 tool cards) and `carrier-tool-write` drove 1. A no-tool run correctly records nothing here — not a gap. ✓

Per-case carrier totals (from the traces below): 4 + 4 + 8 + 12 + 4 = **32**, matching the scorecard.

---

## 3. Case-by-case walkthrough

Each case: the prompt sent, the rendered answer, the Langfuse reasoning trace (routing/depth/model/tools/verdict), and the per-phase carrier-gate carriers. All values are pulled from the live trace — nothing reconstructed. Carrier counts track `step_count` exactly (the routing/model/output trio fires once per ReAct step).

### 3.1 `carrier-plain-capital` — 1 step, L0, no tool
- **Prompt:** *"What is the capital of France? Answer in one sentence."*
- **Output:** *"The capital of France is Paris."* (31 chars)
- **Trace** `d85335e8…` — `step_count=1`, latency 5.8s.
  - **Reasoning:** `step.planned` depth **L0** (single-action — correct); `model.selected` → **gpt-4o**, reason `capable-for-planning` (*"step=0, errors=0, cost_usd=0.0000, plan_depth=L0"*); 1 `llm.call`; goal-judge **goal_met=true / criteria_met=1**; `task.completed` outcome **success**.
  - **Carrier gate (4, all pass):** `initialization` · `routing` · `model_invocation` · `output_validation`. No `tool_execution` (no tool) — a correct legitimate skip, not a gap.
- **Screenshot:** [`carrier-plain-capital.png`](../../cache/carrier_gate/screenshots/carrier-plain-capital.png)

### 3.2 `carrier-plain-explain` — 1 step, L0, no tool
- **Prompt:** *"Briefly explain what a hash chain is, in two sentences."*
- **Output:** *"A hash chain is a sequence of hash values where each hash is derived from the previous one… altering any part of the chain would require recalculating all subsequent hashes."* (281 chars)
- **Trace** `efc877f7…` — `step_count=1`, latency 5.9s.
  - **Reasoning:** depth **L0**; `model.selected` → **gpt-4o** `capable-for-planning`; 1 `llm.call`; goal-judge **goal_met=true**; outcome **success**.
  - **Carrier gate (4, all pass):** init/routing/model/output. No tool (correct).
- **Screenshot:** [`carrier-plain-explain.png`](../../cache/carrier_gate/screenshots/carrier-plain-explain.png)

### 3.3 `carrier-tool-write` — 2 steps, L0, 1 tool
- **Prompt:** *"Create a file named notes.txt containing the text 'hello carrier gate', then tell me you have created it."*
- **Output:** *"I have created the file named notes.txt containing the text 'hello carrier gate'."* (81 chars, 1 tool card)
- **Trace** `e4b639eb…` — `step_count=2`, latency 6.8s.
  - **Reasoning:** depth **L0**; **step 0** `model.selected` → **gpt-4o** `capable-for-planning` (the planning step); **step 1** → **gpt-4o-mini** `steady-state-fast` (*"step=1, cost_usd=0.0068"* — the cost-aware downgrade to the fast tier once the plan is set). 1 `tool.file_io` (the write), 2 `llm.call`, 2 `step.executed`. goal-judge **goal_met=true**; outcome **success**.
  - **Carrier gate (8, all pass):** init ×1 + routing/model/output ×2 (one per step) + `tool_execution` ×1 (the write). The Validation pillar fired exactly where the tool ran.
- **Screenshot:** [`carrier-tool-write.png`](../../cache/carrier_gate/screenshots/carrier-tool-write.png)

### 3.4 `carrier-tool-multi` — 3 steps, L1, 2 tools
- **Prompt:** *"Write a file plan.txt with three short lines, then read it back and summarize what it contains."*
- **Output:** *"The file plan.txt contains the following lines: Finish the report / Call the client / Schedule a meeting. This summarizes a short to-do list with three tasks…"* (171 chars, 2 tool cards)
- **Trace** `8dfe8411…` — `step_count=3`, latency 8.3s.
  - **Reasoning:** depth **L1** (the genuinely two-action write→read→summarize task — correctly deeper than the single-action cases); `model.selected` → **gpt-4o** `capable-for-planning` at step 0, then **gpt-4o-mini** `steady-state-fast` at steps 1 & 2. **2 `tool.file_io`** (write `/workspace/plan.txt` 61 bytes, then read it back — visible in the screenshot's two `file_io completed` cards), 3 `llm.call`, 3 `step.executed`. goal-judge **goal_met=true**; outcome **success**.
  - **Carrier gate (12, all pass):** init ×1 + routing/model/output ×3 (one per step) + `tool_execution` ×2 (write + read). Both tool boundaries surfaced their Validation carrier.
- **Screenshot:** [`carrier-tool-multi.png`](../../cache/carrier_gate/screenshots/carrier-tool-multi.png) — shows the task-understanding card, both `file_io` cards (input/output JSON), and the `gpt-4o-mini step 2 · evaluation` final answer.

### 3.5 `carrier-multistep` — 1 step, L1, no tool
- **Prompt:** *"List three benefits of deterministic governance checks, then pick the single most important one and explain why in one sentence."*
- **Output:** lists Consistency / Transparency / Efficiency, then picks **Consistency** as most important *"…applying the same standards to all cases, thereby building trust in the system."* (607 chars)
- **Trace** `b3132906…` — `step_count=1`, latency 8.1s.
  - **Reasoning:** depth **L1** (the "list-then-select" two-part instruction — correctly L1 not L0, even though it ran in one step since no tool was needed); `model.selected` → **gpt-4o** `capable-for-planning`; 1 `llm.call`; goal-judge **goal_met=true**; outcome **success**.
  - **Carrier gate (4, all pass):** init/routing/model/output. No tool (correct).
- **Screenshot:** [`carrier-multistep.png`](../../cache/carrier_gate/screenshots/carrier-multistep.png)

### Cross-case observations
- **Depth scorer behaved sensibly:** single-action factual asks → **L0** (901, 902); multi-clause / multi-action asks → **L1** (904, 905). This is the deterministic planning floor doing its job in the same traces — orthogonal to the gate, but reassuring.
- **Routing showed the cost-aware tier ladder:** every run plans on **gpt-4o** (`capable-for-planning`) then drops to **gpt-4o-mini** (`steady-state-fast`) on subsequent steps — the Reasoning-pillar `model.selected` rationale makes this auditable from the trace alone.
- **The COMPLETION pillar carrier IS present** (`eval.goal_judge`, all `goal_met=true`) even though the carrier gate deliberately does **not** check COMPLETION (its verdict lives in the eval-overlay sink, not the black box — impl §build-log). So the pillar is *covered in the trace*; it's just not *inline-gated* yet. That gap is a known, deliberate Phase-2 item, not a defect surfaced here.

---

## 4. Acceptance (plan §6) — all met

| Criterion | Result |
|-----------|--------|
| **Emission** — ≥1 carrier per wired phase that ran | ✅ all 4 always-wired phases on every run; TOOL_EXECUTION on the tool runs |
| **Relay fidelity (§4a)** — `details` survive with usable types | ✅ `source`/`phase`/`outcome` read clean; the analyzer's `_as_list` parses the stringified `missing_pillars`; verified on the pre-flight trace before the full batch |
| **Level fidelity (§4b)** — a gap would relay at WARNING, not DEBUG | ✅ fix landed pre-deploy (`_level_for`); no alert occurred to surface, but the path is proven by the publisher L2 tests |
| **Calibration verdict** — per-phase gap rate computed | ✅ 0.000, CLEAN |
| **No-block** — every run rendered an answer regardless of gap | ✅ 5/5 DOM pass |
| **Reproducible** — fresh trace_id/run; re-running the analyzer on the same JSONL is stable | ✅ one trace == one run |

---

## 5. What this establishes for Phase 2

The §5 exit criterion was: *"a real run-corpus shows the missing-carrier rate is true signal, not false-positive on legitimate phase-skips."* This run establishes the **healthy-traffic baseline = 0.000 gap rate** with full coverage — the warn signal is quiet when it should be quiet, and the legitimate skips (resumed-init, no-tool TOOL_EXECUTION) correctly produce no gap (no false-positives).

**This does NOT yet prove the gate *catches* a gap live** — by design (plan CE-4): the L2 failure-mode matrix proves detection deterministically offline, and forcing a live seam defect risks polluting the baseline. A fault-injection live test is the natural **next** calibration step before any Phase-2 enforce decision.

## 6. Fault-injection (the live gap-catch proof) — BUILT 2026-06-17

The hook is now built and proven through the real graph (offline sim) — pending a live tagged-revision run.

- **Mechanism** (mirrors `FANOUT_FAULT_INJECT`): `AgentConfig.carrier_gate_fault_inject` (env `CARRIER_GATE_FAULT_INJECT`, default OFF, prod-forbidden) + a magic token `__DROP_CARRIER:<phase>__` in the prompt. When armed, the named phase's required carrier is **dropped before the gate checks it** — simulating the exact seam defect, so the gate produces a real gap and the enforce path (`source:"carrier_gate_enforce"`, `outcome:"alert"`, WARNING in Langfuse) fires end-to-end. The token is **inert without the flag** (prod safety).
- **Proven offline through `build_graph`:** `test_fault_injection_degrade_alerts_end_to_end_through_the_graph` — fault token + `degrade` mode → an INITIALIZATION enforce alert carrier appears AND the run still completes (degrade never blocks).
- **Live run procedure** (a tagged validation revision, like the planning-stress §Tiered-Loops pattern — never on prod traffic):
  ```bash
  # Deploy a zero-traffic --tag revision with the fault + enforce flags ON:
  gcloud run services update agent-backend-combined --region us-central1 \
    --image "$IMG" --tag cgfault --no-traffic \
    --update-env-vars CARRIER_GATE_FAULT_INJECT=1,CARRIER_GATE_ENFORCE_ENABLED=1
  # (prod stays degrade; a dev/local AGENT_ENV revision would raise instead)
  # Drive a prompt carrying __DROP_CARRIER:initialization__, then:
  python scripts/analyze_planning_traces.py --source langfuse --carrier-gate \
    --jsonl cache/carrier_gate/ui_batch.jsonl
  #   → expect: total_alerts ≥ 1, ENFORCED ≥ 1 (the "alarm rang" line)
  # Tear down the tag afterward (remove-tags cgfault).
  ```
- The analyzer now surfaces an **`ENFORCED`** line (`source:"carrier_gate_enforce"` count + per-case detail) distinct from the shadow gap-rate, so a fault run shows the alarm explicitly.

---

*Validation. Phase 2 (enforce) is BUILT but ships dark — flipping it ON still needs a live fault-injection run + N-run shadow FP≈0 + explicit approval.*
