# Carrier-gate post-deploy walkthrough — case-by-case report

**Status:** validation walkthrough — **2026-06-17** (post-GCP deploy).
**Plan:** [`governance_carrier_gate_e2e_validation.plan.md`](governance_carrier_gate_e2e_validation.plan.md).
**Deploy guide:** [`governance_carrier_gate_gcp_deploy.md`](governance_carrier_gate_gcp_deploy.md) — Posture A (shadow).
**Batch verdict:** ✅ **CLEAN** — 32 carriers, 0 alerts, gap rate **0.000**, 5/5 DOM pass.

This report is the **post-deploy** re-validation run against revision `agent-backend-combined-00075-8js` (commit `2386660`, deploy id `tierA-prod-2026.06.0-2386660`). Each section pulls live Langfuse trace data — nothing reconstructed.

---

## 1. Run parameters

| | |
|---|---|
| Target | prod frontend `https://agent-frontend-w65nrxwkiq-uc.a.run.app` (`TEST_PROFILE=prod`) |
| Backend revision | `agent-backend-combined-00075-8js` |
| Posture | **A — shadow** (`CARRIER_GATE_ENFORCE_ENABLED` unset, `CARRIER_GATE_FAULT_INJECT` unset) |
| Driver | `frontend/e2e/full-stack/carrier-gate.spec.ts` |
| Analyzer | `scripts/analyze_planning_traces.py --source langfuse --carrier-gate` |
| Artifact | [`cache/carrier_gate/ui_batch.jsonl`](../../cache/carrier_gate/ui_batch.jsonl) |
| Langfuse project | `https://cloud.langfuse.com` |

### Batch summary

| Metric | Expected | Actual | Match |
|--------|----------|--------|-------|
| DOM cases passed | 5/5 non-empty answer | 5/5 pass | ✅ |
| Total carriers | ≥ 28 (4×3 plain + 8 + 12 tool runs) | **32** | ✅ |
| Total alerts | 0 (healthy traffic) | **0** | ✅ |
| Gap rate | 0.000 | **0.000** | ✅ |
| Enforced events | 0 (shadow only) | **0** | ✅ |
| Analyzer verdict | CLEAN | **CLEAN** | ✅ |

Per-case carrier totals: **4 + 4 + 8 + 12 + 4 = 32**.

---

## 2. Per-phase carrier scorecard

| Wired phase | Pillar | Carriers emitted | pass | alert |
|-------------|--------|-----------------:|-----:|------:|
| `initialization` | Identity | 5 | 5 | 0 |
| `routing` | Reasoning | 8 | 8 | 0 |
| `model_invocation` | Recording | 8 | 8 | 0 |
| `output_validation` | Validation | 8 | 8 | 0 |
| `tool_execution` | Validation (conditional) | 3 | 3 | 0 |
| **total** | | **32** | **32** | **0** |

---

## 3. Case-by-case walkthrough

Legend for **Expected vs Actual** tables:

- **DOM** — Playwright assertion: non-empty streamed answer rendered.
- **Tool cards** — UI tool-card count; tool cases expect ≥ 1.
- **Carriers** — per-run `guardrail_checked` events with `source:"carrier_gate"`, all `outcome:"pass"`.
- **Alerts** — any carrier with missing pillars (gap); expect 0 on healthy traffic.
- **No-block** — run completes and renders an answer even if a gap were present (shadow mode never blocks).

---

### 3.1 `carrier-plain-capital` — 1 step, L0, no tool

