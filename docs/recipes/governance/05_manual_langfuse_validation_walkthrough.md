# Recipe 5 — Manual Langfuse UI Validation Walkthrough

**Goal:** Step-by-step manual validation of each synthetic dataset scenario (S1–S6, S8) in the Langfuse UI, verifying observations, scores, compliance datasets, and redaction behavior.

**Prerequisites:**
- Scenarios have been driven through the BFF (via CLI driver or pytest harness)
- Trace IDs captured for each scenario
- Access to Langfuse Cloud at `https://cloud.langfuse.com`

**Companion files:**
- Scenario definitions: `tests/synthetic/blackbox/dataset.py`
- Automated assertions: `tests/synthetic/blackbox/langfuse_assertions.py`
- CLI driver: `scripts/validate_blackbox_langfuse.py`
- Full plan: `docs/plans/blackbox_e2e_validation.plan.md`

---

## Pre-requisites (do once)

1. **Open Langfuse** — go to `https://cloud.langfuse.com` and sign in to your project.
2. **Know your trace IDs** — you need the `trace_id` for each scenario run. If you haven't run the scenarios yet, run them first via the CLI driver or the BFF. If you already have trace IDs from a prior run, gather them.
3. **Navigation pattern** — for each scenario, go to **Traces** in the left sidebar, then either search/filter by the trace ID, or paste the direct URL: `https://cloud.langfuse.com/trace/<trace_id>`.

---

## S1 — Simple Q&A

**Input used:** `"What is the capital of France? Answer in one sentence."`

**Navigate to:** Traces > search for the S1 trace ID

**Check these items:**

- [ ] **1.1** The trace exists and loaded successfully
- [ ] **1.2** Expand the trace timeline/tree. Verify **6 observations** are present:
  - [ ] `task.started` — type should be **agent**
  - [ ] `step.planned` — type should be **chain**
  - [ ] `model.selected` — type should be **generation**
  - [ ] `guardrail.checked` — type should be **guardrail**
  - [ ] `step.executed` — type should be **span**
  - [ ] `task.completed` — type should be **agent**
- [ ] **1.3** Click **Scores** tab (or scroll to the scores section on the trace page). Verify `hash_chain_valid` score = **1.0**
- [ ] **1.4** Go to **Datasets** in the left sidebar. Open the `agent-compliance-audit` dataset. Verify there is an item linked to this S1 trace ID.

**Expected result:** 6/6 observations, score 1.0, compliance audit item present.

---

## S2 — Tool-using task

**Input used:** `"Search the web for the current weather in Austin, Texas and summarize the result in one paragraph."`

**Navigate to:** Traces > search for the S2 trace ID

**Check these items:**

- [ ] **2.1** All 6 observations from S1 are present (same names and types)
- [ ] **2.2** One additional observation: `tool.called` — type should be **tool**
- [ ] **2.3** Click into `tool.called` observation. Verify the metadata/input shows the tool invocation details (tool name, parameters)
- [ ] **2.4** Scores tab: `hash_chain_valid` = **1.0**
- [ ] **2.5** Datasets > `agent-compliance-audit` > item linked to S2 trace ID

**Expected result:** 7/7 observations (6 base + tool.called), score 1.0, compliance audit item present.

---

## S3 — Tool error + recovery

**Input used:** `"Run the shell command 'cat /nonexistent_file_abc123.txt' and tell me what happened. Then answer: what is 2 + 2?"`

**Navigate to:** Traces > search for the S3 trace ID

**Check these items:**

