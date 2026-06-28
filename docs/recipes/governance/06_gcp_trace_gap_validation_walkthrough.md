---
type: validation-walkthrough
title: 'Recipe 6 — GCP Trace Gap Validation Walkthrough (Frontend UI)'
description: 'Frontend-UI validation that deployed Trace Gap Closure items render in Langfuse.'
tags: [recipe, governance]
---

# Recipe 6 — GCP Trace Gap Validation Walkthrough (Frontend UI)

**Goal:** Step-by-step validation that the deployed Trace Gap Closure items (G1, G4, G5, G6, G7–G9) work in practice against the live GCP environment. We will use real-world prompts in the Frontend UI to validate G1, G5, G6, and G9, and local synthetic traces to validate G4, G7, and G8 (since they cannot be prompted honestly).

**Audience:** AI intern engineer executing validation manually.

**Time budget:** ~1 hour with the Frontend UI and Langfuse.

**Status:** Human validation guide | complements automated CI in Recipe 13

**Prerequisites:**

- Deployed GCP environment is active.
- Langfuse Cloud access.
- Familiarity with the trace gap program: `docs/plans/trace_gap_closure.plan.md`.
- Read Recipe 13: [`../13_negative_path_traces_and_schema_versioning.md`](../13_negative_path_traces_and_schema_versioning.md).

---

## Before We Start: What You Are Proving

The Trace Gap program fixed several critical observability and correctness issues. We are proving that:
1. **G9 (Shell Errors):** A failed shell command correctly registers an `ERROR_OCCURRED` event instead of silently failing or looping.
2. **G5 & G6 (Loop Cap & Goal Met):** The agent stops gracefully when making no progress, and correctly marks `goal_met=False` (partial success) instead of claiming a clean success.
3. **G1 (Redaction):** PII and API keys entered into the UI are redacted in the telemetry database.
4. **G4, G7, G8 (Synthetic Failures):** The system correctly handles schema versioning, rejected verifications, and broken hash chains using synthetic traces.

---

## Part 0 — One-Time Setup

Ensure you have your environment variables set if you need to run CLI fallback tools, and have your browser open to the GCP Frontend URL and Langfuse Cloud.

```bash
export FRONTEND_URL="https://your-deployed-app.com"
export LANGFUSE_HOST="https://cloud.langfuse.com"
```

1. Open `FRONTEND_URL` in your browser and sign in.
2. Open another tab to `LANGFUSE_HOST` and navigate to your project's **Traces** page.

---

## Part 1 — G9 Shell Error Validation (Real-World UI Prompt)

We will intentionally trigger a tool error to ensure the `ERROR_OCCURRED` observability gap is closed.

### 1.1 Drive the UI
In the Frontend UI chat, submit the following prompt:
> *"Please list the contents of the `/nonexistent_directory_abc123` directory."*

Wait for the agent to attempt the command and report back that the directory does not exist.

### 1.2 Langfuse UI Checklist
Find the generated trace in Langfuse.

- [ ] **G9.1** `tool.called` event is present for the shell command.
- [ ] **G9.2** `error.occurred` event is present with level **ERROR**.
- [ ] **G9.3** `task.completed` is present.
- [ ] **G9.4** Check the terminal `error_type` if the task aborted, or verify the agent recovered and explained the failure to the user.

**Pass Criteria:** The error must not be silent. The backend shell executor returning `ok=False` must surface in Langfuse.

---

## Part 2 — G5 & G6 Loop Cap & Goal Met (Real-World UI Prompt)

We will test the agent's ability to realize it is stuck, terminate the loop, and accurately report a partial success.

### 2.1 Drive the UI
In the Frontend UI chat, submit an impossible task:
> *"Search the web for the exact phrase 'xyzq123impossiblephrase987' and retry repeatedly until you find exactly 50 results."*

Watch the UI. The agent should try searching, fail to find results, and eventually give up rather than looping infinitely.

### 2.2 Langfuse UI Checklist
Find the generated trace in Langfuse.

