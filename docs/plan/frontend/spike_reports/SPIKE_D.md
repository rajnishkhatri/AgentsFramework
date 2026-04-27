# SPIKE_D — Langfuse Cloud Hobby SDK + traced run


| Field                     | Value                                                                                                        |
| ------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Sprint**                | 0                                                                                                            |
| **Story**                 | S0.5.1                                                                                                       |
| **Hypothesis under test** | H6 — Langfuse Cloud Hobby captures a LangGraph run as a structured trace with prompt versions and tool spans |
| **Verdict**               | ➖ **SKIPPED** per Sprint 0 decision **D-S0-6** (activates V1 fallback)                                       |


## Why skipped

The user opted not to provision a Langfuse Cloud account for v1. The
documented V1 fallback is to use **Cloud Trace + Cloud Logging only** for
v1's observability surface.

This is a deliberate cost / surface-area trade-off, not a technical
obstacle: Langfuse Cloud Hobby is free up to 50 K units / month and the
Python SDK is well-known to work, so re-running this spike is cheap if
the v1 product spec changes.

## What v1 loses


| Feature                                                                      | Without Langfuse                                                                |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Per-run trace tree (node → tool span hierarchy)                              | ✅ Cloud Trace gives this                                                        |
| Structured per-step logs                                                     | ✅ Cloud Logging gives this                                                      |
| `trace_id` propagation through every layer                                   | ✅ Already enforced by `agent_ui_adapter/translators/` (independent of Langfuse) |
| Error rate / latency dashboards                                              | ✅ Cloud Monitoring gives these                                                  |
| **Prompt-version capture** (which `.j2` template version emitted which call) | ❌ Lost in v1                                                                    |
| **Side-by-side prompt diff / A-B replay**                                    | ❌ Lost in v1                                                                    |
| **Tool-call-rate-by-prompt-version analytics**                               | ❌ Lost in v1                                                                    |
| **Eval traces correlated to prompt version**                                 | ❌ Lost in v1                                                                    |


The losses are concentrated in **prompt engineering analytics**, not in
operational observability. v1 is operationally observable; what it cannot
do is retroactively forensically debug a prompt-version regression.

## Adapter slot retained

`agent_ui_adapter/adapters/observability/` will hold a `CloudTraceExporter`
for v1 and is structured so a `LangfuseCloudHobbyAdapter` is a
**composition-root-only swap** (no `wire/`, `translators/`, `transport/`,
or `ports/` files change) per the F3 substrate-swap invariant.

## Re-open trigger

Re-run this spike when **any** of these is true:

- First prompt-version A/B test request from product.
- Any postmortem that requires retroactive prompt-version forensics.
- v1.5 product spec includes a "show me which prompt version generated
this trace" feature.

## Decision audit

- See `docs/plan/frontend/SPRINT_0_RUNBOOK.md` §0 row **D-S0-6** for the
full rationale.
- See `SPRINT_BOARD.md` "V1 Fallback Paths" table — Spike D row.