| Field | Value |
|-------|-------|
| **gj_id** | `GJ-STRESS-901` |
| **trace_id** | [`b494b0a046a4dea7dda801e7dd119c0d`](https://cloud.langfuse.com/trace/b494b0a046a4dea7dda801e7dd119c0d) |
| **Screenshot** | [`carrier-plain-capital.png`](../../cache/carrier_gate/screenshots/carrier-plain-capital.png) |
| **UI latency** | 31.3s |

**Prompt:** *"What is the capital of France? Answer in one sentence."*

**Rendered output:** *"The capital of France is Paris."* (31 chars)

#### Expected vs actual

| Check | Expected | Actual | |
|-------|----------|--------|---|
| DOM outcome | `pass`, non-empty answer | `pass`, 31 chars | ✅ |
| Tool cards | 0 (no tool prompt) | 0 | ✅ |
| Planning depth | L0 (single factual ask) | **L0** | ✅ |
| Steps executed | 1 | 1 | ✅ |
| LLM calls | ≥ 1 | 1 | ✅ |
| Model (step 0) | gpt-4o `capable-for-planning` | gpt-4o `capable-for-planning` | ✅ |
| Goal judge | `goal_met=true` | `goal_met=true`, `criteria_met=1` | ✅ |
| Task outcome | `success` | `success` | ✅ |
| Carrier phases | init · routing · model · output (4) | init · routing · model · output (4) | ✅ |
| `tool_execution` carrier | absent (no tool — legitimate skip) | absent | ✅ |
| Alerts | 0 | 0 | ✅ |
| No-block | answer rendered | answer rendered | ✅ |

#### Langfuse reasoning trace

- **`step.planned`** — depth **L0** (single-action factual ask).
- **`model.selected`** (step 0) → **gpt-4o**, reason `capable-for-planning` (*"step=0, errors=0, cost_usd=0.0000, plan_depth=L0"*).
- **1× `llm.call`**, **1× `step.executed`**.
- **`eval.goal_judge`** — `goal_met=true`, `criteria_met=1`.
- **`task.completed`** — outcome **success**.

#### Carrier gate (4, all pass)

`initialization` · `routing` · `model_invocation` · `output_validation` — each `outcome:"pass"`, `missing_pillars:[]`. No `tool_execution` (correct — no tool ran).

---

### 3.2 `carrier-plain-explain` — 1 step, L0, no tool

| Field | Value |
|-------|-------|
| **gj_id** | `GJ-STRESS-902` |
| **trace_id** | [`3eb6102bb3b9e8c1d7fa7fc05ea248b5`](https://cloud.langfuse.com/trace/3eb6102bb3b9e8c1d7fa7fc05ea248b5) |
| **Screenshot** | [`carrier-plain-explain.png`](../../cache/carrier_gate/screenshots/carrier-plain-explain.png) |
| **UI latency** | 7.8s |

**Prompt:** *"Briefly explain what a hash chain is, in two sentences."*

**Rendered output:** *"A hash chain is a sequence of hash values where each hash is derived from the previous one, creating a linked chain of cryptographic hashes. This structure ensures data integrity and authenticity, as altering any part of the chain would require recalculating all subsequent hashes."* (281 chars)

#### Expected vs actual

| Check | Expected | Actual | |
|-------|----------|--------|---|
| DOM outcome | `pass`, non-empty answer | `pass`, 281 chars | ✅ |
| Tool cards | 0 | 0 | ✅ |
| Planning depth | L0 | **L0** | ✅ |
| Steps executed | 1 | 1 | ✅ |
| LLM calls | ≥ 1 | 1 | ✅ |
| Model (step 0) | gpt-4o `capable-for-planning` | gpt-4o `capable-for-planning` | ✅ |
| Goal judge | `goal_met=true` | `goal_met=true`, `criteria_met=1` | ✅ |
| Task outcome | `success` | `success` | ✅ |
| Carrier phases | 4 (no tool_execution) | 4 | ✅ |
| Alerts | 0 | 0 | ✅ |
| No-block | answer rendered | answer rendered | ✅ |

#### Langfuse reasoning trace

- **`step.planned`** — depth **L0**.
- **`model.selected`** (step 0) → **gpt-4o** `capable-for-planning`.
- **1× `llm.call`**, **1× `step.executed`**.
- **`eval.goal_judge`** — `goal_met=true`.
- **`task.completed`** — outcome **success**.

#### Carrier gate (4, all pass)

`initialization` · `routing` · `model_invocation` · `output_validation`. No tool (correct skip).

---

### 3.3 `carrier-tool-write` — 2 steps, L0, 1 tool

| Field | Value |
|-------|-------|
| **gj_id** | `GJ-STRESS-903` |
| **trace_id** | [`59cb109108c355ab2aa1e73a4b4b1f19`](https://cloud.langfuse.com/trace/59cb109108c355ab2aa1e73a4b4b1f19) |
| **Screenshot** | [`carrier-tool-write.png`](../../cache/carrier_gate/screenshots/carrier-tool-write.png) |
| **UI latency** | 7.5s |

**Prompt:** *"Create a file named notes.txt containing the text 'hello carrier gate', then tell me you have created it."*

**Rendered output:** *"I have created the file named notes.txt containing the text 'hello carrier gate'."* (81 chars, **1 tool card**)

#### Expected vs actual

| Check | Expected | Actual | |
|-------|----------|--------|---|
| DOM outcome | `pass`, confirms file created | `pass`, 81 chars | ✅ |
| Tool cards | ≥ 1 (`used_tool=true`) | **1** | ✅ |
| Planning depth | L0 (single write action) | **L0** | ✅ |
| Steps executed | 2 (plan + tool + answer) | **2** | ✅ |
| LLM calls | ≥ 2 | **2** | ✅ |
| Tool calls | 1× `file_io` (write) | **1× `file_io`** | ✅ |
| Model ladder | gpt-4o step 0 → gpt-4o-mini step 1+ | gpt-4o step 0 → gpt-4o-mini step 1 | ✅ |
| Goal judge | `goal_met=true` | `goal_met=true`, `criteria_met=1` | ✅ |
| Task outcome | `success` | `success` | ✅ |
| Carrier total | 8 (init×1 + loop×2 + tool×1) | **8** | ✅ |
| `tool_execution` | 1 (write boundary) | **1** | ✅ |
| Alerts | 0 | 0 | ✅ |
| No-block | answer rendered | answer rendered | ✅ |

#### Langfuse reasoning trace

- **`step.planned`** — depth **L0**.
- **Step 0** `model.selected` → **gpt-4o** `capable-for-planning` (planning step).
- **Step 1** `model.selected` → **gpt-4o-mini** `steady-state-fast` (*"step=1, cost_usd=0.0068"* — cost-aware downgrade after plan is set).
- **1× `tool.file_io`** (write `notes.txt`), **2× `llm.call`**, **2× `step.executed`**.
- **`eval.goal_judge`** — `goal_met=true`.
- **`task.completed`** — outcome **success**.

#### Carrier gate (8, all pass)

`initialization` ×1 + `routing` / `model_invocation` / `output_validation` ×2 (one per ReAct step) + `tool_execution` ×1 (the write). Validation pillar fired exactly at the tool boundary.

---

### 3.4 `carrier-tool-multi` — 3 steps, L1, 2 tools

| Field | Value |
|-------|-------|
| **gj_id** | `GJ-STRESS-904` |
| **trace_id** | [`a0bde1adc69ea62762a2b9354f60358b`](https://cloud.langfuse.com/trace/a0bde1adc69ea62762a2b9354f60358b) |
| **Screenshot** | [`carrier-tool-multi.png`](../../cache/carrier_gate/screenshots/carrier-tool-multi.png) |
| **UI latency** | 8.0s |

**Prompt:** *"Write a file plan.txt with three short lines, then read it back and summarize what it contains."*

**Rendered output:** *"The file plan.txt contains the following lines: Complete the project report / Review the budget proposal / Schedule the team meeting. This summarizes the tasks that need to be accomplished."* (186 chars, **2 tool cards**)

#### Expected vs actual

| Check | Expected | Actual | |
|-------|----------|--------|---|
| DOM outcome | `pass`, summary of file contents | `pass`, 186 chars | ✅ |
| Tool cards | ≥ 2 (write + read) | **2** | ✅ |
| Planning depth | L1 (write→read→summarize) | **L1** | ✅ |
| Steps executed | 3 | **3** | ✅ |
| LLM calls | ≥ 3 | **3** | ✅ |
| Tool calls | 2× `file_io` (write, read) | **2× `file_io`** | ✅ |
| Model ladder | gpt-4o step 0 → gpt-4o-mini steps 1–2 | gpt-4o step 0 → gpt-4o-mini steps 1 & 2 | ✅ |
| Goal judge | `goal_met=true` | `goal_met=true`, `criteria_met=1` | ✅ |
| Task outcome | `success` | `success` | ✅ |
| Carrier total | 12 (init×1 + loop×3 + tool×2) | **12** | ✅ |
| `tool_execution` | 2 (write + read boundaries) | **2** | ✅ |
| Alerts | 0 | 0 | ✅ |
| No-block | answer rendered | answer rendered | ✅ |

#### Langfuse reasoning trace

- **`step.planned`** — depth **L1** (genuinely multi-action: write → read → summarize).
- **Step 0** `model.selected` → **gpt-4o** `capable-for-planning` (*plan_depth=L1*).
- **Steps 1 & 2** → **gpt-4o-mini** `steady-state-fast` (*cost_usd=0.0070 / 0.0072*).
- **2× `tool.file_io`** (write `plan.txt`, read it back), **3× `llm.call`**, **3× `step.executed`**.
- **`eval.goal_judge`** — `goal_met=true`.
- **`task.completed`** — outcome **success**.

#### Carrier gate (12, all pass)

`initialization` ×1 + `routing` / `model_invocation` / `output_validation` ×3 + `tool_execution` ×2. Both tool boundaries surfaced their Validation carrier — matches the 2 tool cards in the UI screenshot.

---

### 3.5 `carrier-multistep` — 1 step, L1, no tool

| Field | Value |
|-------|-------|
| **gj_id** | `GJ-STRESS-905` |
| **trace_id** | [`e689f49897a2a96f02350c6669d18036`](https://cloud.langfuse.com/trace/e689f49897a2a96f02350c6669d18036) |
| **Screenshot** | [`carrier-multistep.png`](../../cache/carrier_gate/screenshots/carrier-multistep.png) |
| **UI latency** | 7.3s |

**Prompt:** *"List three benefits of deterministic governance checks, then pick the single most important one and explain why in one sentence."*

**Rendered output:** lists **Consistency**, **Transparency**, **Efficiency**; picks **Consistency** as most important (*"…applying the same standards to all cases, thereby building trust in the system."*) — 617 chars.

#### Expected vs actual

| Check | Expected | Actual | |
|-------|----------|--------|---|
| DOM outcome | `pass`, list + pick + explain | `pass`, 617 chars | ✅ |
| Tool cards | 0 | 0 | ✅ |
| Planning depth | L1 (list-then-select instruction) | **L1** | ✅ |
| Steps executed | 1 (no tool needed) | 1 | ✅ |
| LLM calls | ≥ 1 | 1 | ✅ |
| Model (step 0) | gpt-4o `capable-for-planning` | gpt-4o `capable-for-planning` | ✅ |
| Goal judge | `goal_met=true` | `goal_met=true`, `criteria_met=1` | ✅ |
| Task outcome | `success` | `success` | ✅ |
| Carrier phases | 4 (no tool_execution) | 4 | ✅ |
| Alerts | 0 | 0 | ✅ |
| No-block | answer rendered | answer rendered | ✅ |

#### Langfuse reasoning trace

- **`step.planned`** — depth **L1** (two-part "list then select" instruction — correctly L1 even though it completed in one step without a tool).
- **`model.selected`** (step 0) → **gpt-4o** `capable-for-planning` (*plan_depth=L1*).
- **1× `llm.call`**, **1× `step.executed`**.
- **`eval.goal_judge`** — `goal_met=true`.
- **`task.completed`** — outcome **success**.

#### Carrier gate (4, all pass)

`initialization` · `routing` · `model_invocation` · `output_validation`. No tool (correct skip).

---

## 4. Cross-case observations

| Observation | Detail |
|-------------|--------|
| **Depth scorer** | Single-action factual asks → **L0** (901, 902, 903); multi-clause / multi-action → **L1** (904, 905). Matches prior baseline run. |
| **Model ladder** | Every multi-step run plans on **gpt-4o** then drops to **gpt-4o-mini** on subsequent steps — auditable from `model.selected` rationale in the trace. |
| **Carrier count lockstep** | `routing` / `model_invocation` / `output_validation` counts move together (8 each) because they share the ReAct loop body — one carrier per step-cycle. |
| **Conditional TOOL_EXECUTION** | Absent on no-tool runs (901, 902, 905) — legitimate skip, not a gap. Present only where tools ran (903: 1, 904: 2). |
| **COMPLETION pillar** | `eval.goal_judge` present on every trace (`goal_met=true`); the carrier gate deliberately does not inline-gate COMPLETION (known Phase-2 item). |
| **Post-deploy parity** | Scorecard shape (32 / 0 / 0.000) matches the pre-deploy baseline in [`governance_carrier_gate_e2e_report.md`](governance_carrier_gate_e2e_report.md). |

---

## 5. Reproduce

```bash
# Driver (prod)
cd frontend
TEST_PROFILE=prod E2E_AUTHENTICATED=1 \
  pnpm exec playwright test e2e/full-stack/carrier-gate.spec.ts --project=chromium-desktop

# Analyzer (requires LANGFUSE_* in repo-root .env)
cd ..
set -a && source .env && set +a
python scripts/analyze_planning_traces.py --source langfuse --carrier-gate \
  --jsonl cache/carrier_gate/ui_batch.jsonl
```

---

*Post-deploy walkthrough. Posture A (shadow) confirmed on prod traffic. Phase-2 enforce remains dark pending fault-injection proof (Posture C) + approval.*
