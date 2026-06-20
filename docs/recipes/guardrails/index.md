# Guardrails (5-rail safety) — bundle index

OKF sub-bundle. Each entry is a typed Concept. See the convention in [CONVENTIONS_OKF.md](../../CONVENTIONS_OKF.md).

- [Recipe 0 — Why One Tired LLM Cannot Guard Five Doors](00_overview.md) — Why one single-LLM input guardrail over-blocks legitimate work.
- [Recipe 1 — Drawing the Map Before Building the Locks](01_dimension_space.md) — Sprint 0 contracts: the 5-rail × OWASP-2025 × code/LLM matrix.
- [Recipe 2 — The Bouncer and the Trained Eye](02_prompt_and_precheck.md) — A narrowed LLM judge prompt plus a deterministic pre-check for over-block relief.
- [Recipe 3 — Teaching Without Cheating](03_synthetic_dataset.md) — Build and freeze the offline synthetic eval set for the classifier and CI gate.
- [Recipe 4 — The Trained Eye, Made Deterministic](04_finetuned_classifier.md) — Add the fine-tuned DeBERTa-v3 injection classifier stage of the Input-rail cascade.
- [Recipe 5 — Proving the Door Lets the Plumber In](05_ci_gate_and_revalidation.md) — Turn the frozen eval set into a three-axis CI gate with revalidation.
- [Recipe 6 — Sanitizing the Mail Slot](06_retrieval_rail.md) — Close the indirect prompt-injection gap on the Retrieval rail.
- [Recipe 7 — Guardrails Validation Walkthrough (Human Executor)](07_validation_walkthrough.md) — Human-executor validation that the Sprint 0–5 guardrails program works in practice.
- [Recipe 8 — Telemetry Redaction & BlackBox Relay Validation Walkthrough](08_telemetry_redaction_validation_walkthrough.md) — Validate the session telemetry fixes (I9–I12) and BlackBox relay redaction end to end.
- [Recipe 9 — Proving the Guard Showed Up: Observable, Deterministic Rails](09_rail_observability_and_determinism.md) — Close G2/G3 — make every guardrail decision provable and deterministic in traces.
