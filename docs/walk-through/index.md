# GoalJudge validation walkthroughs — bundle index

OKF bundle. Each entry is a typed Concept. See the convention in [CONVENTIONS_OKF.md](../CONVENTIONS_OKF.md).

- [PhaseLogger GCP Validation — Step-by-Step Walkthrough](01_phaselogger_gcp_validation_walkthrough.md) — Goal: Validate, end to end, that the PhaseLogger (Reasoning pillar) and the trace-gap closure items (G1, G4, G5, G6, G7-G9) work on the live GCP deployment.
- [GoalJudge UI + Langfuse Validation — Step-by-Step Walkthrough](02_goaljudge_ui_langfuse_validation_walkthrough.md) — Goal: Validate, end to end, that the GoalJudge (I2 task-adaptive LLM-as-judge) produces honest GoalVerdicts and that the success → partial downgrade gate behaves correctly under
- [GoalJudge Synthetic Saturation Corpus — Step-by-Step Walkthrough](03_goaljudge_synthetic_saturation_walkthrough.md) — Goal: Create a structured synthetic corpus sized for stratified coverage to saturation of the seeded taxonomy (~3-5 examples per failure code across 19 distinct codes, single
- [GoalJudge Synthetic Prompt Matrix — Manual Walkthrough](04_goaljudge_synthetic_prompt_matrix_manual_walkthrough.md) — Goal: Hand-validate the 47-case live synthetic prompt matrix (Phase 2b saturation corpus) the same way 02 — UI + Langfuse validation validates P1–P5: run each prompt, record
- [GoalJudge Axial Coding & Failure Taxonomy — Manual Walkthrough](05_goaljudge_axial_coding_failure_taxonomy_walkthrough.md) — Goal: Run the Stage 3 axial coding + failure taxonomy exercise — cluster the Stage-2 open
- [GoalJudge Stage 4 A2 IAA — Case Walkthrough Procedure](06_goaljudge_stage4_a2_iaa_case_walkthrough.md) — Goal: Review all 8 IAA anchor cases one at a time — UI screenshot, Langfuse trace, and