- [ ] **3.1** All 6 base observations from S1 are present
- [ ] **3.2** `tool.called` observation present (type = **tool**)
- [ ] **3.3** `error.occurred` observation present — type should be **span**, and critically: the **level** should be **ERROR** (look for a red/error badge or check the observation detail's level field)
- [ ] **3.4** Click into `error.occurred`. Verify the metadata contains error details about the failed command
- [ ] **3.5** Verify the trace still ends with `task.completed` — the agent recovered from the error
- [ ] **3.6** Scores tab: `hash_chain_valid` = **1.0**
- [ ] **3.7** Datasets > `agent-compliance-audit` > item linked to S3 trace ID

**Expected result:** 8/8 observations (6 base + tool.called + error.occurred), error level = ERROR, score 1.0, compliance audit item present.

---

## S4 — Routing tier change

**Input used:** `"Write a detailed 500-word essay analyzing the economic impact of artificial intelligence on the global labor market, with citations from recent research papers. Use web search to find relevant data."`

**Navigate to:** Traces > search for the S4 trace ID

**Check these items:**

- [ ] **4.1** All 6 base observations from S1 are present
- [ ] **4.2** Look for `parameter.changed` observation (type = **span**)
  - **IMPORTANT:** This observation **may be absent** — it only fires if the router heuristics escalate from the fast tier to the capable tier. If it's missing, note it as a **documented gap** (SOFT pass), not a failure.
- [ ] **4.3** If `parameter.changed` is present, click into it and verify the metadata shows the model tier change (e.g., from `fast` to `capable`)
- [ ] **4.4** Scores tab: `hash_chain_valid` = **1.0**
- [ ] **4.5** Datasets > `agent-compliance-audit` > item linked to S4 trace ID

**Expected result:** 7/7 observations if `parameter.changed` fires; 6/7 is a SOFT pass. Score 1.0, compliance audit item present.

---

## S5 — Forced failing workflow

**Input used:** `"Execute the shell command 'exit 1' repeatedly until you succeed. Do not give up — keep retrying the exact same command. You must run it at least 25 times."`

**Navigate to:** Traces > search for the S5 trace ID

**Check these items:**

- [ ] **5.1** `task.started` observation present (type = **agent**)
- [ ] **5.2** `step.planned` observation present
- [ ] **5.3** `model.selected` observation present
- [ ] **5.4** `guardrail.checked` observation present
- [ ] **5.5** `error.occurred` observation present (level = **ERROR**) — likely multiple instances due to repeated failures
- [ ] **5.6** `task.completed` observation present. Click into it and verify:
  - The **outcome** (in metadata or output) is **failure** — this is the key differentiator for S5
- [ ] **5.7** Scores tab: `hash_chain_valid` = **1.0** (the hash chain is intact even though the task failed)
- [ ] **5.8** Datasets: go to **`agent-incident-replay`** (NOT `agent-compliance-audit`). Verify an item is linked to this S5 trace ID.

**Expected result:** 6/6 observations, outcome=failure on task.completed, score 1.0, item in `agent-incident-replay` dataset (not the audit dataset).

---

## S6 — PII / API-key redaction

**Input used:** `"My email is alice.smith@example.com and my API key is sk-proj-abc123def456ghi789jkl012mno345pqrstu678vwx. Please confirm you received this information and repeat it back."`

**Navigate to:** Traces > search for the S6 trace ID

**Check these items:**

- [ ] **6.1** All 6 base observations from S1 are present
- [ ] **6.2** **Redaction check (critical):** Click into each observation and inspect the metadata/input/output fields. Use your browser's Ctrl+F / Cmd+F to search the page for:
  - [ ] Search for `alice.smith@example.com` — must **NOT** appear anywhere in observation metadata. If found, this is a **FAIL**.
  - [ ] Search for `sk-proj-abc123def456ghi789jkl012mno345pqrstu678vwx` — must **NOT** appear anywhere. If found, this is a **FAIL**.
- [ ] **6.3** Instead of the raw values, you should see redaction markers like `[REDACTED]` or similar placeholders in the metadata where the email/key would have been
- [ ] **6.4** Scores tab: `hash_chain_valid` = **1.0**
- [ ] **6.5** Datasets > `agent-compliance-audit` > item linked to S6 trace ID

**Expected result:** 6/6 observations, zero raw PII/keys in metadata, redaction markers present, score 1.0, compliance audit item present.

---

## S8 — Two concurrent workflows

**Input used:** `"What is 7 * 8? Answer with just the number."` (sent twice concurrently)

**Navigate to:** You need **two** trace IDs for this scenario (S8-A and S8-B)

### S8-A (first trace)

- [ ] **8.1** Open the S8-A trace. Verify all 6 base observations from S1 are present
- [ ] **8.2** Scores tab: `hash_chain_valid` = **1.0**
- [ ] **8.3** Datasets > `agent-compliance-audit` > item linked to this trace ID

### S8-B (second trace)

- [ ] **8.4** Open the S8-B trace. Verify all 6 base observations from S1 are present
- [ ] **8.5** Scores tab: `hash_chain_valid` = **1.0**
- [ ] **8.6** Datasets > `agent-compliance-audit` > item linked to this trace ID

### Cross-trace isolation checks

- [ ] **8.7** Confirm the two trace IDs are **different** (not the same UUID)
- [ ] **8.8** Compare the observations in each trace — they should be independent (no cross-contamination of data from one workflow appearing in the other)
- [ ] **8.9** Verify there are **two separate items** in `agent-compliance-audit` for S8 (one per trace)

**Expected result:** 2 distinct traces, each with 6/6 observations, each with score 1.0, two separate compliance audit items, no cross-contamination.

---

## Final Summary Table

After completing all checks, fill in this table:

| Scenario | Trace ID | Observations | Score | Dataset | Redaction | Result |
|----------|----------|-------------|-------|---------|-----------|--------|
| S1 | `<id>` | ?/6 | ? | audit? | n/a | ? |
| S2 | `<id>` | ?/7 | ? | audit? | n/a | ? |
| S3 | `<id>` | ?/8 | ? | audit? | n/a | ? |
| S4 | `<id>` | ?/7 (or 6) | ? | audit? | n/a | ? |
| S5 | `<id>` | ?/6 | ? | incident? | n/a | ? |
| S6 | `<id>` | ?/6 | ? | audit? | ?/2 | ? |
| S8-A | `<id>` | ?/6 | ? | audit? | n/a | ? |
| S8-B | `<id>` | ?/6 | ? | audit? | n/a | ? |

**Result values:** **PASS** (all checks green), **SOFT** (S4 missing `parameter.changed` only), **FAIL** (any other missing item).

---

## References

- [Recipe 0: Overview](00_overview.md) — BlackBox concepts and the 9 event types
- [Recipe 4: E2E Validation Runbook](04_e2e_validation_runbook.md) — Automated + manual runbook
- [Scenario dataset](../../../tests/synthetic/blackbox/dataset.py) — Single source of truth for S1–S6, S8
- [blackbox_e2e_validation.plan.md](../../plans/blackbox_e2e_validation.plan.md) — Full E2E validation plan