- [ ] **G5.1** The trace has a finite number of steps (it did not hit a massive `max_steps` cap, but stopped early due to `count_trailing_repeats` / `no_progress_repeat_threshold`).
- [ ] **G6.1** Click on the `task.completed` event details.
- [ ] **G6.2** **`goal_met` must be `false`**.
- [ ] **G6.3** `outcome` should be `partial` (or downgraded from `success`).
- [ ] **G6.4** `termination_reason` should indicate `no_progress`.

**Pass Criteria:** The trace must prove the agent halted itself gracefully and correctly reported that the user's goal was not met.

---

## Part 3 — G1 Telemetry Redaction (Real-World UI Prompt)

We must prove that sensitive user inputs are stripped from Langfuse telemetry before they are stored.

### 3.1 Drive the UI
In the Frontend UI chat, submit a prompt containing fake secrets:
> *"My email is alice.smith@example.com and my secret key is sk-proj-abc123456789. Please confirm you received them."*

Wait for the agent to acknowledge.

### 3.2 Langfuse UI Checklist
Find the generated trace in Langfuse.

- [ ] **G1.1** Open the trace and press `Ctrl+F` (or `Cmd+F`).
- [ ] **G1.2** Search for `alice.smith@example.com`. **0 results must be found.**
- [ ] **G1.3** Search for `sk-proj-abc123`. **0 results must be found.**
- [ ] **G1.4** Look at the `input_text` and model outputs. You should see `[REDACTED]` where the email and key were expected.

**Pass Criteria:** Absolute zero presence of the raw email or API key in the Langfuse trace payloads.

---

## Part 4 — G4, G7 & G8 Synthetic Negative Paths (CLI Validation)

Because we cannot honestly prompt the agent to corrupt its own hash chain (G8) or fail its own hardcoded identity checks (G7) via the Frontend UI, these must be verified locally using the synthetic scenarios (S7, S9, S10, S11).

*Note: These scenarios are strictly excluded from the live BFF scenario list so they cannot be driven against the real agent.*

### 4.1 Run the Pure-Bundle Assertions
In your local terminal with the repository activated:

```bash
# Run the 12 negative-path failure matrix tests
python -m pytest -p no:logfire tests/middleware/sidecars/test_compliance_dataset.py -q
```

### 4.2 Terminal Checklist
- [ ] **G7.1** `TestG7FailedAgentFactsTrace` passes (proves `summary.outcome == 'rejected'` surfaces).
- [ ] **G8.1** `test_broken_chain_routes_to_incident_with_break_location` passes (proves corrupted hash chain sets `hash_chain_valid=0.0` and populates `broken_at_event_id`).
- [ ] **G4.1** `TestBundleSchemaVersion` passes in `test_black_box_export.py` (proves `bundle_schema_version="2"` is stamped on all terminal events).

**Pass Criteria:** All local Pytest suites pass, proving the relay and export functions handle synthetic corruption and rejections correctly.

---

## Part 5 — Final Sign-Off Table

| Section | Evidence | Result |
| --- | --- | --- |
| Part 1 (G9) | Shell error shows `error.occurred` in Langfuse | ☐ |
| Part 2 (G5/G6) | Impossible task sets `goal_met=false` and halts | ☐ |
| Part 3 (G1) | `[REDACTED]` hides PII/keys in Langfuse | ☐ |
| Part 4 (G4/G7/G8) | Pure-bundle pytest matrix passes locally | ☐ |

**Overall:** PASS when all checkboxes are complete.

---

## Troubleshooting

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| Agent endlessly loops in Part 2 | Evaluator component missing the `no_progress` cap | Verify deployment contains the Recipe 11 code |
| Secrets visible in Langfuse | Relay redaction not applied | Escalate immediately; redaction failure is a P0 |
| `pytest` fails for synthetic traces | Environment mismatch or missing dependencies | Re-run `pip install -e ".[dev]"` |
| `task.completed` missing `bundle_schema_version` | Outdated deployment | Confirm backend is running the Phase 2 schema version update |
