# Governance / BlackBox → Langfuse — bundle index

OKF sub-bundle. Each entry is a typed Concept. See the convention in [CONVENTIONS_OKF.md](../../CONVENTIONS_OKF.md).

- [Recipe 0 — The Black Box Hidden in Your Cache Folder](00_overview.md) — The BlackBox flight recorder already in your cache folder — what it captures.
- [Recipe 1 — The Dual-Write Bug That Could Have Stayed Hidden Forever](01_outbox_relay.md) — Build the relay that tails the BlackBox JSONL outbox and publishes to Langfuse.
- [Recipe 2 — Translating Nine Languages Into One Timeline](02_event_mapping.md) — Map all 9 BlackBox event types to Langfuse observations with idempotent IDs.
- [Recipe 3 — Turning Every Failed Workflow Into a Lesson Plan](03_compliance_dataset.md) — Publish each completed workflow's compliance bundle as a Langfuse dataset item.
- [Recipe 4 — End-to-End BlackBox → Langfuse Validation Runbook](04_e2e_validation_runbook.md) — End-to-end BlackBox → Langfuse pipeline validation on GCP.
- [Recipe 5 — Manual Langfuse UI Validation Walkthrough](05_manual_langfuse_validation_walkthrough.md) — Manual Langfuse-UI validation of each synthetic dataset scenario (S1–S8).
- [Recipe 6 — GCP Trace Gap Validation Walkthrough (Frontend UI)](06_gcp_trace_gap_validation_walkthrough.md) — Frontend-UI validation that deployed Trace Gap Closure items render in Langfuse.
- [Recipe 7 — Manual PhaseLogger (Reasoning Pillar) Langfuse Validation Walkthrough](07_manual_phaselogger_validation_walkthrough.md) — Manual Langfuse validation of the Phase 3 PhaseLogger (Reasoning pillar) wiring.
- [Recipe 8 — Three Planner Bugs in One Trace](08_three_planner_bugs_in_one_trace.md) — How layered identifier collisions mask each other in an agent planner.
